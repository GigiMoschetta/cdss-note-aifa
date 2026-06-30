"""
NLI-based faithfulness using mDeBERTa-v3-base-mnli-xnli (multilingual NLI model,
deterministic, no judge LLM).

Per ogni frase della MOTIVAZIONE LLM, calcola entailment / contradiction
contro la concatenazione dei chunk recuperati. La metrica è la frazione di
frasi entailed (prob_entailment ≥ 0,5) e la frazione di frasi che contraddicono
i chunk (prob_contradiction ≥ 0,3 — red flag).

Vantaggi vs RAGAS Faithfulness (LLM judge):
  - Riproducibile: stesso input → stesso output
  - Veloce: ~1 sec/frase (vs ~30s per Llama judge)
  - Documentato in letteratura (mDeBERTa-v3 è il modello standard per NLI)

Output:
  evaluation/results/nli_faithfulness_{suffix}.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean


_PROJECT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"


def _split_sentences(text: str) -> list[str]:
    """Split MOTIVAZIONE section text into sentences (Italian-aware)."""
    # Strip the section header if present
    text = re.sub(r"^\s*\d+\.\s*MOTIVAZIONE.*?\n", "", text, flags=re.IGNORECASE)
    # Take only the body before next section
    text = re.split(r"^\s*\d+\.\s*[A-ZÀÈÉ]", text, maxsplit=1, flags=re.MULTILINE)[0]
    # Sentence split on Italian terminators
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÀÈÉÌÒÙ])", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]


def _extract_motivation_sentences(explanation: str) -> list[str]:
    """Find the MOTIVAZIONE section and split it into sentences."""
    m = re.search(
        r"^\s*2\.\s*MOTIVAZIONE\s*\n(.*?)(?=^\s*\d+\.\s*[A-ZÀÈÉÌÒÙ]|\Z)",
        explanation, flags=re.MULTILINE | re.DOTALL,
    )
    if not m:
        return _split_sentences(explanation)
    return _split_sentences(m.group(1))


from evaluation.metrics._chroma_helpers import get_chroma_collection as _get_chroma_collection  # noqa: E402


def _load_chunk_texts(case_chunks: list[dict]) -> list[str]:
    """Look up chunk texts from ChromaDB by chunk_id and return AS LIST (not concatenated)
    so NLI can be run per-chunk and the max entailment kept.

    Honours CHROMA_COLLECTION_SUFFIX env var (audit fix 2026-05-04 P0.1):
    pipeline produces V2 chunk_ids when CHROMA_COLLECTION_SUFFIX=_v2 is set;
    this helper reads the same env var so V1 and V2 work transparently.
    """
    if not case_chunks:
        return []

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

    docs: list[str] = []
    for nid, ids in by_nota.items():
        col = _get_chroma_collection(nid)
        if col is None:
            continue
        try:
            res = col.get(ids=ids, include=["documents"])
            docs.extend(d or "" for d in res.get("documents", []) or [])
        except Exception as exc:
            print(f"  WARN: chunk lookup nota_{nid}: {exc}", file=sys.stderr)
    return [d for d in docs if d.strip()]


_NLI_PIPELINE = None


def _get_nli_pipeline(model_name: str, device: str = "cpu"):
    global _NLI_PIPELINE
    if _NLI_PIPELINE is not None:
        return _NLI_PIPELINE
    from transformers import pipeline
    print(f"Loading NLI model: {model_name} (device={device})", file=sys.stderr)
    _NLI_PIPELINE = pipeline(
        "text-classification",
        model=model_name,
        tokenizer=model_name,
        device=device,
        top_k=None,  # return all class probabilities
    )
    return _NLI_PIPELINE


def _classify(premise: str, hypothesis: str, nli) -> dict:
    """Run NLI on (premise, hypothesis) and return {entailment, neutral, contradiction}."""
    # mDeBERTa expects a single string with [SEP], pipeline handles via candidate
    # Use the standard NLI input: "premise [SEP] hypothesis" — the HF pipeline
    # accepts a dict {text, text_pair}.
    out = nli({"text": premise[:2000], "text_pair": hypothesis[:512]})
    if isinstance(out, list) and out and isinstance(out[0], list):
        out = out[0]  # nested list when top_k=None
    elif isinstance(out, dict):
        out = [out]
    probs = {}
    for item in out:
        label = (item.get("label") or "").lower()
        if "entail" in label:
            probs["entailment"] = float(item["score"])
        elif "contradict" in label:
            probs["contradiction"] = float(item["score"])
        elif "neutral" in label:
            probs["neutral"] = float(item["score"])
    return probs


def evaluate_case(case_result: dict, explanation: str, nli) -> dict:
    chunks_list = _load_chunk_texts(case_result.get("retrieved_chunks_metadata", []))
    if not chunks_list:
        return {"case_id": case_result.get("case_id"), "skip_reason": "no_chunks"}

    sentences = _extract_motivation_sentences(explanation)
    if not sentences:
        return {"case_id": case_result.get("case_id"), "skip_reason": "no_motivation_sentences"}

    sentence_results = []
    for s in sentences:
        # Run NLI(chunk_i, sentence) for every chunk.
        # Aggregation policy (audit fix 2026-05-06, H6): use MAX both for
        # entailment ("does ANY chunk support the claim?") and for contradiction
        # ("does ANY chunk contradict the claim?"). The previous mean-of-
        # contradictions was conservative for noise but inconsistent with
        # semantic_faithfulness_v2.py and made the 0.3/0.5 thresholds non-comparable.
        # The MAX-MAX policy yields a symmetric "best-chunk-evidence" reading:
        #   entailed     = ∃ chunk c. P(c entails s) ≥ 0.5
        #   contradicted = ∃ chunk c. P(c contradicts s) ≥ 0.3
        per_chunk = [_classify(chunk, s, nli) for chunk in chunks_list]
        best_ent_idx = max(
            range(len(per_chunk)),
            key=lambda i: per_chunk[i].get("entailment", 0.0),
        )
        best_ent = per_chunk[best_ent_idx]
        max_contradiction = max(p.get("contradiction", 0.0) for p in per_chunk)
        sentence_results.append({
            "sentence": s,
            "entailment": round(best_ent.get("entailment", 0.0), 4),
            "neutral": round(best_ent.get("neutral", 0.0), 4),
            "contradiction": round(max_contradiction, 4),
            "best_chunk_idx": best_ent_idx,
        })

    n = len(sentence_results)
    n_entailed = sum(1 for r in sentence_results if r["entailment"] >= 0.5)
    n_contradiction = sum(1 for r in sentence_results if r["contradiction"] >= 0.3)
    return {
        "case_id": case_result.get("case_id"),
        "n_sentences": n,
        "entailment_rate": round(n_entailed / n, 4) if n else 0.0,
        "contradiction_rate": round(n_contradiction / n, 4) if n else 0.0,
        "mean_entailment": round(mean(r["entailment"] for r in sentence_results), 4),
        "mean_contradiction": round(mean(r["contradiction"] for r in sentence_results), 4),
        "per_sentence": sentence_results,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--model", default=_DEFAULT_MODEL)
    p.add_argument("--device", default="cpu", help="cpu | cuda:0 | etc.")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)

    expl_dir = Path(args.explanations_dir)
    nli = _get_nli_pipeline(args.model, args.device)

    case_results = report.get("case_results", [])
    if args.limit:
        case_results = case_results[:args.limit]

    per_case = []
    for cr in case_results:
        cid = cr.get("case_id", "?")
        expl_file = expl_dir / f"{cid}.txt"
        explanation = expl_file.read_text(encoding="utf-8") if expl_file.exists() else ""
        if not explanation:
            per_case.append({"case_id": cid, "skip_reason": "no_explanation"})
            continue
        try:
            result = evaluate_case(cr, explanation, nli)
        except Exception as exc:
            print(f"  ERROR on {cid}: {exc}", file=sys.stderr)
            result = {"case_id": cid, "skip_reason": f"error: {exc}"}
        per_case.append(result)
        sys.stderr.write(".")
        sys.stderr.flush()
    sys.stderr.write("\n")

    valid = [r for r in per_case if "skip_reason" not in r]
    aggregate = {}
    if valid:
        aggregate = {
            "n_cases_evaluated": len(valid),
            "n_cases_skipped": len(per_case) - len(valid),
            "mean_entailment_rate": round(mean(r["entailment_rate"] for r in valid), 4),
            "median_entailment_rate": round(sorted(r["entailment_rate"] for r in valid)[len(valid)//2], 4),
            "mean_contradiction_rate": round(mean(r["contradiction_rate"] for r in valid), 4),
            "mean_entailment_prob": round(mean(r["mean_entailment"] for r in valid), 4),
            "mean_contradiction_prob": round(mean(r["mean_contradiction"] for r in valid), 4),
        }

    out = {
        "metric": "nli_faithfulness",
        "model": args.model,
        "aggregate": aggregate,
        "per_case": per_case,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"NLI Faithfulness ({args.model.split('/')[-1]})")
    print(f"{'='*60}")
    for k, v in aggregate.items():
        print(f"  {k:30s} {v}")
    print(f"\nReport: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
