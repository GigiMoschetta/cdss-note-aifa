"""Internal helper — avoids circular imports between engine and logic."""
from __future__ import annotations

from .logic.three_valued import TruthValue
from .models.results import ScoreRange


def _score_eligible(score_range: ScoreRange, threshold: int | None) -> TruthValue:
    if threshold is None:
        return TruthValue.UNKNOWN
    if score_range.min >= threshold:
        return TruthValue.TRUE
    if score_range.max < threshold:
        return TruthValue.FALSE
    return TruthValue.UNKNOWN
