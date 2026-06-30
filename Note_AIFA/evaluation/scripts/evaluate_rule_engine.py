"""
Phase 4 — Rule Engine Regression Evaluation
============================================

Runs the Rule Engine on every gold standard case and checks the output
against the expected values declared in the JSON files.

Exit code: 0 if all cases pass, 1 if any case fails.

Usage:
    python -m evaluation.scripts.evaluate_rule_engine
    python -m evaluation.scripts.evaluate_rule_engine --nota 97
    python -m evaluation.scripts.evaluate_rule_engine --fail-fast
    python -m evaluation.scripts.evaluate_rule_engine --json-report evaluation/results/rule_engine_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "aifa_rule_engine"))

from aifa_rule_engine import ENGINE_VERSION
from aifa_rule_engine.engine.rule_loader import load_rules
from aifa_rule_engine.engine.evaluator import evaluate

_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RESULTS_DIR = _ROOT / "evaluation" / "results"
_RULES_DIR = Path(os.getenv("AIFA_RULES_DIR", str(_ROOT / "aifa_rule_engine" / "rules")))


# ── Result data classes (plain dicts for JSON serialization) ──────────────────

def _check_case(case: dict, rule_index) -> dict:
    """
    Run a single gold standard case and compare against expected.
    Returns a result dict with pass/fail and per-check details.
    """
    inp = case["input"]
    expected = case["expected_rule_engine"]
    result = evaluate(
        nota_id=inp["nota_id"],
        drug_id=inp["drug_id"],
        patient_data=inp.get("patient_data", {}),
        clinician_asserted=inp.get("clinician_asserted", {}),
        rule_index=rule_index,
    )

    checks: dict[str, dict] = {}

    # ── Check 1: reimbursement_decision ───────────────────────────────────────
    exp_decision = expected.get("reimbursement_decision")
    act_decision = result.reimbursement_decision
    checks["reimbursement_decision"] = {
        "expected": exp_decision,
        "actual": act_decision,
        "pass": exp_decision == act_decision,
    }

    # ── Check 2: decision_status ──────────────────────────────────────────────
    exp_status = expected.get("decision_status")
    act_status = result.decision_status
    checks["decision_status"] = {
        "expected": exp_status,
        "actual": act_status,
        "pass": (exp_status is None) or (exp_status == act_status),
    }

    # ── Check 3: route_to (only if ROUTED expected) ────────────────────────────
    exp_route = expected.get("route_to")
    if exp_route is not None:
        act_route = result.route_to
        checks["route_to"] = {
            "expected": exp_route,
            "actual": act_route,
            "pass": exp_route == act_route,
        }

    # ── Check 4: missing_fields_coverage ──────────────────────────────────────
    exp_missing = set(expected.get("missing_fields_coverage", []))
    act_missing = set(result.missing_fields_coverage)
    checks["missing_fields_coverage"] = {
        "expected": sorted(exp_missing),
        "actual": sorted(act_missing),
        "pass": exp_missing == act_missing,
    }

    # ── Check 5: expected blocking rule IDs must match exactly ────────────────
    exp_blocking = set(expected.get("expected_blocking_rule_ids", []))
    act_blocking = {br.rule_id for br in result.rag_payload.blocking_rules}
    checks["blocking_rule_ids"] = {
        "expected": sorted(exp_blocking),
        "actual": sorted(act_blocking),
        "pass": exp_blocking == act_blocking,
    }

    # ── Check 6: expected clinical flag IDs must match exactly ────────────────
    exp_flags = set(expected.get("expected_clinical_flag_rule_ids", []))
    act_flags = {cf.rule_id for cf in result.clinical_flags}
    checks["clinical_flag_ids"] = {
        "expected": sorted(exp_flags),
        "actual": sorted(act_flags),
        "pass": exp_flags == act_flags,
    }

    overall_pass = all(c["pass"] for c in checks.values())
    return {
        "case_id": case["id"],
        "description": case["description"],
        "category": case.get("category", ""),
        "pass": overall_pass,
        "checks": checks,
    }


def _print_case_result(result: dict, verbose: bool = False) -> None:
    status = "✓ PASS" if result["pass"] else "✗ FAIL"
    print(f"  {status}  {result['case_id']}: {result['description'][:70]}")
    if not result["pass"] or verbose:
        for check_name, check in result["checks"].items():
            if not check["pass"]:
                exp = check.get("expected") or check.get("expected_subset")
                act = check.get("actual")
                print(f"         [{check_name}] expected={exp!r}  actual={act!r}")


_DECISION_CLASSES = ["RIMBORSABILE", "NON_RIMBORSABILE", "NON_DETERMINABILE", "ROUTED"]


def _get_decision_label(result: dict) -> tuple[str, str]:
    """Extract (expected, actual) label; maps None → 'ROUTED'."""
    rd = result["checks"].get("reimbursement_decision", {})
    exp = rd.get("expected") or "ROUTED"
    act = rd.get("actual") or "ROUTED"
    return exp, act


def compute_confusion_matrix(results: list[dict]) -> dict[str, dict[str, int]]:
    matrix = {c: {c2: 0 for c2 in _DECISION_CLASSES} for c in _DECISION_CLASSES}
    for r in results:
        true_lbl, pred_lbl = _get_decision_label(r)
        if true_lbl in matrix and pred_lbl in matrix[true_lbl]:
            matrix[true_lbl][pred_lbl] += 1
    return matrix


def compute_per_class_metrics(matrix: dict) -> dict[str, dict[str, float]]:
    out = {}
    for c in _DECISION_CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[o][c] for o in _DECISION_CLASSES if o != c)
        fn = sum(matrix[c][o] for o in _DECISION_CLASSES if o != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec  = tp / (tp + fn) if tp + fn else 0.0
        f1   = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[c] = {"precision": round(prec, 4), "recall": round(rec, 4),
                  "f1": round(f1, 4), "support": tp + fn}
    core = [c for c in _DECISION_CLASSES if c != "ROUTED"]
    out["macro_avg"] = {"f1": round(sum(out[c]["f1"] for c in core) / len(core), 4)}
    return out


def run_evaluation(nota_ids: list[str], fail_fast: bool, verbose: bool) -> dict:
    print(f"Loading rules from: {_RULES_DIR}")
    rule_index = load_rules(_RULES_DIR)
    print(f"Rules loaded: {len(rule_index.rules)} rules\n")

    all_results: list[dict] = []
    total_pass = 0
    total_fail = 0

    for nota_id in nota_ids:
        gold_path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        if not gold_path.exists():
            print(f"[SKIP] Nota {nota_id}: gold standard file not found\n")
            continue

        with open(gold_path, encoding="utf-8") as f:
            gold = json.load(f)

        cases = gold["cases"]
        print(f"Nota {nota_id} ({len(cases)} cases):")

        for case in cases:
            try:
                res = _check_case(case, rule_index)
            except Exception as exc:
                res = {
                    "case_id": case["id"],
                    "description": case["description"],
                    "category": case.get("category", ""),
                    "pass": False,
                    "error": str(exc),
                    "checks": {},
                }
                print(f"  ✗ ERROR  {case['id']}: {exc}", file=sys.stderr)
                total_fail += 1
                if fail_fast:
                    raise

            all_results.append(res)
            _print_case_result(res, verbose=verbose)

            if res["pass"]:
                total_pass += 1
            else:
                total_fail += 1
                if fail_fast:
                    print("\n[--fail-fast] Stopping after first failure.")
                    break

        print()
        if fail_fast and total_fail > 0:
            break

    matrix = compute_confusion_matrix(all_results)
    per_class = compute_per_class_metrics(matrix)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "rules_dir": str(_RULES_DIR),
        "total_cases": total_pass + total_fail,
        "passed": total_pass,
        "failed": total_fail,
        "pass_rate": round(total_pass / max(1, total_pass + total_fail), 4),
        "confusion_matrix": matrix,
        "per_class_metrics": per_class,
        "results": all_results,
    }

    print("=" * 70)
    print(f"SUMMARY: {total_pass}/{total_pass + total_fail} cases passed "
          f"({report['pass_rate'] * 100:.1f}%)")
    if total_fail > 0:
        print(f"         {total_fail} FAILED — see details above")
    print("=" * 70)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regression test the Rule Engine against gold standard cases"
    )
    parser.add_argument(
        "--nota", nargs="+", default=["97", "01", "13", "66"],
        help="Which nota(e) to test (default: all)"
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help="Stop after first failure"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show passing check details"
    )
    parser.add_argument(
        "--json-report", metavar="PATH",
        help="Write JSON report to this path"
    )
    args = parser.parse_args()

    report = run_evaluation(
        nota_ids=args.nota,
        fail_fast=args.fail_fast,
        verbose=args.verbose,
    )

    print("\nTrack 1 — Per-class Metrics")
    print(f"{'Class':<22} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 57)
    for cls in _DECISION_CLASSES:
        m = report["per_class_metrics"][cls]
        print(f"{cls:<22} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>10}")
    print(f"\nMacro F1: {report['per_class_metrics']['macro_avg']['f1']:.4f}")

    if args.json_report:
        out_path = Path(args.json_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nJSON report written to: {out_path}")

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
