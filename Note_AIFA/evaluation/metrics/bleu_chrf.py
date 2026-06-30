"""
Deterministic lexical-alignment metric (BLEU + chrF) for the LLM MOTIVAZIONE
section against the retrieved chunks corpus.

Rationale: ROUGE-L vs `gold_answer` is structurally low (gold_answer is a
single reference sentence, the LLM produces a 5-section answer ~300-600 tokens),
so ROUGE-L mainly measures structural mismatch, not lexical fidelity. BLEU and
chrF computed against the *retrieved chunks* (the LLM's actual evidence) instead
quantify how much of the LLM wording is anchored in the source PDF text.

What we compute, per case:
  - bleu_motivazione_vs_chunks   : sacrebleu BLEU (Italian tokeniser="13a")
  - chrf_motivazione_vs_chunks   : sacrebleu chrF score (character-3gram + word-1gram)
  - chrfpp_motivazione_vs_chunks : chrF++ (adds word-2gram component)

Aggregate: mean / median / std across N cases.

Inputs:
  --pipeline-report     pipeline_report.json (Track 3)
  --explanations-dir    directory of per-case .txt files
  --output              JSON output

Usage:
    python -m evaluation.metrics.bleu_chrf \\
        --pipeline-report evaluation/results/pipeline_report.json \\
        --explanations-dir evaluation/results/pipeline_explanations \\
        --output evaluation/results/bleu_chrf.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean, median, stdev

import sacrebleu

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent

_CHROMA_CACHE: dict[str, object] = {}


def _get_chroma_collection(nota_id: str):
    """Lazy-load ChromaDB collection. None if unavailable.

    Audit fix 2026-05-06 (H8): default CHROMA_COLLECTION_SUFFIX aligned to
    "_v2" — was "" in this module while every other module used "_v2",
    producing a silent zero-evaluated-cases run when CHROMA_COLLECTION_SUFFIX
    was not exported.
    """
    if nota_id in _CHROMA_CACHE:
        return _CHROMA_CACHE[nota_id]
    try:
        import chromadb, os
        suffix = os.getenv("CHROMA_COLLECTION_SUFFIX", "_v2")
        client = chromadb.PersistentClient(path=str(_PROJECT / "rag_pipeline" / "chroma_db"))
        col = client.get_collection(f"nota_{nota_id}{suffix}")
        _CHROMA_CACHE[nota_id] = col
        return col
    except Exception as exc:
        print(f"  WARN: ChromaDB unavailable for nota_{nota_id}: {exc}", file=sys.stderr)
        _CHROMA_CACHE[nota_id] = None
        return None


def _fetch_chunk_texts(chunks_meta: list[dict]) -> list[str]:
    """Resolve chunk ids to their full text via ChromaDB."""
    by_nota: dict[str, list[str]] = {}
    for c in chunks_meta:
        cid = c.get("chunk_id")
        nota = c.get("nota_id") or _infer_nota_from_pdf(c.get("pdf_file", ""))
        if cid and nota:
            by_nota.setdefault(nota, []).append(cid)
    texts: list[str] = []
    for nota, ids in by_nota.items():
        col = _get_chroma_collection(nota)
        if col is None:
            continue
        try:
            res = col.get(ids=ids, include=["documents"])
            for doc in res.get("documents", []):
                if doc:
                    texts.append(doc)
        except Exception as exc:
            print(f"  WARN: chunk fetch failed for nota_{nota}: {exc}", file=sys.stderr)
    return texts


def _infer_nota_from_pdf(pdf_file: str) -> str | None:
    name = pdf_file.lower()
    for n in ("01", "13", "66", "97"):
        if f"_{n}" in name or f"-{n}" in name or f"nota_{n}" in name or f"nota-{n}" in name:
            return n
    return None


_MOTIVAZIONE_RE = re.compile(
    r"(?:^|\n)\s*2\.\s*MOTIVAZIONE\s*\n(.*?)(?=\n\s*3\.|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_motivazione(explanation: str) -> str:
    m = _MOTIVAZIONE_RE.search(explanation)
    return m.group(1).strip() if m else ""


def _evaluate_case(case_result: dict, explanation_text: str, gold_excerpt: str | None) -> dict | None:
    motivazione = _extract_motivazione(explanation_text)
    if not motivazione:
        return None
    chunk_texts = _fetch_chunk_texts(case_result.get("retrieved_chunks_metadata", []))
    if not chunk_texts:
        return None
    # vs full chunks (lexical anchoring of the explanation in retrieved evidence).
    # Audit note 2026-05-06 (H8-bis): we deliberately concatenate chunks into a
    # single reference, so BLEU's brevity penalty is computed against the full
    # corpus length. This measures lexical *coverage* of retrieved evidence by
    # the LLM motivazione, not paraphrase quality. The thesis must report this
    # interpretation explicitly. (Multi-reference BLEU with chunk_texts as
    # separate refs would over-credit any chunk match — equally undesirable.)
    refs_full = [[" ".join(chunk_texts)]]
    hyp = [motivazione]
    bleu_full = sacrebleu.corpus_bleu(hyp, refs_full, tokenize="13a").score
    chrf_full = sacrebleu.corpus_chrf(hyp, refs_full).score
    chrfpp_full = sacrebleu.corpus_chrf(hyp, refs_full, word_order=2).score
    # vs gold excerpt only (closest analogue to a "reference translation")
    out = {
        "case_id": case_result["case_id"],
        "motivazione_chars": len(motivazione),
        "n_chunks": len(chunk_texts),
        "bleu_vs_chunks": round(bleu_full, 4),
        "chrf_vs_chunks": round(chrf_full, 4),
        "chrfpp_vs_chunks": round(chrfpp_full, 4),
    }
    if gold_excerpt:
        refs_excerpt = [[gold_excerpt]]
        out["bleu_vs_excerpt"] = round(sacrebleu.corpus_bleu(hyp, refs_excerpt, tokenize="13a").score, 4)
        out["chrf_vs_excerpt"] = round(sacrebleu.corpus_chrf(hyp, refs_excerpt).score, 4)
        out["chrfpp_vs_excerpt"] = round(sacrebleu.corpus_chrf(hyp, refs_excerpt, word_order=2).score, 4)
        out["gold_excerpt_chars"] = len(gold_excerpt)
    return out


def _load_gold_index(gold_dir: Path) -> dict[str, str]:
    """Return {case_id: pdf_reference.excerpt} for every case."""
    idx: dict[str, str] = {}
    for nota in ("01", "13", "66", "97"):
        f = gold_dir / f"nota_{nota}_cases.json"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        for c in data.get("cases", []):
            ref = (c.get("pdf_reference") or {}).get("excerpt") or ""
            idx[c["id"]] = ref.strip()
    return idx


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--gold-dir", default=str(_PROJECT / "evaluation" / "gold_standard"),
                   help="Path to gold_standard dir for fetching pdf_reference.excerpt")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)
    expl_dir = Path(args.explanations_dir)
    gold_idx = _load_gold_index(Path(args.gold_dir))

    per_case: list[dict] = []
    skipped = 0
    for cr in report.get("case_results", []):
        cid = cr["case_id"]
        expl_file = expl_dir / f"{cid}.txt"
        if not expl_file.exists():
            skipped += 1
            continue
        explanation = expl_file.read_text(encoding="utf-8")
        gold_excerpt = gold_idx.get(cid) or None
        result = _evaluate_case(cr, explanation, gold_excerpt)
        if result is None:
            skipped += 1
            continue
        per_case.append(result)

    if not per_case:
        print("ERROR: no cases evaluated (check ChromaDB availability and explanations dir)",
              file=sys.stderr)
        return 1

    def _agg(key: str) -> dict | None:
        vals = [r[key] for r in per_case if key in r]
        if not vals:
            return None
        return {
            "mean": round(mean(vals), 4),
            "median": round(median(vals), 4),
            "std": round(stdev(vals), 4) if len(vals) > 1 else 0.0,
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "n": len(vals),
        }

    aggregate = {
        "n_cases_evaluated": len(per_case),
        "n_cases_skipped": skipped,
        "bleu_vs_chunks": _agg("bleu_vs_chunks"),
        "chrf_vs_chunks": _agg("chrf_vs_chunks"),
        "chrfpp_vs_chunks": _agg("chrfpp_vs_chunks"),
        "bleu_vs_excerpt": _agg("bleu_vs_excerpt"),
        "chrf_vs_excerpt": _agg("chrf_vs_excerpt"),
        "chrfpp_vs_excerpt": _agg("chrfpp_vs_excerpt"),
    }

    out = {
        "metric": "bleu_chrf_motivazione",
        "tokenizer": "13a",
        "references": {
            "vs_chunks": "concatenated retrieved chunks (Track 2 output)",
            "vs_excerpt": "gold_standard pdf_reference.excerpt (verbatim PDF text)",
        },
        "aggregate": aggregate,
        "per_case": per_case,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"BLEU/chrF — MOTIVAZIONE ({len(per_case)} cases)")
    print("=" * 60)
    for k, label in (("bleu_vs_chunks", "BLEU vs chunks"),
                      ("chrf_vs_chunks", "chrF vs chunks"),
                      ("chrfpp_vs_chunks", "chrF++ vs chunks"),
                      ("bleu_vs_excerpt", "BLEU vs excerpt"),
                      ("chrf_vs_excerpt", "chrF vs excerpt"),
                      ("chrfpp_vs_excerpt", "chrF++ vs excerpt")):
        a = aggregate.get(k)
        if a:
            print(f"  {label:20s}  mean={a['mean']:7.4f}  median={a['median']:7.4f}  std={a['std']:7.4f}  n={a['n']}")
    print(f"\nReport written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
