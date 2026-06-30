"""
Day 4 audit fix F5-7 ALTO: majority class baseline.

Applies the trivial baseline "always predict the most common class" (RIMBORSABILE)
and computes Macro F1 against the gold standard. This baseline answers the
question: "How much better is the rule engine than guessing?"

Expected result on this dataset (~55% RIMBORSABILE):
- Accuracy: ~55%
- Macro F1: low (because non-RIMB classes get F1=0)

Usage:
    python -m evaluation.baselines.majority_class
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


_DECISION_CLASSES = ["RIMBORSABILE", "NON_RIMBORSABILE", "NON_DETERMINABILE", "ROUTED"]


def load_all_cases() -> list[dict]:
    cases: list[dict] = []
    for nota_id in ("01", "13", "66", "97"):
        path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cases.extend(data["cases"])
    return cases


def predict_majority(cases: list[dict]) -> list[tuple[str, str, str]]:
    """For every case, predict the majority class. Returns [(case_id, true_label, pred_label)]."""
    # Determine majority class from training data (here = the gold standard itself)
    label_counts = Counter()
    for c in cases:
        true = c["expected_rule_engine"].get("reimbursement_decision") or "ROUTED"
        label_counts[true] += 1
    majority = label_counts.most_common(1)[0][0]
    print(f"Majority class identified: {majority} (n={label_counts[majority]}/{sum(label_counts.values())})")
    print(f"Class distribution: {dict(label_counts)}")

    predictions = []
    for c in cases:
        true = c["expected_rule_engine"].get("reimbursement_decision") or "ROUTED"
        predictions.append((c["id"], true, majority))
    return predictions


def compute_metrics(predictions: list[tuple[str, str, str]]) -> dict:
    """Compute confusion matrix, per-class F1, macro F1."""
    matrix = {c: {c2: 0 for c2 in _DECISION_CLASSES} for c in _DECISION_CLASSES}
    for _, true, pred in predictions:
        if true in matrix and pred in matrix[true]:
            matrix[true][pred] += 1

    per_class: dict[str, dict] = {}
    for c in _DECISION_CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[o][c] for o in _DECISION_CLASSES if o != c)
        fn = sum(matrix[c][o] for o in _DECISION_CLASSES if o != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[c] = {
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "support": tp + fn,
        }
    core = [c for c in _DECISION_CLASSES if c != "ROUTED"]
    macro_f1 = sum(per_class[c]["f1"] for c in core) / len(core)

    accuracy = sum(1 for _, t, p in predictions if t == p) / len(predictions)

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "total_cases": len(predictions),
    }


def main() -> int:
    cases = load_all_cases()
    print(f"Loaded {len(cases)} gold standard cases.\n")

    predictions = predict_majority(cases)
    metrics = compute_metrics(predictions)

    print(f"\n{'='*60}")
    print("Majority Class Baseline (always predict RIMBORSABILE)")
    print(f"{'='*60}")
    print(f"Accuracy:  {metrics['accuracy']*100:.2f}%")
    print(f"Macro F1:  {metrics['macro_f1']:.4f}")
    print(f"\nPer-class:")
    for cls, m in metrics["per_class"].items():
        print(f"  {cls:<22} P={m['precision']:.4f}  R={m['recall']:.4f}  F1={m['f1']:.4f}  (support={m['support']})")
    print(f"{'='*60}\n")

    out = {
        "baseline": "majority_class",
        "majority_label": predictions[0][2],
        "metrics": metrics,
    }
    out_path = _RESULTS_DIR / "baseline_majority_class.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Report written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
