"""Audit V4 2026-05-12: validation invariants on rule AST.

- LogicalNode AND/OR must have >=2 operands (n-ary operator semantics)
- requires_passed cross-reference checked at evaluator time
"""
import pytest
from pydantic import ValidationError

from aifa_rule_engine.models.conditions import BinaryCompNode, LogicalNode, VarNode


def _bool_leaf(var: str) -> dict:
    return {
        "operator": "EQ",
        "left": {"operator": "VAR", "name": var},
        "right": {"operator": "LITERAL", "value": True},
        "type_domain": "boolean",
    }


class TestLogicalNodeMinLength:
    def test_and_rejects_zero_operands(self):
        with pytest.raises(ValidationError):
            LogicalNode(operator="AND", operands=[])

    def test_and_rejects_single_operand(self):
        with pytest.raises(ValidationError):
            LogicalNode(operator="AND", operands=[_bool_leaf("smoker")])

    def test_or_rejects_zero_operands(self):
        with pytest.raises(ValidationError):
            LogicalNode(operator="OR", operands=[])

    def test_or_rejects_single_operand(self):
        with pytest.raises(ValidationError):
            LogicalNode(operator="OR", operands=[_bool_leaf("smoker")])

    def test_accepts_two_operands(self):
        node = LogicalNode(
            operator="AND",
            operands=[_bool_leaf("smoker"), _bool_leaf("anticoag_user")],
        )
        assert len(node.operands) == 2
