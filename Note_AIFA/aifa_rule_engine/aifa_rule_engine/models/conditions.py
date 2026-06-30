"""
AST node definitions for rule conditions.

ValueNode: nodes that return a raw value (int, float, str, bool, None)
BoolNode: nodes that return a TruthValue (TRUE / FALSE / UNKNOWN)

All nodes carry an `operator` discriminator for Pydantic unions.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Value nodes
# ---------------------------------------------------------------------------

class VarNode(BaseModel):
    """Reference to a patient-data field. Produces the raw value or None."""
    operator: Literal["VAR"] = "VAR"
    name: str


class LiteralNode(BaseModel):
    """Compile-time constant. Produces the literal value as-is."""
    operator: Literal["LITERAL"] = "LITERAL"
    value: Any


# Discriminated union: nodes that produce *values*, not truth-values
ValueNode = Annotated[
    VarNode | LiteralNode,
    Field(discriminator="operator"),
]


# ---------------------------------------------------------------------------
# Bool nodes
# ---------------------------------------------------------------------------

class IsTrueNode(BaseModel):
    """IS_TRUE(var): None→UNKNOWN, True→TRUE, False→FALSE.
    Only valid for boolean-typed fields (enforced by DataDictionary at load time).
    """
    operator: Literal["IS_TRUE"] = "IS_TRUE"
    var: str


class NotNode(BaseModel):
    """Logical NOT — Kleene semantics."""
    operator: Literal["NOT"] = "NOT"
    operand: BoolNode


class LogicalNode(BaseModel):
    """AND / OR with short-circuit Kleene semantics.
    operands: at least 2 elements (enforced by Pydantic min_length=2).
    """
    operator: Literal["AND", "OR"]
    # Audit V4 2026-05-12: enforce n-ary operator semantics — a 0- or 1-operand
    # AND/OR is malformed (unary AND degenerates to its operand; empty AND is
    # vacuously TRUE which is rarely what an author intends in rule YAML).
    operands: list[BoolNode] = Field(min_length=2)


class BinaryCompNode(BaseModel):
    """Numeric or string binary comparison.

    left/right MUST be ValueNodes.
    type_domain is required and validated:
      - GT/GTE/LT/LTE require "numeric"
      - EQ/NEQ accept any domain
    """
    operator: Literal["GT", "GTE", "LT", "LTE", "EQ", "NEQ"]
    left: ValueNode
    right: ValueNode
    type_domain: Literal["numeric", "string", "boolean"]

    @model_validator(mode="after")
    def validate_type_compatibility(self) -> BinaryCompNode:
        if self.operator in {"GT", "GTE", "LT", "LTE"} and self.type_domain != "numeric":
            raise ValueError(
                f"Operator {self.operator} requires type_domain='numeric', "
                f"got '{self.type_domain}'"
            )
        return self


class BetweenNode(BaseModel):
    """BETWEEN(var, low, high): inclusive on both ends [low, high].
    Equivalent to GTE(var, low) AND LTE(var, high).
    """
    operator: Literal["BETWEEN"] = "BETWEEN"
    var: str
    low: float
    high: float
    type_domain: Literal["numeric"] = "numeric"


class InNode(BaseModel):
    """IN(var, allowed_set): None→UNKNOWN, else membership check."""
    operator: Literal["IN"] = "IN"
    var: str
    allowed_set: list[str]


class CountGeqNode(BaseModel):
    """COUNT_GEQ(conditions, threshold):
    known_true  = count(c == TRUE)
    unknown_n   = count(c == UNKNOWN)
    if known_true >= threshold             → TRUE
    elif known_true + unknown_n < threshold → FALSE
    else                                   → UNKNOWN
    """
    operator: Literal["COUNT_GEQ"] = "COUNT_GEQ"
    conditions: list[BoolNode]
    threshold: int


class ScoreRangeGTENode(BaseModel):
    """SCORE_RANGE_GTE(score_range_var, threshold_var):
    Evaluates interval-score eligibility.
    Returns (TruthValue, frozenset[missing_fields]).
    Reserved exclusively for CHA2DS2-VASc interval eligibility.
    """
    operator: Literal["SCORE_RANGE_GTE"] = "SCORE_RANGE_GTE"
    score_range_var: str    # e.g. "cha2ds2vasc_range"
    threshold_var: str      # e.g. "cha2ds2vasc_threshold" — int | None
    anchor_note: str        # for proof generation


# Discriminated union: nodes that produce TruthValues
BoolNode = Annotated[
    IsTrueNode | NotNode | LogicalNode | BinaryCompNode | BetweenNode | InNode | CountGeqNode | ScoreRangeGTENode,
    Field(discriminator="operator"),
]

# Rebuild forward references
NotNode.model_rebuild()
LogicalNode.model_rebuild()
CountGeqNode.model_rebuild()
