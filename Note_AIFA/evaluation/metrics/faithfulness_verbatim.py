"""
Day 4 audit fix F5-9 ALTO: deterministic faithfulness verbatim metric.

For each LLM-generated explanation, verifies that quoted text matches
verbatim text from the retrieved chunks. Catches paraphrased or invented
"normative-looking" content.

Algorithm: extract quoted spans from explanation (inside double quotes or
between specific markers), then check N-gram (3-gram) coverage in retrieved
chunks. A claim is "verbatim-supported" if ≥80% of its 3-grams appear in
some chunk's text.

Returns aggregate metrics:
- verbatim_quote_rate    — fraction of quoted spans that are verbatim-supported
- avg_ngram_coverage     — mean 3-gram coverage across all quoted spans
- n_quotes_per_explanation — distribution

Usage:
    python -m evaluation.metrics.faithfulness_verbatim \
        --pipeline-report evaluation/results/pipeline_report.json \
        --output evaluation/results/faithfulness_verbatim.json

NOTE: this metric works on existing pipeline_report.json (Track 3 output);
no need to re-run the LLM. Reads `generated_explanation` and
`retrieved_chunks_metadata` from each case.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean, median


def normalize_text(text: str) -> str:
    """Normalize for N-gram matching: lowercase, collapse whitespace, strip punct."""
    text = text.lower()
    text = re.sub(r'[,;:.!?\'"()\[\]{}«»]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def trigrams(text: str) -> list[str]:
    """Return word-level 3-grams."""
    words = normalize_text(text).split()
    if len(words) < 3:
        return [normalize_text(text)]
    return [" ".join(words[i:i+3]) for i in range(len(words) - 2)]


def extract_quoted_spans(explanation: str) -> list[str]:
    """Extract quoted text spans (between double quotes or 'PROVA NORMATIVA' markers).

    Audit fix 2026-05-04 P0.2: added Italian guillemets «...» support — the
    deterministic PROVE NORMATIVA template uses caporali ("Testo verbatim:
    «...»") not ASCII double-quotes, so the previous regex captured zero spans
    in 122/122 cases, making the metric vacuous (mean_verbatim_quote_rate=1.0
    spuriously high because numerator and denominator were both 0).
    """
    spans: list[str] = []
    # ASCII / curly double quotes "..."
    for m in re.finditer(r'"([^"]{20,500})"', explanation):
        spans.append(m.group(1))
    # Italian caporali «...» (used by deterministic PROVE NORMATIVA template).
    # Verbatim PDF excerpts may exceed 500 chars (whole PDF paragraph cited),
    # so cap at 5000 and use re.DOTALL to allow multi-line content.
    for m in re.finditer(r'«([^»]{20,5000})»', explanation, re.DOTALL):
        spans.append(m.group(1))
    # PROVA NORMATIVA blocks
    for m in re.finditer(r'PROVA NORMATIVA(.*?)FINE', explanation, re.DOTALL):
        block = m.group(1)
        # "Testo verbatim: «...»" (current template) and legacy "Testo: \"...\""
        for sub in re.finditer(r'Testo\s+verbatim:\s*«([^»]+)»', block, re.DOTALL):
            spans.append(sub.group(1))
        for sub in re.finditer(r'Testo:\s*"([^"]{20,5000})"', block, re.DOTALL):
            spans.append(sub.group(1))
    # Long parenthetical excerpts (e.g. citing a passage)
    for m in re.finditer(r'\(([^)]{50,500})\)', explanation):
        s = m.group(1)
        # Heuristic: only consider it a quote if it has at least one comma
        # (indicates substantive content vs short clarification)
        if "," in s:
            spans.append(s)
    return spans


from evaluation.metrics._chroma_helpers import get_chroma_collection as _get_chroma_collection  # noqa: E402


def chunk_text_pool(case_result: dict) -> str:
    """Return the concatenated normalized text of all retrieved chunks.

    Strategy:
    1. If chunk text is embedded in the report, use it.
    2. Otherwise, lookup chunks by chunk_id from ChromaDB.
    """
    chunks = case_result.get("retrieved_chunks_metadata", [])
    if not chunks:
        return ""

    # Strategy 1: text already in report
    texts = []
    chunks_without_text = []
    for c in chunks:
        if isinstance(c, dict) and c.get("text"):
            texts.append(c["text"])
        elif isinstance(c, dict) and c.get("chunk_id"):
            chunks_without_text.append(c)

    # Strategy 2: lookup from ChromaDB
    if chunks_without_text:
        # Group by nota_id to minimize collection lookups
        by_nota: dict[str, list[str]] = {}
        for c in chunks_without_text:
            nota = c.get("pdf_file", "")
            # Map pdf_file → nota_id
            if "97" in nota:
                nid = "97"
            elif "13" in nota:
                nid = "13"
            elif "66" in nota:
                nid = "66"
            elif "01" in nota or "Nota_01" in nota:
                nid = "01"
            else:
                continue
            by_nota.setdefault(nid, []).append(c["chunk_id"])

        for nid, ids in by_nota.items():
            col = _get_chroma_collection(nid)
            if col is None:
                continue
            try:
                result = col.get(ids=ids, include=["documents"])
                docs = result.get("documents", []) or []
                texts.extend(docs)
            except Exception as exc:
                print(f"  WARN: chunk lookup failed: {exc}", file=sys.stderr)

    return normalize_text(" ".join(texts))


def check_quote_verbatim(quote: str, chunk_pool_normalized: str, threshold: float = 0.8) -> dict:
    """Check if a quote is verbatim-supported. Returns coverage info."""
    grams = trigrams(quote)
    if not grams:
        return {"verbatim": True, "n_grams": 0, "coverage": 1.0}
    matched = sum(1 for g in grams if g in chunk_pool_normalized)
    coverage = matched / len(grams)
    return {
        "verbatim": coverage >= threshold,
        "n_grams": len(grams),
        "n_matched": matched,
        "coverage": round(coverage, 4),
    }


def evaluate_case(case_result: dict) -> dict:
    """Compute verbatim faithfulness for one case."""
    explanation = case_result.get("explanation", "") or case_result.get("generated_explanation", "")
    if not explanation:
        return {"case_id": case_result.get("case_id", "?"), "skip_reason": "no_explanation"}

    spans = extract_quoted_spans(explanation)
    if not spans:
        # No quoted spans — verbatim_rate is *undefined*, not 1.0 vacuously.
        # Returning None lets the aggregate distinguish "0 verbatim cited" from
        # "100% verbatim verified". Aggregate filters None to compute a true
        # mean only over cases that *actually quoted* normative text.
        return {
            "case_id": case_result.get("case_id"),
            "n_quoted_spans": 0,
            "n_verbatim_supported": 0,
            "verbatim_rate": None,
            "avg_coverage": None,
            "skip_reason": "no_quoted_spans",
        }

    pool = chunk_text_pool(case_result)
    if not pool:
        return {
            "case_id": case_result.get("case_id"),
            "skip_reason": "no_chunks_in_report",
            "n_quoted_spans": len(spans),
        }

    span_results = [check_quote_verbatim(s, pool) for s in spans]
    n_verbatim = sum(1 for r in span_results if r["verbatim"])
    avg_cov = mean(r["coverage"] for r in span_results) if span_results else 1.0

    return {
        "case_id": case_result.get("case_id"),
        "n_quoted_spans": len(spans),
        "n_verbatim_supported": n_verbatim,
        "verbatim_rate": round(n_verbatim / len(spans), 4),
        "avg_coverage": round(avg_cov, 4),
        "span_details": span_results,
    }


def load_full_responses_dir(dir_path: Path) -> list[dict]:
    """Load CDSSResponse JSONs from audit/llm_outputs/. Each has full
    `generated_explanation` + `retrieved_chunks` with text — perfect for
    verbatim verification."""
    responses = []
    for f in sorted(dir_path.glob("*.json")):
        if f.name.startswith("_"):
            continue
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        # Wrap as case_result-like dict
        case_id = f.stem
        responses.append({
            "case_id": case_id,
            "generated_explanation": data.get("generated_explanation", ""),
            "retrieved_chunks_metadata": data.get("retrieved_chunks", []),
        })
    return responses


def merge_pipeline_with_explanations(report: dict, explanations_dir: Path) -> list[dict]:
    """Combine pipeline_report case_results with saved explanation .txt files."""
    merged = []
    for cr in report.get("case_results", []):
        cid = cr.get("case_id", "")
        expl_path = explanations_dir / f"{cid}.txt"
        if expl_path.exists():
            cr_copy = dict(cr)
            cr_copy["generated_explanation"] = expl_path.read_text(encoding="utf-8")
            merged.append(cr_copy)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--pipeline-report",
                        help="Pipeline report JSON (uses chunk_id ChromaDB lookup; needs save-explanations)")
    parser.add_argument("--explanations-dir",
                        help="Pair with --pipeline-report: directory of saved explanation .txt files")
    parser.add_argument("--llm-outputs-dir",
                        help="Alternative: directory of raw CDSSResponse JSONs (has full text)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.llm_outputs_dir:
        case_results = load_full_responses_dir(Path(args.llm_outputs_dir))
        print(f"Loaded {len(case_results)} CDSSResponse files from {args.llm_outputs_dir}")
    elif args.pipeline_report and args.explanations_dir:
        with open(args.pipeline_report, encoding="utf-8") as f:
            report = json.load(f)
        case_results = merge_pipeline_with_explanations(report, Path(args.explanations_dir))
        print(f"Loaded {len(case_results)} cases (pipeline_report + explanations)")
    elif args.pipeline_report:
        with open(args.pipeline_report, encoding="utf-8") as f:
            report = json.load(f)
        case_results = report.get("case_results", [])
        print(f"Processing {len(case_results)} cases from {args.pipeline_report}...")
    else:
        print("ERROR: provide --pipeline-report (+ --explanations-dir) or --llm-outputs-dir", file=sys.stderr)
        return 1

    per_case = []
    n_evaluated = 0
    n_skipped = 0
    for cr in case_results:
        result = evaluate_case(cr)
        per_case.append(result)
        if "skip_reason" in result:
            n_skipped += 1
        else:
            n_evaluated += 1

    # Aggregate — separate "actually-quoted" cases from "no-quote" (None) cases.
    # Mean is computed ONLY over cases that quoted at least one span; cases with
    # zero quoted spans are tracked separately to avoid the vacuous-1.0 inflation
    # bug (audit C4): an LLM that never quotes used to get verbatim_rate=1.0.
    quoted = [
        r for r in per_case
        if "skip_reason" not in r and r.get("verbatim_rate") is not None
    ]
    no_quote = [r for r in per_case if r.get("skip_reason") == "no_quoted_spans"]
    n_quoted = len(quoted)
    n_no_quote = len(no_quote)

    if n_quoted > 0:
        agg_verbatim_rate = mean(r["verbatim_rate"] for r in quoted)
        agg_avg_coverage = mean(r["avg_coverage"] for r in quoted)
        n_quotes_list = [r["n_quoted_spans"] for r in quoted]
        med_quotes = median(n_quotes_list)
        max_quotes = max(n_quotes_list)
        n_perfect = sum(1 for r in quoted if r["verbatim_rate"] == 1.0)
        perfect_rate = n_perfect / n_quoted
    else:
        agg_verbatim_rate = None
        agg_avg_coverage = None
        med_quotes = max_quotes = 0
        perfect_rate = None

    out = {
        "metric": "faithfulness_verbatim",
        "method": "3-gram coverage (threshold 0.8) of quoted spans against retrieved chunks",
        "n_cases_evaluated": n_evaluated,
        "n_cases_skipped": n_skipped,
        "n_cases_with_quotes": n_quoted,
        "n_cases_without_quotes": n_no_quote,
        "aggregate": {
            # Means computed ONLY over cases that actually quoted ≥1 span.
            # If no case quoted, the rate is undefined (None).
            "mean_verbatim_quote_rate": round(agg_verbatim_rate, 4) if agg_verbatim_rate is not None else None,
            "mean_3gram_coverage": round(agg_avg_coverage, 4) if agg_avg_coverage is not None else None,
            "perfect_verbatim_rate": round(perfect_rate, 4) if perfect_rate is not None else None,
            "median_quotes_per_explanation": med_quotes,
            "max_quotes_per_explanation": max_quotes,
            # Audit V4 2026-05-12: fixed denominator. Was n_no_quote / n_evaluated
            # which produced a value >1 (e.g. 83/39 = 2.13) because n_no_quote
            # counts SKIPPED cases (skip_reason=no_quoted_spans) while
            # n_evaluated only counts NON-skipped ones. The correct rate is over
            # the TOTAL evaluable explanations: skipped + evaluated.
            "no_quote_rate": round(
                n_no_quote / max(n_no_quote + n_evaluated, 1), 4
            ),
        },
        "per_case": per_case,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    def _pct(v: float | None) -> str:
        return f"{v*100:.2f}%" if v is not None else "N/A (no quoted spans)"

    print(f"\n{'='*60}")
    print(f"Faithfulness Verbatim — {n_evaluated} cases evaluated")
    print(f"{'='*60}")
    print(f"Cases with quoted spans:     {n_quoted}/{n_evaluated}")
    print(f"Cases without quoted spans:  {n_no_quote}/{n_evaluated}  (excluded from mean)")
    print(f"Mean verbatim quote rate:    {_pct(agg_verbatim_rate)}  [over n={n_quoted}]")
    print(f"Mean 3-gram coverage:        {_pct(agg_avg_coverage)}  [over n={n_quoted}]")
    print(f"Perfect verbatim cases:      {_pct(perfect_rate)}")
    print(f"Median quotes/explanation:   {med_quotes}")
    print(f"Max quotes/explanation:      {max_quotes}")
    print(f"Cases skipped (no data):     {n_skipped}")
    print(f"{'='*60}")
    print(f"\nReport written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
