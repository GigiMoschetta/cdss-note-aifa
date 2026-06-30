"""
Unit tests for Kleene 3-valued logic operations.

Covers: AND/OR/NOT tables, COUNT_GEQ, ScoreRangeGTE, numeric comparisons.
"""
import pytest

from aifa_rule_engine.logic.three_valued import (
    TruthValue,
    _eval_count_geq,
    _eval_score_range_gte,
    tv_and,
    tv_not,
    tv_or,
)
from aifa_rule_engine.models.conditions import (
    BetweenNode,
    CountGeqNode,
    IsTrueNode,
    LiteralNode,
    ScoreRangeGTENode,
    VarNode,
)
from aifa_rule_engine.models.results import ScoreRange

T = TruthValue.TRUE
F = TruthValue.FALSE
U = TruthValue.UNKNOWN


# ---------------------------------------------------------------------------
# AND table (9 combinations)
# ---------------------------------------------------------------------------

class TestAnd:
    def test_tt(self): assert tv_and(T, T) == T
    def test_tf(self): assert tv_and(T, F) == F
    def test_tu(self): assert tv_and(T, U) == U
    def test_ft(self): assert tv_and(F, T) == F
    def test_ff(self): assert tv_and(F, F) == F
    def test_fu(self): assert tv_and(F, U) == F
    def test_ut(self): assert tv_and(U, T) == U
    def test_uf(self): assert tv_and(U, F) == F
    def test_uu(self): assert tv_and(U, U) == U


# ---------------------------------------------------------------------------
# OR table (9 combinations)
# ---------------------------------------------------------------------------

class TestOr:
    def test_tt(self): assert tv_or(T, T) == T
    def test_tf(self): assert tv_or(T, F) == T
    def test_tu(self): assert tv_or(T, U) == T
    def test_ft(self): assert tv_or(F, T) == T
    def test_ff(self): assert tv_or(F, F) == F
    def test_fu(self): assert tv_or(F, U) == U
    def test_ut(self): assert tv_or(U, T) == T
    def test_uf(self): assert tv_or(U, F) == U
    def test_uu(self): assert tv_or(U, U) == U


# ---------------------------------------------------------------------------
# NOT table
# ---------------------------------------------------------------------------

class TestNot:
    def test_not_true(self):  assert tv_not(T) == F
    def test_not_false(self): assert tv_not(F) == T
    def test_not_unknown(self): assert tv_not(U) == U


# ---------------------------------------------------------------------------
# COUNT_GEQ edge cases
# ---------------------------------------------------------------------------

def _make_count_geq(conditions_tvs: list[TruthValue], threshold: int) -> CountGeqNode:
    """Helper: build a COUNT_GEQ node with IsTrueNode placeholders,
    then evaluate it via inline data."""
    from aifa_rule_engine.logic.three_valued import eval_condition
    from aifa_rule_engine.models.conditions import CountGeqNode, IsTrueNode
    # We use distinct var names, set them in data
    vars_ = [f"v{i}" for i in range(len(conditions_tvs))]
    data = {}
    for var, tv in zip(vars_, conditions_tvs):
        if tv == TruthValue.TRUE:
            data[var] = True
        elif tv == TruthValue.FALSE:
            data[var] = False
        else:
            data[var] = None  # UNKNOWN

    node = CountGeqNode(
        operator="COUNT_GEQ",
        conditions=[IsTrueNode(operator="IS_TRUE", var=v) for v in vars_],
        threshold=threshold,
    )
    return eval_condition(node, data)


class TestCountGeq:
    def test_threshold_zero(self):
        tv, missing = _make_count_geq([], 0)
        assert tv == T
        assert missing == frozenset()

    def test_all_true_meets_threshold(self):
        tv, _ = _make_count_geq([T, T, T], 2)
        assert tv == T

    def test_all_unknown_below_threshold(self):
        tv, _ = _make_count_geq([U, U], 3)
        assert tv == F

    def test_mixed_unknown_straddles(self):
        # 1 TRUE, 1 UNKNOWN, threshold=2 → 1 < 2 ≤ 1+1 → UNKNOWN
        tv, missing = _make_count_geq([T, U, F], 2)
        assert tv == U

    def test_known_true_sufficient(self):
        # 2 TRUE, 1 UNKNOWN, threshold=2 → known_true=2 ≥ 2 → TRUE
        tv, missing = _make_count_geq([T, T, U], 2)
        assert tv == T
        assert missing == frozenset()  # no missing needed

    def test_impossible_to_reach(self):
        # 0 TRUE, 1 UNKNOWN, threshold=3 → max_possible=1 < 3 → FALSE
        tv, _ = _make_count_geq([F, F, U], 3)
        assert tv == F

    def test_apixaban_2of3_all_true(self):
        tv, _ = _make_count_geq([T, T, T], 2)
        assert tv == T

    def test_apixaban_2of3_with_unknown_enough(self):
        # eta=82 (TRUE), peso=55 (TRUE), creat=None (UNKNOWN) → TRUE (2 known ≥ 2)
        tv, missing = _make_count_geq([T, T, U], 2)
        assert tv == T

    def test_apixaban_2of3_with_unknown_insufficient(self):
        # eta=65 (FALSE), peso=70 (FALSE), creat=None (UNKNOWN)
        # known_true=0, unknown=1, max_possible=1 < 2 → FALSE
        tv, _ = _make_count_geq([F, F, U], 2)
        assert tv == F


# ---------------------------------------------------------------------------
# Numeric comparisons with None → UNKNOWN
# ---------------------------------------------------------------------------

from aifa_rule_engine.logic.three_valued import eval_condition
from aifa_rule_engine.models.conditions import BinaryCompNode


