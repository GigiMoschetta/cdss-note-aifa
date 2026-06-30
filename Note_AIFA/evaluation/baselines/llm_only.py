"""
Day 4 audit fix F5-7 ALTO: LLM-only baseline (no rule engine, no retrieval).

Tests the hypothesis "the rule engine adds value over an LLM-only system" by
running each gold standard case through Llama 3.1 8B with a minimal prompt that:
- Receives only the patient_data (as JSON), drug_id, and nota_id
- Does NOT receive retrieved chunks (see llm_rag baseline for that ablation)
- Does NOT receive any rule engine decision injection
- Must classify as RIMBORSABILE / NON_RIMBORSABILE / NON_DETERMINABILE

Observed in the 2026-04-28 overnight run: the model collapsed to majority class
(always RIMBORSABILE), yielding macro F1 = 0.244 — i.e. equal to the trivial
majority baseline. This quantifies the contribution of the symbolic+RAG layers
combined: on this benchmark, an 8B-parameter LLM with clinical patient JSON
alone has zero discriminative ability for AIFA reimbursement classification.

Usage (requires Ollama running with llama3.1:8b):
    python -m evaluation.baselines.llm_only

The script is gracefully degrading: if Ollama is unreachable, prints
instructions and exits 2 (allows Day 4 to complete with majority baseline only).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RESULTS_DIR = _ROOT / "evaluation" / "results"

_DECISION_CLASSES = ["RIMBORSABILE", "NON_RIMBORSABILE", "NON_DETERMINABILE"]


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

Risposta:"""


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


def call_ollama(prompt: str) -> str | None:
    """Call Ollama llama3.1:8b. Returns None on connection failure."""
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
    """Parse first decision-token from LLM output."""
    if not text:
        return "PARSE_FAIL"
    text_upper = text.upper()
    for label in ("NON_RIMBORSABILE", "NON RIMBORSABILE", "NON_DETERMINABILE",
                  "NON DETERMINABILE", "RIMBORSABILE"):
        if label in text_upper:
            return label.replace(" ", "_")
    return "PARSE_FAIL"


def evaluate_case(case: dict) -> dict:
    inp = case["input"]
    patient_str = json.dumps(inp.get("patient_data", {}), indent=2, ensure_ascii=False)
    if inp.get("clinician_asserted"):
        patient_str += "\n\nClinician asserted:\n" + json.dumps(
            inp["clinician_asserted"], indent=2, ensure_ascii=False)
    prompt = PROMPT_TEMPLATE.format(
        patient_data=patient_str,
        drug_id=inp["drug_id"],
        nota_id=inp["nota_id"],
    )
    response = call_ollama(prompt)
    pred = parse_decision(response)
    true = case["expected_rule_engine"].get("reimbursement_decision") or "ROUTED"
    return {
        "case_id": case["id"],
        "true": true,
        "pred": pred,
        "raw_response": response,
        "match": pred == true,
    }


def main() -> int:
    cases = load_all_cases()
    print(f"LLM-only baseline — {len(cases)} cases")
    print("Calling Ollama llama3.1:8b for each case (slow: ~10-30 min)...\n")

    # Quick smoke: try one call
    smoke = call_ollama("Rispondi con la singola parola: RIMBORSABILE")
    if smoke is None:
        print("\nERROR: cannot reach Ollama. Run 'ollama serve' and 'ollama pull llama3.1:8b'.")
        print("(LLM-only baseline is optional — majority class baseline works without LLM.)")
        return 2

    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
        r = evaluate_case(case)
        results.append(r)
        status = "✓" if r["match"] else "✗"
        print(f"{status} pred={r['pred']} true={r['true']}")

    # Aggregate
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
    print("LLM-only baseline (Llama 3.1 8B, no rule engine, no decision injection)")
    print(f"{'='*60}")
    print(f"Accuracy:        {accuracy*100:.2f}%")
    print(f"Macro F1:        {macro_f1:.4f}")
    print(f"Parse failures:  {n_parse_fail}/{len(results)}")
    for cls, m in per_class.items():
        print(f"  {cls:<22} P={m['precision']:.4f}  R={m['recall']:.4f}  F1={m['f1']:.4f}  (n={m['support']})")
    print(f"{'='*60}\n")

    out = {
        "baseline": "llm_only",
        "model": "llama3.1:8b",
        "n_cases": len(results),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "parse_failures": n_parse_fail,
        "per_class": per_class,
        "case_results": results,
    }
    out_path = _RESULTS_DIR / "baseline_llm_only.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Report written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
