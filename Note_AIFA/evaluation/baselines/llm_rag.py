"""
LLM+RAG baseline (no rule engine, with retrieval).

Companion to `llm_only.py`. Adds retrieval of the top-k chunks from ChromaDB
for the relevant Nota and feeds them into the prompt — but does NOT inject the
rule engine decision. This isolates the contribution of the symbolic layer
(rule engine) from the retrieval layer (RAG).

Expected outcome: F1 between 0.244 (llm_only) and 1.000 (full hybrid). The
delta vs the hybrid quantifies the symbolic layer's specific contribution; the
delta vs llm_only quantifies the retrieval layer's contribution.

Usage (requires Ollama + ChromaDB populated):
    python -m evaluation.baselines.llm_rag

Outputs: evaluation/results/baseline_llm_rag.json with the same schema as
baseline_llm_only.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RESULTS_DIR = _ROOT / "evaluation" / "results"
_CHROMA_DIR = _ROOT / "rag_pipeline" / "chroma_db"

_DECISION_CLASSES = ["RIMBORSABILE", "NON_RIMBORSABILE", "NON_DETERMINABILE"]
_DEFAULT_K = 5


PROMPT_TEMPLATE = """\
Sei un assistente di farmacologia clinica specializzato nel sistema di rimborso
farmaceutico italiano (SSN/Note AIFA). Devi classificare se la prescrizione di
un farmaco è rimborsabile a carico del SSN secondo le Note AIFA.

Output: una singola parola fra RIMBORSABILE, NON_RIMBORSABILE, NON_DETERMINABILE.
Nessuna spiegazione, nessuna punteggiatura, nessuna formattazione markdown.

Dati paziente:
{patient_data}

Farmaco proposto: {drug_id}
Nota AIFA da applicare: {nota_id}

Estratti normativi recuperati (Top-{k}):
{chunks_block}

