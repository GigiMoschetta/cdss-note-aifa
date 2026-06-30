"""
M3-bis — Semantic Similarity Italian (cross-encoder STSB)
=========================================================

Complementary metric to M3 (NLI). Where M3 measures entailment vs chunk
(strict logical relation), M3-bis measures *italian-native textual similarity*
between each LLM motivation sentence and the retrieved chunks.

Model: nickprock/cross-encoder-italian-bert-stsb
       (Italian-tuned cross-encoder fine-tuned on STSB-it; output ∈ [0, 5])

For each LLM explanation:
  1. Extract sentences from the MOTIVAZIONE section (same as M3).
  2. For every (sentence, chunk) pair, compute STSB similarity score.
  3. Per sentence: max similarity across chunks (best-supporting chunk).
  4. M3-bis_per_case = mean over sentences of max-similarity, normalised to [0, 1].

Why this metric in addition to M3:
  - The XNLI multilingual model used by M3 is generic and not Italian-specific;
    its entailment scores can be artificially low on Italian normative prose
    (vocabulary distribution mismatch).
  - This cross-encoder is *trained on Italian sentence pairs* and is therefore
    a stronger signal of "the LLM sentence is supported by the chunks" in the
    italian-text domain.

NOT a replacement for M3 — it answers a different (semantic similarity) question
than NLI (logical entailment). Both are reported for triangulation.

Usage:
    python -m evaluation.metrics.semantic_similarity_italian \
        --pipeline-report evaluation/results/pipeline_report.json \
        --explanations-dir evaluation/results/pipeline_explanations \
        --output evaluation/results/semantic_similarity_italian.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from statistics import mean, median, stdev

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_EXPLANATIONS_DIR = _ROOT / "evaluation" / "results" / "pipeline_explanations"
_OUTPUT = _ROOT / "evaluation" / "results" / "semantic_similarity_italian.json"

_MODEL_ID = "nickprock/cross-encoder-italian-bert-stsb"
_STSB_MAX = 5.0      # STSB score range is [0, 5]; normalise to [0, 1]
_MAX_CHUNKS_PER_SENTENCE = 8


def _extract_motivation(text: str) -> str:
    m = re.search(
        r"^\s*2\.\s*MOTIVAZIONE\s*\n(.+?)(?=^\s*\d+\.\s|\Z)",
        text, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    return m.group(1).strip() if m else text


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"---\s*PROVA.*?---\s*FINE\s*---", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"---\s*DATI\s*MANCANTI.*?---\s*FINE\s*DATI.*?---", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^\s*5\.\s*FONTI.*", "", text, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"^\s*\d+\.\s+[A-ZÀ-Ÿ ]+$", "", text, flags=re.MULTILINE)
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 30]


def _load_model(model_id: str):
    """Load the cross-encoder. Returns (model, device)."""
    from sentence_transformers import CrossEncoder
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CrossEncoder(model_id, device=device)
    return model, device


def compute_ssim_for_case(explanation: str, chunks: list[str], model) -> dict:
    motiv = _extract_motivation(explanation)
    sents = _split_sentences(motiv)
    if not sents or not chunks:
        return {"skipped": True, "reason": "no sentences or no chunks"}

    used_chunks = chunks[:_MAX_CHUNKS_PER_SENTENCE]
    per_sentence: list[dict] = []
    sent_max_sims: list[float] = []

    for sent in sents:
        # Build (sentence, chunk_text) pairs — model.predict returns scores in [0, 5]
        pairs = [(sent, c[:600]) for c in used_chunks]
        scores_raw = model.predict(pairs)
        # Normalise to [0, 1]
        scores = [max(0.0, min(1.0, float(s) / _STSB_MAX)) for s in scores_raw]
        max_sim = max(scores) if scores else 0.0
        sent_max_sims.append(max_sim)
        per_sentence.append({
            "sentence_preview": sent[:120] + ("..." if len(sent) > 120 else ""),
            "max_similarity": round(max_sim, 4),
        })

    return {
        "skipped": False,
        "n_sentences": len(sents),
        "mean_max_similarity": round(mean(sent_max_sims), 4),
        "min_max_similarity": round(min(sent_max_sims), 4),
        "n_low_support": sum(1 for s in sent_max_sims if s < 0.5),
        "per_sentence": per_sentence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-report", type=Path, default=_PIPELINE_REPORT)
    parser.add_argument("--explanations-dir", type=Path, default=_EXPLANATIONS_DIR)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    parser.add_argument("--model-id", type=str, default=_MODEL_ID,
                        help="HuggingFace cross-encoder model id (default: %(default)s)")
    parser.add_argument("--max-cases", type=int, default=0,
                        help="Limit cases for testing (0 = all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("ssim_it")

    if not args.pipeline_report.exists():
        log.error(f"Pipeline report missing: {args.pipeline_report}")
        return 1

    rep = json.loads(args.pipeline_report.read_text())
    cases = rep.get("case_results", [])
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    log.info(f"Loaded {len(cases)} cases from {args.pipeline_report}")

    log.info(f"Loading cross-encoder: {args.model_id}")
    model, device = _load_model(args.model_id)
    log.info(f"Model loaded on {device}")

    # ChromaDB lookup for chunk text (same scheme used by semantic_faithfulness_v2)
    import chromadb
    chroma_dir = _ROOT / "rag_pipeline" / "chroma_db"
    chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
    suffix = os.environ.get("CHROMA_COLLECTION_SUFFIX", "_v2")
    log.info(f"ChromaDB at {chroma_dir} (suffix={suffix})")
    coll_cache: dict[str, object] = {}

    def _fetch_chunk_text(chunk_id: str, nota_id: str) -> str | None:
        col_name = f"nota_{nota_id}{suffix}"
        if col_name not in coll_cache:
            try:
                coll_cache[col_name] = chroma_client.get_collection(col_name)
            except Exception:
                return None
        col = coll_cache[col_name]
        try:
            r = col.get(ids=[chunk_id], include=["documents"])
            if r["documents"]:
                return r["documents"][0]
        except Exception:
            return None
        return None

    per_case: list[dict] = []
    sims: list[float] = []

    for c in cases:
        case_id = c.get("case_id")
        ex_path = args.explanations_dir / f"{case_id}.txt"
        if not ex_path.exists():
            per_case.append({"case_id": case_id, "skipped": True, "reason": "explanation file missing"})
            continue
        explanation = ex_path.read_text()
        chunks_meta = c.get("retrieved_chunks_metadata", []) or []
        chunk_texts: list[str] = []
        case_nota = case_id.split("-")[0].lstrip("N").zfill(2) if "-" in case_id else None
        for cm in chunks_meta:
            t = cm.get("text") or cm.get("chunk_text", "")
            if t:
                chunk_texts.append(t)
                continue
            chunk_id = cm.get("chunk_id")
            nota = cm.get("nota_id") or case_nota
            if not chunk_id or not nota:
                continue
            fetched = _fetch_chunk_text(chunk_id, nota)
            if not fetched:
                for alt in ("01", "13", "66", "97"):
                    if alt == nota:
                        continue
                    fetched = _fetch_chunk_text(chunk_id, alt)
                    if fetched:
                        break
            if fetched:
                chunk_texts.append(fetched)
        if not chunk_texts:
            per_case.append({
                "case_id": case_id, "skipped": True,
                "reason": "no chunk text available (ChromaDB lookup failed)",
            })
            continue

        result = compute_ssim_for_case(explanation, chunk_texts, model)
        result["case_id"] = case_id
        per_case.append(result)
        if not result.get("skipped"):
            sims.append(result["mean_max_similarity"])
        if (len(per_case) % 10) == 0:
            log.info(f"  processed {len(per_case)}/{len(cases)}")

    if sims:
        agg = {
            "n_cases_evaluated": len(sims),
            "n_cases_skipped": len(cases) - len(sims),
            "ssim_mean": round(mean(sims), 4),
            "ssim_median": round(median(sims), 4),
            "ssim_std": round(stdev(sims), 4) if len(sims) > 1 else 0.0,
            "n_low_support_total": sum(c.get("n_low_support", 0) for c in per_case if not c.get("skipped")),
        }
    else:
        agg = {"n_cases_evaluated": 0, "n_cases_skipped": len(cases)}

    out = {
        "metric": "M3bis_semantic_similarity_italian",
        "description": (
            "Italian-native STSB cross-encoder similarity between LLM motivation sentences "
            "and retrieved chunks. Per sentence: max similarity across chunks. "
            "Per case: mean over sentences. Normalized to [0,1] from raw STSB [0,5]. "
            "Complements M3 (NLI entailment) — different question (similarity vs entailment), "
            "Italian-specific model."
        ),
        "model": args.model_id,
        "tautological": False,
        "score_range": [0.0, 1.0],
        "interpretation": (
            "≥0.7 strong support; 0.5-0.7 partial; <0.5 weak support — see per_sentence."
        ),
        "n_cases_total": len(cases),
        "aggregate": agg,
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(f"SSIM mean={agg.get('ssim_mean','?')} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
