"""
Deterministic excerpt-match metric (companion to faithfulness_verbatim).

For every gold case the file `pdf_reference.excerpt` contains the *exact
verbatim text* that the audit team transcribed from the PDF. This metric
checks whether that excerpt (or a sufficient n-gram subset) appears in the
LLM-generated explanation, the retrieved chunks, or both.

Three sub-metrics are computed per case:

    1. excerpt_in_llm        : the gold excerpt is reproduced verbatim
                                (3-gram coverage >= threshold) inside the
                                LLM `MOTIVAZIONE`/`FONTI` body.
    2. excerpt_in_retrieval  : the gold excerpt is present in at least one
                                retrieved chunk (Track 2-style support check).
    3. gold_anchor_in_topk   : the gold (pdf_file, page) is among the top-k
                                retrieved chunks (k=3, 5, 10).

Aggregate metrics:

    excerpt_match_rate_llm        — fraction of cases where #1 holds
    excerpt_match_rate_retrieval  — fraction of cases where #2 holds
    gold_anchor_recall_at_{3,5,10}— fraction of cases where #3 holds for that k

Inputs:
    --pipeline-report    pipeline_report.json (Track 3 output, has retrieved chunks metadata)
    --explanations-dir   directory of per-case LLM .txt files (saved with --save-explanations)
    --gold-dir           evaluation/gold_standard/
    --output             output JSON path

Usage:
    python -m evaluation.metrics.excerpt_match \\
        --pipeline-report evaluation/results/pipeline_report.json \\
        --explanations-dir evaluation/results/pipeline_explanations \\
        --gold-dir evaluation/gold_standard \\
        --output evaluation/results/excerpt_match.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean


_NGRAM_THRESHOLD = 0.8
_NGRAM_N = 3

# Set at runtime by main() so module-level helpers see the user-chosen threshold.
_RUNTIME_THRESHOLD: float = _NGRAM_THRESHOLD


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[«»\"'`,;:.!?()\[\]{}–—-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ngrams(text: str, n: int = _NGRAM_N) -> list[str]:
    words = _normalize(text).split()
    if len(words) < n:
        return [_normalize(text)] if text else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _coverage(needle: str, haystack_normalized: str) -> float:
    grams = _ngrams(needle)
    if not grams:
        return 0.0
    matched = sum(1 for g in grams if g in haystack_normalized)
    return matched / len(grams)


from evaluation.metrics._chroma_helpers import get_chroma_collection as _get_chroma_collection


def _fetch_chunk_texts(case_chunks: list[dict]) -> dict[str, str]:
    """Return {chunk_id: text} for every retrieved chunk, looking up in ChromaDB."""
    by_nota: dict[str, list[str]] = {}
    for c in case_chunks:
        cid = c.get("chunk_id", "")
        if not cid:
            continue
        pdf = c.get("pdf_file", "")
        if "97" in pdf:
            nid = "97"
        elif "13" in pdf:
            nid = "13"
        elif "66" in pdf:
            nid = "66"
        elif "01" in pdf or "Nota_01" in pdf:
            nid = "01"
        else:
            continue
        by_nota.setdefault(nid, []).append(cid)

    out: dict[str, str] = {}
    for nid, ids in by_nota.items():
        col = _get_chroma_collection(nid)
        if col is None:
            continue
        try:
            res = col.get(ids=ids, include=["documents"])
            for cid, doc in zip(res.get("ids", []), res.get("documents", []) or []):
                out[cid] = doc or ""
        except Exception as exc:
            print(f"  WARN: chunk lookup failed: {exc}", file=sys.stderr)
    return out


def _load_gold_index(gold_dir: Path) -> dict[str, dict]:
    """Return {case_id: case_dict} merged across all 4 nota gold files."""
    idx: dict[str, dict] = {}
    for nota in ("01", "13", "66", "97"):
        f = gold_dir / f"nota_{nota}_cases.json"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        for c in data.get("cases", []):
            idx[c["id"]] = c
    return idx


def _evaluate_case(
    case_result: dict,
    case_gold: dict,
    explanation_text: str,
    chunk_texts: dict[str, str],
) -> dict:
    pdf_ref = case_gold.get("pdf_reference", {}) or {}
    excerpt = (pdf_ref.get("excerpt") or "").strip()
    gold_pdf = pdf_ref.get("pdf_file", "")
    gold_page = pdf_ref.get("page", 0)

    # 1. excerpt in LLM
    cov_llm = _coverage(excerpt, _normalize(explanation_text)) if excerpt and explanation_text else 0.0
    in_llm = cov_llm >= _RUNTIME_THRESHOLD

    # 2. excerpt in retrieved chunks
    chunks_blob = " ".join(chunk_texts.values())
    cov_ret = _coverage(excerpt, _normalize(chunks_blob)) if excerpt and chunks_blob else 0.0
    in_retrieval = cov_ret >= _RUNTIME_THRESHOLD

    # 3. gold anchor in top-k
    chunks = case_result.get("retrieved_chunks_metadata", [])
    pages_top = [(c.get("pdf_file", ""), c.get("page", 0)) for c in chunks]
    gold_pair = (gold_pdf, gold_page) if gold_pdf else None
    in_top = {
        "top_3": gold_pair in pages_top[:3] if gold_pair else None,
        "top_5": gold_pair in pages_top[:5] if gold_pair else None,
        "top_10": gold_pair in pages_top[:10] if gold_pair else None,
    }

    return {
        "case_id": case_gold["id"],
        "gold_pdf_file": gold_pdf,
        "gold_page": gold_page,
        "gold_excerpt_len": len(excerpt),
        "excerpt_in_llm": in_llm,
        "excerpt_coverage_llm": round(cov_llm, 4),
        "excerpt_in_retrieval": in_retrieval,
        "excerpt_coverage_retrieval": round(cov_ret, 4),
        "gold_anchor_in_top_3": in_top["top_3"],
        "gold_anchor_in_top_5": in_top["top_5"],
        "gold_anchor_in_top_10": in_top["top_10"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--gold-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--ngram-threshold", type=float, default=_NGRAM_THRESHOLD,
                   help=f"3-gram coverage threshold for excerpt match (default {_NGRAM_THRESHOLD})")
    args = p.parse_args()
    global _RUNTIME_THRESHOLD
    _RUNTIME_THRESHOLD = args.ngram_threshold

    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)
    case_results = report.get("case_results", [])
    gold_idx = _load_gold_index(Path(args.gold_dir))
    expl_dir = Path(args.explanations_dir)

    per_case: list[dict] = []
    for cr in case_results:
        cid = cr["case_id"]
        gold = gold_idx.get(cid)
        if gold is None:
            continue
        expl_file = expl_dir / f"{cid}.txt"
        explanation = expl_file.read_text(encoding="utf-8") if expl_file.exists() else ""
        chunk_texts = _fetch_chunk_texts(cr.get("retrieved_chunks_metadata", []))
        per_case.append(_evaluate_case(cr, gold, explanation, chunk_texts))

    n = len(per_case)
    if n == 0:
        print("ERROR: no cases evaluated", file=sys.stderr)
        return 1

    def _frac(key: str) -> float:
        vals = [r[key] for r in per_case if r.get(key) is not None]
        return round(sum(1 for v in vals if v) / max(len(vals), 1), 4)

    aggregate = {
        "n_cases": n,
        "ngram_threshold": _RUNTIME_THRESHOLD,
        "excerpt_match_rate_llm": _frac("excerpt_in_llm"),
        "excerpt_match_rate_retrieval": _frac("excerpt_in_retrieval"),
        "gold_anchor_recall_at_3": _frac("gold_anchor_in_top_3"),
        "gold_anchor_recall_at_5": _frac("gold_anchor_in_top_5"),
        "gold_anchor_recall_at_10": _frac("gold_anchor_in_top_10"),
        "mean_excerpt_coverage_llm": round(mean(r["excerpt_coverage_llm"] for r in per_case), 4),
        "mean_excerpt_coverage_retrieval": round(mean(r["excerpt_coverage_retrieval"] for r in per_case), 4),
    }

    out = {"metric": "excerpt_match", "aggregate": aggregate, "per_case": per_case}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Excerpt Match — {n} cases")
    print(f"{'=' * 60}")
    for k, v in aggregate.items():
        if k in ("n_cases", "ngram_threshold"):
            continue
        print(f"  {k:35s} {v}")
    print(f"\nReport written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
