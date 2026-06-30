"""
NON_DETERMINABILE coverage analysis (Fase 5.6).

Directly addresses the brief from the relatore:
    "valutare la capacità del sistema di dichiarare esplicitamente
     l'insufficienza delle informazioni quando necessario"

Computes precision / recall / F1 for the NON_DETERMINABILE class against the
gold standard, and breaks down by Note. The headline number "M7 macro F1 = 1.0"
is class-balanced, so this script complements it with a per-class lens that
makes the missing-data behaviour explicit.

Inputs:
    evaluation/results/rule_engine_report.json (must already exist; produced
    by `make eval-rule-engine`)

Output:
    evaluation/results/non_determinable_analysis.json
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

log = logging.getLogger("non_determinable_analysis")
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

DEFAULT_INPUT = Path("evaluation/results/rule_engine_report.json")
DEFAULT_OUTPUT = Path("evaluation/results/non_determinable_analysis.json")
TARGET = "NON_DETERMINABILE"


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _decisions(r: dict) -> tuple[str, str]:
    """Return (gold, pred) for one entry from rule_engine_report.results.

    Schema (rule_engine_report.json v3.4):
        results[i].checks.reimbursement_decision.expected
        results[i].checks.reimbursement_decision.actual
    """
    checks = r.get("checks") or {}
    rd = checks.get("reimbursement_decision") or {}
    gold = rd.get("expected") or ""
    pred = rd.get("actual") or ""
    return gold, pred


def _missing_actual(r: dict) -> list[str]:
    checks = r.get("checks") or {}
    mf = checks.get("missing_fields_coverage") or {}
    actual = mf.get("actual") or []
    return list(actual) if isinstance(actual, list) else []


def _binary_metrics(results: list[dict]) -> dict[str, Any]:
    """One-vs-rest precision/recall/F1 for the NON_DETERMINABILE class."""
    tp = fp = fn = tn = 0
    for r in results:
        gold, pred = _decisions(r)
        if gold == TARGET and pred == TARGET:
            tp += 1
        elif gold != TARGET and pred == TARGET:
            fp += 1
        elif gold == TARGET and pred != TARGET:
            fn += 1
        else:
            tn += 1
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "support_positive": tp + fn,  # gold count
        "support_negative": fp + tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _per_nota_breakdown(results: list[dict]) -> dict[str, dict[str, Any]]:
    by_nota: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        # case_id format e.g. "N97-001" → nota = "97"
        cid = r.get("case_id") or r.get("id") or ""
        if cid.startswith("N") and "-" in cid:
            nota = cid.split("-", 1)[0].lstrip("N")
        else:
            nota = "unknown"
        by_nota[nota].append(r)
    return {nota: _binary_metrics(rs) for nota, rs in sorted(by_nota.items())}


def _missing_fields_audit(results: list[dict]) -> dict[str, Any]:
    """For TP cases (gold=ND, pred=ND), check that the report exposes which
    fields were missing — i.e. the system not only refuses but explains why."""
    tp_cases = [
        r for r in results
        if _decisions(r) == (TARGET, TARGET)
    ]
    declared = 0
    for r in tp_cases:
        if _missing_actual(r):
            declared += 1
    return {
        "n_tp": len(tp_cases),
        "n_with_declared_missing_fields": declared,
        "fraction_declared": round(_safe_div(declared, len(tp_cases)), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help="rule_engine_report.json path",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="output JSON path",
    )
    args = parser.parse_args()

    if not args.input.exists():
        log.error("Input not found: %s — run `make eval-rule-engine` first.", args.input)
        return 2

    report = json.loads(args.input.read_text(encoding="utf-8"))
    results = report.get("results", [])
    if not results:
        log.error("No 'results' key in %s", args.input)
        return 2

    overall = _binary_metrics(results)
    per_nota = _per_nota_breakdown(results)
    audit = _missing_fields_audit(results)

    out = {
        "target_class": TARGET,
        "n_cases_total": len(results),
        "overall": overall,
        "per_nota": per_nota,
        "missing_fields_declaration_audit": audit,
        "interpretation": (
            "Precision = of the cases the system FLAGS as NON_DETERMINABILE, "
            "what fraction were genuinely under-specified in the gold? "
            "Recall = of the gold-labelled NON_DETERMINABILE cases, what "
            "fraction did the system flag correctly? "
            "missing_fields_declaration_audit.fraction_declared = of TP "
            "(correctly flagged ND) cases, fraction that ALSO surface the "
            "specific missing fields — addresses the brief's 'declare "
            "insufficiency of information explicitly'."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info("Wrote %s", args.output)
    log.info(
        "ND P=%.3f R=%.3f F1=%.3f (n_pos=%d, n_neg=%d). "
        "Missing-fields declared on TP: %.1f%% (%d/%d).",
        overall["precision"], overall["recall"], overall["f1"],
        overall["support_positive"], overall["support_negative"],
        100 * audit["fraction_declared"],
        audit["n_with_declared_missing_fields"], audit["n_tp"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
