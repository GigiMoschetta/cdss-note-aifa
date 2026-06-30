"""
Kleene Strong Three-Valued Logic — core evaluation primitives.

TruthValue: TRUE | FALSE | UNKNOWN

Implements:
- AND / OR / NOT tables
- COUNT_GEQ semantics
- Numeric/string comparison operators with None → UNKNOWN
- eval_value / eval_condition split (Fix — type safety contract)
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from ..models.conditions import (
    BetweenNode,
    BinaryCompNode,
    BoolNode,
    CountGeqNode,
    InNode,
    IsTrueNode,
    LiteralNode,
    LogicalNode,
    NotNode,
    ScoreRangeGTENode,
    ValueNode,
    VarNode,
)
from ..models.results import ScoreRange


class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Kleene tables
# ---------------------------------------------------------------------------

def tv_and(a: TruthValue, b: TruthValue) -> TruthValue:
    if a == TruthValue.FALSE or b == TruthValue.FALSE:
        return TruthValue.FALSE
    if a == TruthValue.TRUE and b == TruthValue.TRUE:
        return TruthValue.TRUE
    return TruthValue.UNKNOWN


def tv_or(a: TruthValue, b: TruthValue) -> TruthValue:
    if a == TruthValue.TRUE or b == TruthValue.TRUE:
        return TruthValue.TRUE
    if a == TruthValue.FALSE and b == TruthValue.FALSE:
        return TruthValue.FALSE
    return TruthValue.UNKNOWN


def tv_not(a: TruthValue) -> TruthValue:
    if a == TruthValue.TRUE:
        return TruthValue.FALSE
    if a == TruthValue.FALSE:
        return TruthValue.TRUE
    return TruthValue.UNKNOWN


# ---------------------------------------------------------------------------
# eval_value — resolves ValueNodes to raw Python values
# ---------------------------------------------------------------------------

def eval_value(
    node: ValueNode,
    data: dict[str, Any],
) -> tuple[Any | None, frozenset[str]]:
    """Return (raw_value_or_None, missing_fields).

    Never returns a TruthValue — only raw Python scalars.
    """
    if isinstance(node, VarNode):
        val = data.get(node.name)
        if val is None:
            return (None, frozenset({node.name}))
        return (val, frozenset())
    if isinstance(node, LiteralNode):
        return (node.value, frozenset())
    raise TypeError(f"eval_value: unknown ValueNode type {type(node)}")


# ---------------------------------------------------------------------------
# eval_condition — resolves BoolNodes to TruthValue
# ---------------------------------------------------------------------------

def eval_condition(
    node: BoolNode,
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """Return (TruthValue, missing_fields).

    Short-circuit semantics:
    - AND(FALSE, X) → (FALSE, frozenset())  — X never evaluated
    - OR(TRUE, X)   → (TRUE,  frozenset())  — X never evaluated
    """

    # --- IS_TRUE ---
    if isinstance(node, IsTrueNode):
        val = data.get(node.var)
        if val is None:
            return (TruthValue.UNKNOWN, frozenset({node.var}))
        # Audit fix 2026-05-06 (F-NEW-1) + 2026-05-07 (V3-F1.5): JSON deserialization
        # may produce int 1 for a "boolean" field (e.g. {"flag": 1}) or a string
        # ("true"/"false") if upstream HTTP/form parsing did not coerce types.
        # Strict `is True` would silently flip these to FALSE. Accept:
        #   bool True / int 1 / str "true"/"1" (case-insensitive, stripped) → TRUE
        # Everything else (including bool False, 0, "false", None-like) → FALSE.
        if val is True or val == 1:
            return (TruthValue.TRUE, frozenset())
        if isinstance(val, str) and val.strip().lower() in ("true", "1"):
            return (TruthValue.TRUE, frozenset())
        return (TruthValue.FALSE, frozenset())

    # --- NOT ---
    if isinstance(node, NotNode):
        tv, missing = eval_condition(node.operand, data)
        return (tv_not(tv), missing)

    # --- AND / OR ---
    if isinstance(node, LogicalNode):
        if node.operator == "AND":
            return _eval_and(node.operands, data)
        else:
            return _eval_or(node.operands, data)

    # --- BinaryComp ---
    if isinstance(node, BinaryCompNode):
        return _eval_binary_comp(node, data)

    # --- BETWEEN ---
    if isinstance(node, BetweenNode):
        val = data.get(node.var)
        if val is None:
            return (TruthValue.UNKNOWN, frozenset({node.var}))
        result = node.low <= val <= node.high
        return (TruthValue.TRUE if result else TruthValue.FALSE, frozenset())

    # --- IN ---
    if isinstance(node, InNode):
        val = data.get(node.var)
        if val is None:
            return (TruthValue.UNKNOWN, frozenset({node.var}))
        result = str(val) in node.allowed_set
        return (TruthValue.TRUE if result else TruthValue.FALSE, frozenset())

    # --- COUNT_GEQ ---
    if isinstance(node, CountGeqNode):
        return _eval_count_geq(node, data)

    # --- SCORE_RANGE_GTE ---
    if isinstance(node, ScoreRangeGTENode):
        return _eval_score_range_gte(node, data)

    raise TypeError(f"eval_condition: unknown BoolNode type {type(node)}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _eval_and(
    operands: list[BoolNode],
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """AND with short-circuit: first FALSE → return immediately."""
    accumulated_missing: frozenset[str] = frozenset()
    current_tv = TruthValue.TRUE

    for operand in operands:
        tv, missing = eval_condition(operand, data)
        if tv == TruthValue.FALSE:
            # Short-circuit — discard any missing from un-evaluated branches
            return (TruthValue.FALSE, frozenset())
        accumulated_missing = accumulated_missing | missing
        current_tv = tv_and(current_tv, tv)

    return (current_tv, accumulated_missing)


def _eval_or(
    operands: list[BoolNode],
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """OR with short-circuit: first TRUE → return immediately."""
    accumulated_missing: frozenset[str] = frozenset()
    current_tv = TruthValue.FALSE

    for operand in operands:
        tv, missing = eval_condition(operand, data)
        if tv == TruthValue.TRUE:
            # Short-circuit — discard missing from un-evaluated branches
            return (TruthValue.TRUE, frozenset())
        accumulated_missing = accumulated_missing | missing
        current_tv = tv_or(current_tv, tv)

    return (current_tv, accumulated_missing)


def _eval_binary_comp(
    node: BinaryCompNode,
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    lv, lm = eval_value(node.left, data)
    rv, rm = eval_value(node.right, data)

    if lv is None or rv is None:
        return (TruthValue.UNKNOWN, lm | rm)

    op = node.operator
    # Audit fix 2026-05-06 (F-NEW-2): a malformed patient_data payload may send
    # a string where a number is expected (e.g. {"paziente_eta": "80"}). The
    # comparison would raise TypeError → propagate as opaque HTTP 500. Wrap
    # with an explicit ValueError that names the offending node and types so
    # the API can return a 4xx with diagnostic detail.
    try:
        if op == "GT":
            result = lv > rv
        elif op == "GTE":
            result = lv >= rv
        elif op == "LT":
            result = lv < rv
        elif op == "LTE":
            result = lv <= rv
        elif op == "EQ":
            result = lv == rv
        elif op == "NEQ":
            result = lv != rv
        else:
            raise ValueError(f"Unknown binary operator: {op}")
    except TypeError as exc:
        raise ValueError(
            f"Type mismatch in binary comparison '{op}': "
            f"left={type(lv).__name__}({lv!r}) vs right={type(rv).__name__}({rv!r}). "
            "Check patient_data field types — numeric fields must not be strings."
        ) from exc

    return (TruthValue.TRUE if result else TruthValue.FALSE, frozenset())


def _eval_count_geq(
    node: CountGeqNode,
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """COUNT_GEQ semantics with UNKNOWN propagation."""
    known_true = 0
    unknown_n = 0
    all_missing: frozenset[str] = frozenset()

    for cond in node.conditions:
        tv, missing = eval_condition(cond, data)
        if tv == TruthValue.TRUE:
            known_true += 1
        elif tv == TruthValue.UNKNOWN:
            unknown_n += 1
            all_missing = all_missing | missing

    thr = node.threshold
    if known_true >= thr:
        return (TruthValue.TRUE, frozenset())
    elif known_true + unknown_n < thr:
        return (TruthValue.FALSE, frozenset())
    else:
        return (TruthValue.UNKNOWN, all_missing)


def _eval_score_range_gte(
    node: ScoreRangeGTENode,
    data: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """Interval-score eligibility for CHA2DS2-VASc.

    Reads pre-computed ScoreRange and threshold from enriched data.
    Returns (TruthValue, frozenset[missing_fields]).
    """
    score_range: ScoreRange | None = data.get(node.score_range_var)
    threshold: int | None = data.get(node.threshold_var)

    if threshold is None:
        # Sex unknown → threshold unknown → UNKNOWN
        return (TruthValue.UNKNOWN, frozenset({"paziente_sesso"}))

    if score_range is None:
        return (TruthValue.UNKNOWN, frozenset({node.score_range_var}))

    if score_range.min >= threshold:
        return (TruthValue.TRUE, frozenset())
    elif score_range.max < threshold:
        return (TruthValue.FALSE, frozenset())
    else:
        # Range straddles threshold — which components are missing?
        return (TruthValue.UNKNOWN, frozenset(score_range.unknown_components))