Risposta:"""


# Audit fix 2026-05-04 P0.1: V1/V2 collection mismatch.
# Use the centralized helper that honours CHROMA_COLLECTION_SUFFIX env var.
# Pre-fix this baseline retrieved from V1 chunks while production pipeline used
# V2 — the resulting macro_F1=0.32 was therefore measured on a different chunk
# corpus than the hybrid system it was being compared against.
sys.path.insert(0, str(_ROOT))
from evaluation.metrics._chroma_helpers import get_chroma_collection as _get_chroma_collection  # noqa: E402

# Reranker variant (--rerank): same cross-encoder and two-stage parameters as
# the production retriever (rag_pipeline/orchestrator/retriever.py): over-fetch
# _FETCH_K candidates by cosine, rerank with the Italian cross-encoder, keep k.
# This closes the RQ5 ablation gap: LLM+RAG+rerank, still without rule engine.
_RERANKER_MODEL = "nickprock/cross-encoder-italian-bert-stsb"
_FETCH_K = 15
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(_RERANKER_MODEL)
    return _reranker


def _retrieve_chunks(nota_id: str, query: str, k: int = _DEFAULT_K,
                     rerank: bool = False) -> list[str]:
    col = _get_chroma_collection(nota_id)
    if col is None:
        return []
    try:
        fetch_k = _FETCH_K if rerank else k
        res = col.query(query_texts=[query], n_results=fetch_k)
        docs = res.get("documents", [[]])[0] or []
        if not rerank or len(docs) <= k:
            return docs[:k]
        scores = _get_reranker().predict([(query, d) for d in docs])
        ranked = sorted(zip(scores, docs), key=lambda p: p[0], reverse=True)
        return [d for _, d in ranked[:k]]
    except Exception as exc:
        print(f"  WARN: chunk query failed for nota_{nota_id}: {exc}", file=sys.stderr)
        return []


def _build_query(case_input: dict) -> str:
    """Build a natural-language query from patient_data + drug + nota."""
    pd = case_input.get("patient_data", {})
    drug = case_input.get("drug_id", "")
    nota = case_input.get("nota_id", "")
    flags_true = [k.replace("_", " ") for k, v in pd.items() if v is True]
    flags_str = ", ".join(flags_true) if flags_true else "nessun flag clinico positivo"
    return f"Prescrizione di {drug} secondo Nota AIFA {nota}. Paziente con: {flags_str}."


def call_ollama(prompt: str) -> str | None:
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        response = client.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0, "num_ctx": 8192, "num_predict": 30},
        )
        return response["message"]["content"]
    except Exception as exc:
        print(f"  Ollama call failed: {exc}", file=sys.stderr)
        return None


def parse_decision(text: str | None) -> str:
    if not text:
        return "PARSE_FAIL"
    text_upper = text.upper()
    for label in ("NON_RIMBORSABILE", "NON RIMBORSABILE", "NON_DETERMINABILE",
                  "NON DETERMINABILE", "RIMBORSABILE"):
        if label in text_upper:
            return label.replace(" ", "_")
    return "PARSE_FAIL"


def evaluate_case(case: dict, k: int, rerank: bool = False) -> dict:
    inp = case["input"]
    patient_str = json.dumps(inp.get("patient_data", {}), indent=2, ensure_ascii=False)
    if inp.get("clinician_asserted"):
        patient_str += "\n\nClinician asserted:\n" + json.dumps(
            inp["clinician_asserted"], indent=2, ensure_ascii=False)

    # Retrieve chunks
    query = _build_query(inp)
    chunks = _retrieve_chunks(inp["nota_id"], query, k=k, rerank=rerank)
    if chunks:
        chunks_block = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    else:
        chunks_block = "(nessun chunk recuperato)"

    prompt = PROMPT_TEMPLATE.format(
        patient_data=patient_str,
        drug_id=inp["drug_id"],
        nota_id=inp["nota_id"],
        k=k,
        chunks_block=chunks_block,
    )
    response = call_ollama(prompt)
    pred = parse_decision(response)
    true = case["expected_rule_engine"].get("reimbursement_decision") or "ROUTED"
    return {
        "case_id": case["id"],
        "true": true,
        "pred": pred,
        "n_chunks_retrieved": len(chunks),
        "raw_response": response,
        "match": pred == true,
    }


def load_all_cases() -> list[dict]:
    cases = []
    for nota_id in ("01", "13", "66", "97"):
        path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cases.extend(data["cases"])
    return cases


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, default=_DEFAULT_K, help=f"top-k chunks to retrieve (default {_DEFAULT_K})")
    p.add_argument("--limit", type=int, default=None, help="limit cases (for smoke testing)")
    p.add_argument("--rerank", action="store_true",
                   help=f"two-stage retrieval: fetch {_FETCH_K} candidates, rerank with {_RERANKER_MODEL}, keep k")
    args = p.parse_args()

    cases = load_all_cases()
    if args.limit:
        cases = cases[:args.limit]
    variant = "LLM+RAG+rerank" if args.rerank else "LLM+RAG"
    print(f"{variant} baseline — {len(cases)} cases (k={args.k})")
    print("Calling Ollama llama3.1:8b for each case (slow: ~15-40 min)...\n")

    smoke = call_ollama("Rispondi con la singola parola: RIMBORSABILE")
    if smoke is None:
        print("\nERROR: cannot reach Ollama. Run 'ollama serve' and 'ollama pull llama3.1:8b'.")
        return 2

    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
        r = evaluate_case(case, k=args.k, rerank=args.rerank)
        results.append(r)
        status = "✓" if r["match"] else "✗"
        print(f"{status} pred={r['pred']} true={r['true']}")

    matrix: dict[str, Counter] = {c: Counter() for c in _DECISION_CLASSES + ["ROUTED", "PARSE_FAIL"]}
    for r in results:
        if r["true"] in matrix:
            matrix[r["true"]][r["pred"]] += 1

    n_correct = sum(1 for r in results if r["match"])
    accuracy = n_correct / len(results)

    per_class = {}
    for cls in _DECISION_CLASSES:
        tp = matrix[cls][cls]
        fn = sum(v for k, v in matrix[cls].items() if k != cls)
        fp = sum(matrix[other][cls] for other in matrix if other != cls)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[cls] = {
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "support": tp + fn,
        }
    macro_f1 = sum(p["f1"] for p in per_class.values()) / len(per_class)

    n_parse_fail = sum(1 for r in results if r["pred"] == "PARSE_FAIL")

    print(f"\n{'='*60}")
    print(f"{variant} baseline (Llama 3.1 8B + retrieval, no rule engine, k={args.k})")
    print(f"{'='*60}")
    print(f"Accuracy:        {accuracy*100:.2f}%")
    print(f"Macro F1:        {macro_f1:.4f}")
    print(f"Parse failures:  {n_parse_fail}/{len(results)}")
    for cls, m in per_class.items():
        print(f"  {cls:<22} P={m['precision']:.4f}  R={m['recall']:.4f}  F1={m['f1']:.4f}  (n={m['support']})")
    print(f"{'='*60}\n")

    out = {
        "baseline": "llm_rag_rerank" if args.rerank else "llm_rag",
        "model": "llama3.1:8b",
        "k_chunks": args.k,
        "reranker": _RERANKER_MODEL if args.rerank else None,
        "fetch_k": _FETCH_K if args.rerank else None,
        "n_cases": len(results),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "parse_failures": n_parse_fail,
        "per_class": per_class,
        "case_results": results,
    }
    out_name = "baseline_llm_rag_rerank.json" if args.rerank else "baseline_llm_rag.json"
    out_path = _RESULTS_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Report written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
