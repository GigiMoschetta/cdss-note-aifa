"""
Unit tests for eval_condition / eval_value:
- Return type: (TruthValue, frozenset[str])
- Short-circuit semantics
- Missing field propagation
- BinaryCompNode type_domain validation (load-time)
"""
import pytest
from pydantic import ValidationError

from aifa_rule_engine.logic.three_valued import TruthValue, eval_condition, eval_value
from aifa_rule_engine.models.conditions import (
    BetweenNode,
    BinaryCompNode,
    InNode,
    IsTrueNode,
    LiteralNode,
    LogicalNode,
    NotNode,
    VarNode,
)

T = TruthValue.TRUE
F = TruthValue.FALSE
U = TruthValue.UNKNOWN


def is_true(var: str) -> IsTrueNode:
    return IsTrueNode(operator="IS_TRUE", var=var)


def lit(v):
    return LiteralNode(operator="LITERAL", value=v)


def var(name: str):
    return VarNode(operator="VAR", name=name)


def and_(*operands):
    return LogicalNode(operator="AND", operands=list(operands))


def or_(*operands):
    return LogicalNode(operator="OR", operands=list(operands))


def not_(operand):
    return NotNode(operator="NOT", operand=operand)


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------

def test_eval_condition_returns_tuple():
    tv, missing = eval_condition(is_true("x"), {"x": True})
    assert isinstance(tv, TruthValue)
    assert isinstance(missing, frozenset)


def test_eval_condition_true():
    tv, _ = eval_condition(is_true("x"), {"x": True})
    assert tv == T


def test_eval_condition_false():
    tv, _ = eval_condition(is_true("x"), {"x": False})
    assert tv == F


def test_eval_condition_unknown_missing():
    tv, missing = eval_condition(is_true("x"), {})
    assert tv == U
    assert "x" in missing


# ---------------------------------------------------------------------------
# Short-circuit: AND(FALSE, UNKNOWN) → (FALSE, frozenset())
# ---------------------------------------------------------------------------

def test_and_short_circuit_false_unknown():
    node = and_(is_true("a"), is_true("b"))
    data = {"a": False}  # b is missing (UNKNOWN)
    tv, missing = eval_condition(node, data)
    assert tv == F
    assert missing == frozenset()  # b never evaluated


# ---------------------------------------------------------------------------
# Short-circuit: OR(TRUE, UNKNOWN) → (TRUE, frozenset())
# ---------------------------------------------------------------------------

def test_or_short_circuit_true_unknown():
    node = or_(is_true("a"), is_true("b"))
    data = {"a": True}  # b is missing (UNKNOWN)
    tv, missing = eval_condition(node, data)
    assert tv == T
    assert missing == frozenset()  # b never evaluated


# ---------------------------------------------------------------------------
# Missing field propagation
# ---------------------------------------------------------------------------

def test_and_propagates_missing():
    node = and_(is_true("a"), is_true("b"))
    # a=True (UNKNOWN b is decisive)
    tv, missing = eval_condition(node, {"a": True})
    assert tv == U
    assert "b" in missing


def test_nested_and_missing():
    # AND(a=None, b=True) → (UNKNOWN, {a})
    node = and_(is_true("a"), is_true("b"))
    tv, missing = eval_condition(node, {"a": None, "b": True})
    assert tv == U
    assert "a" in missing
    assert "b" not in missing  # b is TRUE, not missing


def test_or_propagates_missing_from_both_unknown():
    # OR(UNKNOWN, UNKNOWN) → (UNKNOWN, {a,b})
    node = or_(is_true("a"), is_true("b"))
    tv, missing = eval_condition(node, {})
    assert tv == U
    assert "a" in missing
    assert "b" in missing


def test_or_false_unknown_propagates():
    # OR(FALSE, UNKNOWN) → (UNKNOWN, {b})
    node = or_(is_true("a"), is_true("b"))
    tv, missing = eval_condition(node, {"a": False})
    assert tv == U
    assert "b" in missing