class TestNumericComparison:
    def _data(self, val):
        return {"x": val}

    def _gte(self, threshold):
        return BinaryCompNode(
            operator="GTE",
            left=VarNode(operator="VAR", name="x"),
            right=LiteralNode(operator="LITERAL", value=threshold),
            type_domain="numeric",
        )

    def test_none_operand_gives_unknown(self):
        node = self._gte(80)
        tv, missing = eval_condition(node, {"x": None})
        assert tv == U
        assert "x" in missing

    def test_gte_true(self):
        tv, _ = eval_condition(self._gte(80), {"x": 82})
        assert tv == T

    def test_gte_false(self):
        tv, _ = eval_condition(self._gte(80), {"x": 79})
        assert tv == F

    def test_gte_boundary_inclusive(self):
        # VEP-1.1 / Patch 6 — boundary must be inclusive
        tv, _ = eval_condition(self._gte(80), {"x": 80})
        assert tv == T

    def test_lte_boundary_inclusive(self):
        node = BinaryCompNode(
            operator="LTE",
            left=VarNode(operator="VAR", name="x"),
            right=LiteralNode(operator="LITERAL", value=60),
            type_domain="numeric",
        )
        tv, _ = eval_condition(node, {"x": 60})
        assert tv == T


# ---------------------------------------------------------------------------
# SCORE_RANGE_GTE — three eligibility cases + sex=None
# ---------------------------------------------------------------------------



class TestScoreRangeGte:
    def _node(self):
        return ScoreRangeGTENode(
            operator="SCORE_RANGE_GTE",
            score_range_var="cha2ds2vasc_range",
            threshold_var="cha2ds2vasc_threshold",
            anchor_note="97",
        )

    def _data(self, min_s, max_s, thr, unknown_comps=None):
        return {
            "cha2ds2vasc_range": ScoreRange(
                min=min_s, max=max_s,
                unknown_components=unknown_comps or [],
            ),
            "cha2ds2vasc_threshold": thr,
        }

    def test_true_min_above_threshold(self):
        # M, min=4 ≥ 2 → TRUE
        tv, missing = eval_condition(self._node(), self._data(4, 4, 2))
        assert tv == T
        assert missing == frozenset()

    def test_false_max_below_threshold(self):
        # M, max=1 < 2 → FALSE
        tv, missing = eval_condition(self._node(), self._data(1, 1, 2))
        assert tv == F
        assert missing == frozenset()

    def test_unknown_range_straddles(self):
        # M, min=1 < 2, max=3 ≥ 2 → UNKNOWN; missing = {"diabete_mellito"}
        tv, missing = eval_condition(
            self._node(),
            self._data(1, 3, 2, unknown_comps=["diabete_mellito"]),
        )
        assert tv == U
        assert "diabete_mellito" in missing

    def test_sex_none_gives_unknown(self):
        # threshold=None (sex unknown) → UNKNOWN; missing={"paziente_sesso"}
        tv, missing = eval_condition(
            self._node(),
            {
                "cha2ds2vasc_range": ScoreRange(min=4, max=4),
                "cha2ds2vasc_threshold": None,
            },
        )
        assert tv == U
        assert "paziente_sesso" in missing

    # V3.2 boundary test T-1.1a: M, score=2 → RIMBORSABILE (≥2)
    def test_m_score2_true(self):
        tv, _ = eval_condition(self._node(), self._data(2, 2, 2))
        assert tv == T

    # V3.2 boundary test T-1.1b: M, score=1 → NON_RIMBORSABILE
    def test_m_score1_false(self):
        tv, _ = eval_condition(self._node(), self._data(1, 1, 2))
        assert tv == F

    # V3.2 boundary: F, score=3 → RIMBORSABILE (≥3)
    def test_f_score3_true(self):
        tv, _ = eval_condition(self._node(), self._data(3, 3, 3))
        assert tv == T

    # V3.2 boundary: F, score=2 → NON_RIMBORSABILE
    def test_f_score2_false(self):
        tv, _ = eval_condition(self._node(), self._data(2, 2, 3))
        assert tv == F


# ── Audit fix 2026-05-06 (F-NEW-1, F-NEW-2): runtime robustness ───────────

class TestIsTrueIntCoercion:
    """JSON deserialization can produce int 1/0 for boolean fields. The strict
    `is True` check used to flip the truth value silently — now we accept
    int 1 as TRUE and int 0/anything else as FALSE."""

    def _node(self):
        return IsTrueNode(operator="IS_TRUE", var="flag")

    def test_int_one_is_true(self):
        tv, _ = eval_condition(self._node(), {"flag": 1})
        assert tv == T

    def test_int_zero_is_false(self):
        tv, _ = eval_condition(self._node(), {"flag": 0})
        assert tv == F

    def test_bool_true_still_true(self):
        tv, _ = eval_condition(self._node(), {"flag": True})
        assert tv == T

    def test_none_still_unknown(self):
        tv, missing = eval_condition(self._node(), {"flag": None})
        assert tv == U
        assert "flag" in missing


class TestBinaryCompTypeError:
    """A string vs numeric comparison must raise a clear ValueError, not an
    opaque TypeError that propagates as HTTP 500 without diagnostic detail."""

    def test_string_vs_numeric_raises_value_error(self):
        node = BinaryCompNode(
            operator="GTE",
            left=VarNode(operator="VAR", name="paziente_eta"),
            right=LiteralNode(operator="LITERAL", value=80.0),
            type_domain="numeric",
        )
        with pytest.raises(ValueError, match="Type mismatch"):
            eval_condition(node, {"paziente_eta": "80"})
