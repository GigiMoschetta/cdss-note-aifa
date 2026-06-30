"""
Day 5 audit fix F2-6 / F5-11: idempotency test.

Run a sample of gold standard cases through the rule engine multiple times
and verify the output is bit-identical (excluding non-deterministic timestamps).

The rule engine is purely functional → expected: 100% identical output.
This test quantitatively validates the determinism claim.

Usage:
    python -m evaluation.robustness.idempotency
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RESULTS_DIR = _ROOT / "evaluation" / "results"

sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "aifa_rule_engine"))

from aifa_rule_engine.engine.rule_loader import load_rules  # noqa: E402
from aifa_rule_engine.engine.evaluator import evaluate  # noqa: E402


def _strip_nondeterministic(result_dict: dict) -> dict:
    """Remove fields that are expected to vary across runs (timestamps)."""
    out = dict(result_dict)
    out.pop("evaluation_timestamp", None)
    return out


def main() -> int:
    rule_index = load_rules(_ROOT / "aifa_rule_engine" / "rules")
    print(f"Loaded {len(rule_index.rules)} rules")

    # Sample 20 cases across all 4 Notes
    cases_to_test = []
    for nota_id in ("01", "13", "66", "97"):
        path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cases_to_test.extend(data["cases"][:5])  # first 5 from each nota

    print(f"Testing idempotency on {len(cases_to_test)} cases × 3 runs each\n")

    n_pass = 0
    n_fail = 0
    failures = []

    for case in cases_to_test:
        inp = case["input"]
        results = []
        for i in range(3):
            r = evaluate(
                nota_id=inp["nota_id"],
                drug_id=inp["drug_id"],
                patient_data=inp.get("patient_data", {}),
                clinician_asserted=inp.get("clinician_asserted", {}),
                rule_index=rule_index,
            )
            results.append(_strip_nondeterministic(r.model_dump(mode="json")))

        # Compare runs 1 vs 2 vs 3
        all_equal = all(r == results[0] for r in results)
        if all_equal:
            n_pass += 1
            print(f"  ✓ {case['id']:<10} 3 runs identical")
        else:
            n_fail += 1
            print(f"  ✗ {case['id']:<10} runs DIFFER")
            failures.append({"case_id": case["id"], "runs": results})

    print(f"\n{'='*60}")
    print(f"Idempotency: {n_pass}/{len(cases_to_test)} cases ({n_pass/len(cases_to_test)*100:.1f}%) reproducibly identical")
    print(f"{'='*60}")

    out = {
        "test": "rule_engine_idempotency",
        "n_cases": len(cases_to_test),
        "n_runs_per_case": 3,
        "n_pass": n_pass,
        "n_fail": n_fail,
        "pass_rate": round(n_pass / len(cases_to_test), 4),
        "failures": failures,
    }
    out_path = _RESULTS_DIR / "robustness_idempotency.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Report written to: {out_path}")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
