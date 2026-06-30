"""
ALES sensitivity analysis (Fase 5.1).

The composite score
    ALES = α·DecisionScore + β·EvidenceSupport + γ·ContextualUtility + δ·AnswerQuality
hard-codes (α, β, γ, δ) = (0.40, 0.30, 0.20, 0.10). The thesis defends this
choice on safety-priorization grounds, but the audit asked for an explicit
sensitivity table — how stable is the headline ALES under reasonable weight
perturbations?

This script reads `composite_scores.json` and, for each component, perturbs
its weight by ±0.10 (renormalizing the others proportionally), recomputes
the per-case ALES, and reports mean/median/std plus delta vs the default
weights. The output is a small JSON + a markdown table ready to drop into
the manuscript.

Inputs:
    evaluation/results/composite_scores.json
Output:
    evaluation/results/ales_sensitivity.json
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

log = logging.getLogger("ales_sensitivity")
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")


COMPONENT_KEYS = ("DecisionScore", "EvidenceSupport", "ContextualUtility", "AnswerQuality")
DEFAULT_WEIGHTS = (0.40, 0.30, 0.20, 0.10)
PERTURBATIONS = (-0.10, -0.05, 0.0, 0.05, 0.10)


def _ales_for_case(case: dict, weights: tuple[float, float, float, float]) -> float | None:
    """Recompute ALES for a single case with the supplied weights, ignoring
    components missing on that case (rescale by available weight, mirroring
    composite_scores.py logic so the sensitivity is comparable)."""
    pieces: list[tuple[float, float]] = []
    for key, w in zip(COMPONENT_KEYS, weights):
        v = case.get(key)
        if v is not None:
            pieces.append((v, w))
    if not pieces:
        return None
    total_w = sum(w for _, w in pieces)
    if total_w == 0:
        return None
    return sum(v * w / total_w for v, w in pieces)


def _summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "std": round(stdev(values) if len(values) > 1 else 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _renormalize(weights: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Clip negatives to 0 then renormalize to sum=1 — keeps the perturbed
    weight system on the simplex even when a single weight is pushed below 0."""
    clipped = tuple(max(0.0, w) for w in weights)
    total = sum(clipped)
    if total == 0:
        return DEFAULT_WEIGHTS
    return tuple(w / total for w in clipped)  # type: ignore[return-value]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=Path("evaluation/results/composite_scores.json"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("evaluation/results/ales_sensitivity.json"),
    )
    args = parser.parse_args()

    if not args.input.exists():
        log.error("Input not found: %s — run composite_scores first.", args.input)
        return 2

    data = json.loads(args.input.read_text(encoding="utf-8"))
    per_case: list[dict] = data.get("per_case", [])
    if not per_case:
        log.error("No per_case entries in %s", args.input)
        return 2

    # Default-weight baseline (read straight from the file)
    baseline_values = [c["ALES"] for c in per_case if c.get("ALES") is not None]
    baseline_summary = _summary(baseline_values)

    perturbations: list[dict[str, Any]] = []
    for ci, comp in enumerate(COMPONENT_KEYS):
        for delta in PERTURBATIONS:
            if delta == 0.0:
                continue  # baseline already covered
            new_weights_raw = list(DEFAULT_WEIGHTS)
            new_weights_raw[ci] = DEFAULT_WEIGHTS[ci] + delta
            new_weights = _renormalize(tuple(new_weights_raw))  # type: ignore[arg-type]
            values = [
                _ales_for_case(c, new_weights) for c in per_case
                if _ales_for_case(c, new_weights) is not None
            ]
            summary = _summary(values)
            mean_delta = (
                round(summary.get("mean", 0.0) - baseline_summary.get("mean", 0.0), 4)
                if values else None
            )
            perturbations.append({
                "perturbed_component": comp,
                "delta": round(delta, 4),
                "weights_used": [round(w, 4) for w in new_weights],
                "summary": summary,
                "mean_delta_vs_baseline": mean_delta,
            })

    # Maximum absolute mean deviation across all perturbations
    max_abs_delta = max(
        (abs(p["mean_delta_vs_baseline"]) for p in perturbations
         if p["mean_delta_vs_baseline"] is not None),
        default=0.0,
    )

    out = {
        "default_weights": list(DEFAULT_WEIGHTS),
        "component_keys": list(COMPONENT_KEYS),
        "perturbation_grid": list(PERTURBATIONS),
        "baseline": baseline_summary,
        "perturbations": perturbations,
        "max_abs_mean_delta_vs_baseline": round(max_abs_delta, 4),
        "interpretation": (
            "Each perturbed row reports the per-case ALES recomputed with one "
            "component weight shifted by `delta`, the other three rescaled to "
            "preserve sum=1. `max_abs_mean_delta_vs_baseline` is the worst-case "
            "shift in ALES.mean across the grid; values below ~0.05 indicate "
            "the headline composite is robust to the chosen weights."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    log.info("Wrote %s", args.output)
    log.info(
        "Baseline ALES.mean=%.4f. Max |Δmean| across grid=%.4f",
        baseline_summary.get("mean", 0.0), max_abs_delta,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
