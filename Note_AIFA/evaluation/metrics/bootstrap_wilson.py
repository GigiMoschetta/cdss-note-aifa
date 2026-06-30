"""
bootstrap_wilson.py — Wilson score interval for proportion-like metrics
========================================================================

Replaces the normal-percentile bootstrap CI for metrics where p̂ ∈ [0, 1]
and especially handles the degenerate case p̂ = 1.0 where normal-percentile
collapses to [1.0, 1.0].

Wilson score interval gives a non-degenerate CI even at the boundaries.

Usage as library:
    from evaluation.metrics.bootstrap_wilson import wilson_ci
    low, high = wilson_ci(n_successes=122, n_total=122, confidence=0.95)

Usage as CLI:
    python -m evaluation.metrics.bootstrap_wilson --report rule_engine_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path


def wilson_ci(n_successes: int, n_total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval. Non-degenerate at p̂=0 and p̂=1.

    Returns (lower, upper).
    """
    if n_total == 0:
        return (0.0, 1.0)
    # z-score for two-sided CI
    alpha = 1 - confidence
    # Approximate z using inverse error function
    z = math.sqrt(2.0) * _erfcinv(alpha)

    p_hat = n_successes / n_total
    denom = 1 + z * z / n_total
    centre = p_hat + z * z / (2 * n_total)
    halfw = z * math.sqrt(p_hat * (1 - p_hat) / n_total + z * z / (4 * n_total ** 2))
    lower = (centre - halfw) / denom
    upper = (centre + halfw) / denom
    return (max(0.0, lower), min(1.0, upper))


def _erfcinv(y: float) -> float:
    """Approximate inverse complementary error function."""
    # https://en.wikipedia.org/wiki/Error_function#Inverse_functions
    # erfc(x) = 1 - erf(x). For 0 < y < 2.
    # We need x such that erfc(x) = y. erf^{-1}(1 - y) = erfcinv(y).
    return _erfinv(1.0 - y)


def _erfinv(x: float) -> float:
    """Approximate inverse error function (Acklam)."""
    a = 0.147
    ln = math.log(1 - x * x) if x * x < 1 else -1e9
    first = 2 / (math.pi * a) + ln / 2
    return math.copysign(math.sqrt(math.sqrt(first ** 2 - ln / a) - first), x)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path,
                        default=Path("evaluation/results/rule_engine_report.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("evaluation/results/wilson_ci_rule_engine.json"))
    parser.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("wilson")

    rep = json.loads(args.report.read_text())
    n_total = rep.get("total_cases", 0)
    n_pass = rep.get("passed", 0)
    pass_rate = rep.get("pass_rate", 0.0)
    low, high = wilson_ci(n_pass, n_total, args.confidence)

    # Per-class
    per_class_ci: dict = {}
    cm = rep.get("confusion_matrix", {})
    for cls, row in cm.items():
        if not isinstance(row, dict):
            continue
        tp = row.get(cls, 0)
        fn = sum(v for k, v in row.items() if k != cls)
        fp = sum(other.get(cls, 0) for k, other in cm.items() if k != cls and isinstance(other, dict))
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec_low, rec_high = wilson_ci(tp, tp + fn, args.confidence)
        prec_low, prec_high = wilson_ci(tp, tp + fp, args.confidence)
        per_class_ci[cls] = {
            "support": tp + fn,
            "recall": round(recall, 4),
            "recall_ci": [round(rec_low, 4), round(rec_high, 4)],
            "precision": round(precision, 4),
            "precision_ci": [round(prec_low, 4), round(prec_high, 4)],
        }

    out = {
        "metric": "wilson_ci_rule_engine",
        "method": "wilson_score",
        "confidence_level": args.confidence,
        "n_total": n_total,
        "n_pass": n_pass,
        "pass_rate": round(pass_rate, 4),
        "pass_rate_ci": [round(low, 4), round(high, 4)],
        "note": (
            "Wilson score interval is non-degenerate at p̂=1.0 (vs normal-percentile "
            "which collapses to [1.0, 1.0]). For n=122 with p̂=1.0, Wilson 95% CI is "
            "approximately [0.969, 1.000]."
        ),
        "per_class": per_class_ci,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(f"pass_rate={pass_rate} → Wilson 95% CI = [{low:.4f}, {high:.4f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