# ---------------------------------------------------------------------------
# eval_value basics
# ---------------------------------------------------------------------------

def test_eval_value_var_present():
    val, missing = eval_value(var("x"), {"x": 42})
    assert val == 42
    assert missing == frozenset()


def test_eval_value_var_missing():
    val, missing = eval_value(var("x"), {})
    assert val is None
    assert "x" in missing


def test_eval_value_literal():
    val, missing = eval_value(lit(99), {})
    assert val == 99
    assert missing == frozenset()


# ---------------------------------------------------------------------------
# NOT semantics
# ---------------------------------------------------------------------------

def test_not_true_gives_false():
    tv, _ = eval_condition(not_(is_true("x")), {"x": True})
    assert tv == F


def test_not_false_gives_true():
    tv, _ = eval_condition(not_(is_true("x")), {"x": False})
    assert tv == T


def test_not_unknown_stays_unknown():
    tv, missing = eval_condition(not_(is_true("x")), {})
    assert tv == U
    assert "x" in missing


# ---------------------------------------------------------------------------
# BETWEEN
# ---------------------------------------------------------------------------

def test_between_inclusive_low():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, _ = eval_condition(node, {"x": 15})
    assert tv == T


def test_between_inclusive_high():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, _ = eval_condition(node, {"x": 29})
    assert tv == T


def test_between_inside():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, _ = eval_condition(node, {"x": 22})
    assert tv == T


def test_between_outside_low():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, _ = eval_condition(node, {"x": 14})
    assert tv == F


def test_between_outside_high():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, _ = eval_condition(node, {"x": 30})
    assert tv == F


def test_between_none_gives_unknown():
    node = BetweenNode(operator="BETWEEN", var="x", low=15.0, high=29.0)
    tv, missing = eval_condition(node, {})
    assert tv == U
    assert "x" in missing


# ---------------------------------------------------------------------------
# IN
# ---------------------------------------------------------------------------

def test_in_match():
    node = InNode(operator="IN", var="x", allowed_set=["apixaban", "dabigatran"])
    tv, _ = eval_condition(node, {"x": "apixaban"})
    assert tv == T


def test_in_no_match():
    node = InNode(operator="IN", var="x", allowed_set=["apixaban", "dabigatran"])
    tv, _ = eval_condition(node, {"x": "warfarin"})
    assert tv == F


def test_in_none_gives_unknown():
    node = InNode(operator="IN", var="x", allowed_set=["apixaban"])
    tv, missing = eval_condition(node, {})
    assert tv == U
    assert "x" in missing


# ---------------------------------------------------------------------------
# BinaryCompNode type_domain validation — load-time (Pydantic)
# ---------------------------------------------------------------------------

def test_binary_comp_type_domain_validation_gt_requires_numeric():
    with pytest.raises(ValidationError, match="numeric"):
        BinaryCompNode(
            operator="GT",
            left=VarNode(operator="VAR", name="x"),
            right=LiteralNode(operator="LITERAL", value=5),
            type_domain="boolean",  # INVALID for GT
        )


def test_binary_comp_gte_requires_numeric():
    with pytest.raises(ValidationError, match="numeric"):
        BinaryCompNode(
            operator="GTE",
            left=VarNode(operator="VAR", name="x"),
            right=LiteralNode(operator="LITERAL", value=5),
            type_domain="string",  # INVALID for GTE
        )


def test_binary_comp_eq_allows_string():
    # EQ with string domain is valid
    node = BinaryCompNode(
        operator="EQ",
        left=VarNode(operator="VAR", name="x"),
        right=LiteralNode(operator="LITERAL", value="dabigatran"),
        type_domain="string",
    )
    assert node is not None


def test_binary_comp_neq_allows_string():
    node = BinaryCompNode(
        operator="NEQ",
        left=VarNode(operator="VAR", name="x"),
        right=LiteralNode(operator="LITERAL", value="nimesulide"),
        type_domain="string",
    )
    assert node is not None
