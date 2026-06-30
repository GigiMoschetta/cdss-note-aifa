"""
Property-based tests for the Kleene three-valued logic algebra.

Audit fix 2026-05-06 (Task #21): the original test suite verified the 9 truth-
table entries for AND/OR/NOT manually but did not check the algebraic laws.
These properties are what makes Kleene 3VL a genuine logic — verifying them
gives strong assurance that the implementation cannot drift even if the
tables were typo'd.

Laws checked (all valid in Kleene strong 3VL, K3):
  - Idempotence:    AND(a, a) == a    ;  OR(a, a) == a
  - Double negation: NOT(NOT(a)) == a
  - De Morgan:      NOT(AND(a, b)) == OR(NOT(a), NOT(b))
                    NOT(OR(a, b))  == AND(NOT(a), NOT(b))
  - Commutativity:  AND(a, b) == AND(b, a) ; OR(a, b) == OR(b, a)
  - Associativity:  AND(AND(a, b), c) == AND(a, AND(b, c))
                    OR(OR(a, b), c)   == OR(a, OR(b, c))
  - Absorption:     AND(a, OR(a, b)) == a   ;  OR(a, AND(a, b)) == a
  - Identity:       AND(a, TRUE) == a   ;  OR(a, FALSE) == a
  - Annihilator:    AND(a, FALSE) == FALSE ; OR(a, TRUE) == TRUE
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aifa_rule_engine.logic.three_valued import TruthValue, tv_and, tv_not, tv_or

T = TruthValue.TRUE
F = TruthValue.FALSE
U = TruthValue.UNKNOWN

# Strategy: any TruthValue
truth_values = st.sampled_from([T, F, U])

_S = settings(max_examples=200, deadline=None)


@_S
@given(a=truth_values)
def test_and_idempotent(a):
    assert tv_and(a, a) == a


@_S
@given(a=truth_values)
def test_or_idempotent(a):
    assert tv_or(a, a) == a


@_S
@given(a=truth_values)
def test_double_negation(a):
    assert tv_not(tv_not(a)) == a


@_S
@given(a=truth_values, b=truth_values)
def test_de_morgan_and(a, b):
    assert tv_not(tv_and(a, b)) == tv_or(tv_not(a), tv_not(b))


@_S
@given(a=truth_values, b=truth_values)
def test_de_morgan_or(a, b):
    assert tv_not(tv_or(a, b)) == tv_and(tv_not(a), tv_not(b))


@_S
@given(a=truth_values, b=truth_values)
def test_and_commutative(a, b):
    assert tv_and(a, b) == tv_and(b, a)


@_S
@given(a=truth_values, b=truth_values)
def test_or_commutative(a, b):
    assert tv_or(a, b) == tv_or(b, a)


@_S
@given(a=truth_values, b=truth_values, c=truth_values)
def test_and_associative(a, b, c):
    assert tv_and(tv_and(a, b), c) == tv_and(a, tv_and(b, c))


@_S
@given(a=truth_values, b=truth_values, c=truth_values)
def test_or_associative(a, b, c):
    assert tv_or(tv_or(a, b), c) == tv_or(a, tv_or(b, c))


@_S
@given(a=truth_values, b=truth_values)
def test_absorption_and_or(a, b):
    """AND(a, OR(a, b)) == a"""
    assert tv_and(a, tv_or(a, b)) == a


@_S
@given(a=truth_values, b=truth_values)
def test_absorption_or_and(a, b):
    """OR(a, AND(a, b)) == a"""
    assert tv_or(a, tv_and(a, b)) == a


@_S
@given(a=truth_values)
def test_and_identity_true(a):
    """AND(a, TRUE) == a — TRUE is the identity element of AND."""
    assert tv_and(a, T) == a


@_S
@given(a=truth_values)
def test_or_identity_false(a):
    """OR(a, FALSE) == a — FALSE is the identity element of OR."""
    assert tv_or(a, F) == a


@_S
@given(a=truth_values)
def test_and_annihilator_false(a):
    """AND(a, FALSE) == FALSE — FALSE annihilates AND."""
    assert tv_and(a, F) == F


@_S
@given(a=truth_values)
def test_or_annihilator_true(a):
    """OR(a, TRUE) == TRUE — TRUE annihilates OR."""
    assert tv_or(a, T) == T


# Excluded middle and non-contradiction DO NOT hold in Kleene 3VL — that's a
# feature, not a bug. We assert their failure for U to make this explicit.

def test_excluded_middle_fails_for_unknown():
    """OR(U, NOT(U)) == U — Kleene 3VL is paracomplete (no LEM)."""
    assert tv_or(U, tv_not(U)) == U


def test_non_contradiction_fails_for_unknown():
    """AND(U, NOT(U)) == U — Kleene 3VL is paraconsistent for UNKNOWN."""
    assert tv_and(U, tv_not(U)) == U
