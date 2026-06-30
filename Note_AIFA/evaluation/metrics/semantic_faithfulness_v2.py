"""
M3 — Semantic Faithfulness (NLI-based, GPU+fp16 Italian-aware)
==============================================================

For each LLM explanation:
  1. Extract sentences from the MOTIVAZIONE section (or the whole text if section
     not detected).
  2. For each sentence, compute NLI(premise=chunk_text, hypothesis=sentence) over
     all retrieved chunks. The score per sentence is the MAX entailment over chunks.
  3. SF = mean over sentences of max_entailment.

Model: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli (multilingual; XNLI includes Italian).

Validation: this metric is non-tautological. It does NOT confront the LLM against
an author-scripted gold; it confronts each LLM claim against retrieved PDF chunks.

Hardware: forced fp16 on CUDA, batch size 16 for ~10x speedup vs CPU.

Caveats documented in tesi:
  - mDeBERTa is multilingual, NOT specifically fine-tuned on Italian normative
    text. A floor effect can lower the score even when the LLM is faithful.
  - Recommended interpretation: SF is a LOWER BOUND of actual faithfulness.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report_v2.json"
_PIPELINE_REPORT_FALLBACK = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_EXPLANATIONS_DIR_V2 = _ROOT / "evaluation" / "results" / "pipeline_explanations_v2"
_EXPLANATIONS_DIR_V1 = _ROOT / "evaluation" / "results" / "pipeline_explanations"
_OUTPUT = _ROOT / "evaluation" / "results" / "semantic_faithfulness_v2.json"

_MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
_MAX_LEN = 256  # reduced from 512 to fit in ~2GB VRAM alongside Ollama
_BATCH_SIZE = 4  # reduced from 16; mDeBERTa fp16 + chunks*sents needs less batch


def _extract_motivation(text: str) -> str:
    m = re.search(
        r"^\s*2\.\s*MOTIVAZIONE\s*\n(.+?)(?=^\s*\d+\.\s|\Z)",
        text, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    return m.group(1).strip() if m else text


def _split_sentences(text: str) -> list[str]:
    # Strip evidence boxes / FONTI section
    text = re.sub(r"---\s*PROVA.*?---\s*FINE\s*---", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"---\s*DATI\s*MANCANTI.*?---\s*FINE\s*DATI.*?---", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^\s*5\.\s*FONTI.*", "", text, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"^\s*\d+\.\s+[A-ZÀ-Ÿ ]+$", "", text, flags=re.MULTILINE)
    # Sentence split
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 30]  # min length filter


def _resolve_label_indices(label_map: dict[int, str]) -> tuple[int, int, int]:
    """Map model.config.id2label to (entailment_idx, neutral_idx, contradiction_idx).

    Audit fix 2026-05-06 (C2): the previous code hardcoded indices [0]=ent,
    [1]=neu, [2]=con — correct for `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`
    but silently inverted if a different MNLI checkpoint is used (e.g. some
    DeBERTa-v2 variants emit {0:contradiction, 1:neutral, 2:entailment}).
    Resolve dynamically and assert all three labels are present at boot.
    """
    norm = {i: str(lbl).strip().lower() for i, lbl in label_map.items()}
    by_label: dict[str, int] = {}
    for i, lbl in norm.items():
        if "entail" in lbl:
            by_label["entailment"] = i
        elif "contradict" in lbl:
            by_label["contradiction"] = i
        elif "neutral" in lbl:
            by_label["neutral"] = i
    missing = {"entailment", "neutral", "contradiction"} - by_label.keys()
    if missing:
        raise RuntimeError(
            f"NLI model label_map is missing required labels: {missing}. "
            f"Got id2label={label_map}. Refusing to proceed with fixed indices."
        )
    return by_label["entailment"], by_label["neutral"], by_label["contradiction"]


def _load_model(model_id: str = _MODEL_ID):
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id).to(device).eval()
    if device == "cuda":
        model = model.half()
    label_map = model.config.id2label  # e.g. {0: entailment, 1: neutral, 2: contradiction}
    # Resolve indices dynamically — fail loudly if the model uses a different layout.
    indices = _resolve_label_indices(label_map)
    return tok, model, device, indices


def _nli_batch(tokenizer, model, device, indices: tuple[int, int, int],
               premises: list[str], hypotheses: list[str]) -> list[dict]:
    """Compute NLI scores for a batch of (premise, hypothesis) pairs.

    `indices` is the (ent_idx, neu_idx, con_idx) tuple resolved at model load
    time from `model.config.id2label` — see audit fix C2.
    """
    import torch

    ent_idx, neu_idx, con_idx = indices
    enc = tokenizer(
        premises, hypotheses,
        padding=True, truncation=True, max_length=_MAX_LEN,
        return_tensors="pt",
    ).to(device)
    with torch.no_grad():
        logits = model(**enc).logits
    probs = torch.softmax(logits.float(), dim=-1).cpu().numpy()
    return [
        {
            "entailment":   float(p[ent_idx]),
            "neutral":      float(p[neu_idx]),
            "contradiction": float(p[con_idx]),
        }
        for p in probs
    ]


def compute_sf_for_case(
    explanation: str,
    chunks: list[str],
    tok, model, device, indices,
) -> dict:
    motiv = _extract_motivation(explanation)
    sents = _split_sentences(motiv)
    if not sents or not chunks:
        return {"skipped": True, "reason": "no sentences or no chunks"}

    # For each sentence, compute NLI vs each chunk → max entailment / contradiction
    per_sentence: list[dict] = []
    sf_entailments: list[float] = []
    sf_contradictions: list[float] = []

    for sent in sents:
        # Limit chunks per sentence (top 5 by chronological retrieval order)
        # to keep memory bounded
        used_chunks = chunks[:8]
        # Premise = chunk (truncated 600 chars), Hypothesis = sentence
        premises = [c[:600] for c in used_chunks]
        hypotheses = [sent] * len(used_chunks)
        # Run in micro-batches to respect _BATCH_SIZE
        scores = []
        for i in range(0, len(premises), _BATCH_SIZE):
            scores.extend(_nli_batch(
                tok, model, device, indices,
                premises[i:i + _BATCH_SIZE], hypotheses[i:i + _BATCH_SIZE],
            ))
        max_ent = max(s["entailment"] for s in scores)
        max_con = max(s["contradiction"] for s in scores)
        sf_entailments.append(max_ent)
        sf_contradictions.append(max_con)
        per_sentence.append({
            "sentence_preview": sent[:120] + ("..." if len(sent) > 120 else ""),
            "max_entailment": round(max_ent, 4),
            "max_contradiction": round(max_con, 4),
        })

    return {
        "skipped": False,
        "n_sentences": len(sents),
        "mean_max_entailment": round(mean(sf_entailments), 4),
        "mean_max_contradiction": round(mean(sf_contradictions), 4),
        "min_max_entailment": round(min(sf_entailments), 4),
        "n_high_contradiction": sum(1 for c in sf_contradictions if c > 0.5),
        "per_sentence": per_sentence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-report", type=Path, default=None)
    parser.add_argument("--explanations-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    parser.add_argument("--model-id", type=str, default=_MODEL_ID,
                        help="HuggingFace NLI model id (default: %(default)s)")
    parser.add_argument("--max-cases", type=int, default=0,
                        help="Limit cases for testing (0 = all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("sf_v2")

    pipeline_path = args.pipeline_report or (
        _PIPELINE_REPORT if _PIPELINE_REPORT.exists() else _PIPELINE_REPORT_FALLBACK
    )
    expl_dir = args.explanations_dir or (
        _EXPLANATIONS_DIR_V2 if _EXPLANATIONS_DIR_V2.exists() else _EXPLANATIONS_DIR_V1
    )

    if not pipeline_path.exists():
        log.error(f"Pipeline report missing: {pipeline_path}")
        return 1

    rep = json.loads(pipeline_path.read_text())
    cases = rep.get("case_results", [])
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    log.info(f"Loaded {len(cases)} cases from {pipeline_path}")

    log.info(f"Loading NLI model: {args.model_id}")
    tok, model, device, indices = _load_model(args.model_id)
    log.info(f"Model loaded on {device}, label_indices=(ent,neu,con)={indices}")

    per_case: list[dict] = []
    sf_values: list[float] = []
    contr_values: list[float] = []

    # Pre-init ChromaDB connection for chunk lookups (text is not in pipeline_report)
    import chromadb, os
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

    for c in cases:
        case_id = c.get("case_id")
        ex_path = expl_dir / f"{case_id}.txt"
        if not ex_path.exists():
            per_case.append({"case_id": case_id, "skipped": True, "reason": "explanation file missing"})
            continue
        explanation = ex_path.read_text()
        chunks_meta = c.get("retrieved_chunks_metadata", []) or []
        chunk_texts: list[str] = []
        # Case_id encodes nota: N97-001 → "97", N01-005 → "01"
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
                # Cross-nota fallback (chunk may be in any collection)
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

        result = compute_sf_for_case(explanation, chunk_texts, tok, model, device, indices)
        result["case_id"] = case_id
        per_case.append(result)
        if not result.get("skipped"):
            sf_values.append(result["mean_max_entailment"])
            contr_values.append(result["mean_max_contradiction"])
        if (len(per_case) % 10) == 0:
            log.info(f"  processed {len(per_case)}/{len(cases)}")

    if sf_values:
        agg = {
            "n_cases_evaluated": len(sf_values),
            "n_cases_skipped": len(cases) - len(sf_values),
            "sf_mean_entailment": round(mean(sf_values), 4),
            "sf_median_entailment": round(median(sf_values), 4),
            "sf_std_entailment": round(stdev(sf_values), 4) if len(sf_values) > 1 else 0.0,
            "sf_mean_contradiction": round(mean(contr_values), 4),
            "n_with_high_contradiction_total": sum(c.get("n_high_contradiction", 0) for c in per_case if not c.get("skipped")),
        }
    else:
        agg = {"n_cases_evaluated": 0, "n_cases_skipped": len(cases)}

    out = {
        "metric": "M3_semantic_faithfulness_v2",
        "description": "NLI entailment of LLM motivation sentences against retrieved chunks (Italian via mDeBERTa-XNLI, GPU fp16)",
        "model": args.model_id,
        "tautological": False,
        "limitations": [
            "Multilingual model — not fine-tuned on Italian normative text",
            "SF mean entailment is interpreted as a LOWER BOUND of actual faithfulness",
        ],
        "n_cases_total": len(cases),
        "aggregate": agg,
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(f"SF mean_entailment={agg.get('sf_mean_entailment','?')}, mean_contradiction={agg.get('sf_mean_contradiction','?')} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
