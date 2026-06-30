"""
Phase 4 — Generate Expected Rule Engine Outputs
=================================================

Runs the Rule Engine on every gold standard case and writes the full
EvaluationResult JSON to  evaluation/gold_standard/<nota_id>_expected_outputs.json

This file is later used by evaluate_rule_engine.py for regression testing
and by evaluate_pipeline.py to validate orchestrator outputs against the
authoritative deterministic baseline.

Usage:
    # From the project root (Note_AIFA/)
    python -m evaluation.scripts.generate_expected_outputs

    # Or with explicit rules dir:
    AIFA_RULES_DIR=aifa_rule_engine/rules python -m evaluation.scripts.generate_expected_outputs
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "aifa_rule_engine"))

from aifa_rule_engine.engine.rule_loader import load_rules
from aifa_rule_engine.engine.evaluator import evaluate

_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RULES_DIR = Path(os.getenv("AIFA_RULES_DIR", str(_ROOT / "aifa_rule_engine" / "rules")))


def _load_gold_standard(nota_id: str) -> dict:
    path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_case(case: dict, rule_index) -> dict:
    """Run a single gold standard case through the Rule Engine."""
    inp = case["input"]
    # normalise null -> None (already handled by json.load)
    result = evaluate(
        nota_id=inp["nota_id"],
        drug_id=inp["drug_id"],
        patient_data=inp.get("patient_data", {}),
        clinician_asserted=inp.get("clinician_asserted", {}),
        rule_index=rule_index,
    )
    return result.model_dump(mode="json")


def generate_all() -> None:
    print(f"Loading rules from: {_RULES_DIR}")
    rule_index = load_rules(_RULES_DIR)
    print(f"Rules loaded: {len(rule_index.rules)} rules\n")

    nota_ids = ["97", "01", "13", "66"]
    total_cases = 0
    total_errors = 0

    for nota_id in nota_ids:
        gold_path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        if not gold_path.exists():
            print(f"[SKIP] nota_{nota_id}_cases.json not found")
            continue

        gold = _load_gold_standard(nota_id)
        cases = gold["cases"]
        output_records = []
        errors = []

        print(f"Processing Nota {nota_id} ({len(cases)} cases)...")
        for case in cases:
            case_id = case["id"]
            try:
                result_dict = _run_case(case, rule_index)
                output_records.append({
                    "case_id": case_id,
                    "description": case["description"],
                    "input": case["input"],
                    "actual_result": result_dict,
                })
                print(f"  ✓ {case_id}: {result_dict.get('reimbursement_decision') or result_dict.get('decision_status')}")
            except Exception as exc:
                errors.append({"case_id": case_id, "error": str(exc)})
                print(f"  ✗ {case_id}: ERROR — {exc}", file=sys.stderr)
                total_errors += 1

        output_path = _GOLD_DIR / f"nota_{nota_id}_expected_outputs.json"
        output = {
            "schema_version": "1.0",
            "nota_id": nota_id,
            "generated": str(date.today()),
            "engine_version": "3.4.0",
            "total_cases": len(output_records),
            "errors": errors,
            "outputs": output_records,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  → Saved {len(output_records)} outputs to {output_path.name}")
        if errors:
            print(f"  ⚠ {len(errors)} errors encountered")
        total_cases += len(cases)
        print()

    print(f"Done. {total_cases} total cases processed, {total_errors} errors.")


if __name__ == "__main__":
    generate_all()
