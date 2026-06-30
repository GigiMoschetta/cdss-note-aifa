"""
Day 4 audit fix F5-6 ALTO: bootstrap confidence intervals for evaluation metrics.

Reads pipeline_report.json or rule_engine_report.json and computes 95% CI for
all reported rates. Uses **percentile bootstrap** (numpy-based, n_resamples=5000,
seed=42), NOT BCa. The historical docstring incorrectly stated "BCa method";
the implementation has always been percentile bootstrap (no jackknife / no
bias-correction / no acceleration). For proportions, prefer
`evaluation.metrics.bootstrap_wilson` (Wilson score interval, exact closed-form)
over this percentile bootstrap.

Usage:
    python -m evaluation.metrics.bootstrap_ci \
        --input evaluation/results/rule_engine_report.json \
        --metric pass_rate \
        --output evaluation/results/rule_engine_ci.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def bootstrap_ci_proportion(
    successes: int,
    total: int,
    n_resamples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute percentile bootstrap CI for a proportion (success/total).

    Returns (point_estimate, ci_low, ci_high).

    Uses **percentile bootstrap** (resample with replacement n_resamples times,
    take 2.5%/97.5% quantiles of the resampled means). NOT BCa — there is no
    jackknife bias-correction and no acceleration term. For extreme proportions
    (p≈0 or p≈1) the percentile CI may collapse to [p, p]; in that regime
    Wilson score interval (`bootstrap_wilson`) is more reliable.
    """
    if total == 0:
        return (0.0, 0.0, 0.0)

    point = successes / total

    # Bootstrap by resampling the binary outcome vector
    rng = np.random.default_rng(seed)
    data = np.concatenate([np.ones(successes), np.zeros(total - successes)])
    bootstrap_means = []
    for _ in range(n_resamples):
        sample = rng.choice(data, size=total, replace=True)
        bootstrap_means.append(sample.mean())
    bootstrap_means = np.array(bootstrap_means)

    alpha = (1.0 - confidence_level) / 2
    ci_low = float(np.percentile(bootstrap_means, alpha * 100))
    ci_high = float(np.percentile(bootstrap_means, (1.0 - alpha) * 100))

    return (point, ci_low, ci_high)


def compute_all_cis(report: dict) -> dict:
    """Compute CIs for all relevant metrics in a report."""
    out: dict[str, dict] = {}

    # Track 1 — rule_engine_report.json structure
    if "pass_rate" in report and "passed" in report and "total_cases" in report:
        passed = int(report["passed"])
        total = int(report["total_cases"])
        p, lo, hi = bootstrap_ci_proportion(passed, total)
        out["pass_rate"] = {
            "point": p,
            "ci_95_low": lo,
            "ci_95_high": hi,
            "n_successes": passed,
            "n_total": total,
        }

    # Per-class metrics — F1 doesn't bootstrap easily as proportion, but
    # we can bootstrap precision and recall separately
    if "per_class_metrics" in report:
        out["per_class_ci"] = {}
        for cls, metrics in report["per_class_metrics"].items():
            if cls == "macro_avg":
                continue
            # Need TP, FP, FN counts — derive from matrix if available
            cm = report.get("confusion_matrix", {})
            if cls in cm:
                row = cm[cls]
                tp = int(row.get(cls, 0))
                fn = sum(int(row.get(o, 0)) for o in row if o != cls)
                fp = sum(int(cm.get(o, {}).get(cls, 0)) for o in cm if o != cls)
                out["per_class_ci"][cls] = {
                    "tp": tp, "fp": fp, "fn": fn,
                    "support": tp + fn,
                }
                if tp + fp > 0:
                    p, lo, hi = bootstrap_ci_proportion(tp, tp + fp)
                    out["per_class_ci"][cls]["precision"] = {"point": p, "ci_95_low": lo, "ci_95_high": hi}
                if tp + fn > 0:
                    p, lo, hi = bootstrap_ci_proportion(tp, tp + fn)
                    out["per_class_ci"][cls]["recall"] = {"point": p, "ci_95_low": lo, "ci_95_high": hi}

    # Track 3 — pipeline_report.json structure
    if "aggregate_metrics" in report:
        agg = report["aggregate_metrics"]
        n = int(agg.get("total_cases", 0))
        if n > 0:
            for metric_name in (
                "overall_pass_rate", "decision_consistency_rate",
                "citation_coverage_rate", "hallucination_rate",
                "section_completeness_rate", "justification_snippet_coverage_rate",
            ):
                if metric_name in agg:
                    rate = float(agg[metric_name])
                    successes = round(rate * n)
                    p, lo, hi = bootstrap_ci_proportion(successes, n)
                    out[metric_name] = {
                        "point": p, "ci_95_low": lo, "ci_95_high": hi,
                        "n_successes": successes, "n_total": n,
                    }

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--input", required=True, help="Path to report JSON")
    parser.add_argument("--output", help="Path to write CI JSON (default: stdout)")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {in_path} not found", file=sys.stderr)
        return 1

    with open(in_path, encoding="utf-8") as f:
        report = json.load(f)

    cis = compute_all_cis(report)
    output = {
        "source_report": str(in_path),
        "method": "bootstrap normal percentile, n_resamples=5000, seed=42",
        "confidence_level": 0.95,
        "metrics_with_ci": cis,
    }

    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"CI report written to: {args.output}")
    else:
        print(text)

    # Print human-readable summary
    print("\nSummary (point [95% CI]):")
    for metric, info in cis.items():
        if metric == "per_class_ci":
            continue
        if isinstance(info, dict) and "point" in info:
            p = info["point"]
            lo = info["ci_95_low"]
            hi = info["ci_95_high"]
            print(f"  {metric:<35} {p*100:6.2f}% [{lo*100:6.2f}%, {hi*100:6.2f}%]  (n={info['n_total']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
