"""
Pydantic models for rule specifications.

All rule types share BaseRule. Each is discriminated by rule_type.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from .conditions import BoolNode


class NormativeAnchor(BaseModel):
    """Required on every rule. No anchor → startup failure."""
    pdf_file: str
    page: int
    section: str = ""
    excerpt: str = ""


class StructuredMotivation(BaseModel):
    rationale_it: str = ""
    clinical_impact: str = ""


class BaseRule(BaseModel):
    rule_id: str
    nota: Literal["97", "13", "01", "66"]
    version: str = "3.4.0"
    description_it: str
    # Deprecated — inferred from AST at startup; kept for optional validation
    required_variables: list[str] = []
    condition: BoolNode
    normative_anchor: NormativeAnchor
    structured_motivation: StructuredMotivation = Field(
        default_factory=StructuredMotivation
    )
    evaluation_order: int = 0
    # Declarative prerequisite (rule IDs that should have evaluated TRUE before this).
    #
    # STATUS — documentation-only, NOT enforced at runtime.
    #
    # The 10-phase fail-fast pipeline already short-circuits SCOPE/INCL/PATHWAY
    # violations, so prerequisite enforcement is implicit for those phases.
    # For GUIDANCE_DOSE/PREF/WARN this field is purely informative.
    #
    # Enforcement gate: if a YAML rule populates this list, rule_loader Phase
    # S3 emits a startup WARNING reminding the maintainer that the field is
    # documentation-only. Use `evaluation_order` (or the rule_type phase) for
    # hard ordering, not this field. To enable strict enforcement, see the
    # follow-up item in LIMITATIONS.md.
    requires_passed: list[str] = []
    # When this EXCEPTION fires TRUE, skip these rule_ids
    bypasses: list[str] = []
    # Set by rule_loader Phase S4: variables actually referenced by the
    # rule's AST condition. Used by `_gather_facts` to populate the audit
    # trail with the patient values that drove the decision. Stored as a
    # frozenset for hashability and immutability after loading.
    # Excluded from `model_dump()` because it is internal startup state, not
    # part of the YAML-author-facing schema.
    inferred_variables: frozenset[str] = Field(
        default_factory=frozenset,
        exclude=True,
        repr=False,
    )


class ScopeRule(BaseRule):
    rule_type: Literal["SCOPE"] = "SCOPE"


class ExclHardRule(BaseRule):
    rule_type: Literal["EXCL_HARD"] = "EXCL_HARD"


class InclusionRule(BaseRule):
    rule_type: Literal["INCLUSION"] = "INCLUSION"


class PathwayRule(BaseRule):
    rule_type: Literal["PATHWAY"] = "PATHWAY"


class ExceptionRule(BaseRule):
    rule_type: Literal["EXCEPTION"] = "EXCEPTION"
    outcome_if_true: Literal["NON_RIMBORSABILE", "BYPASS", "ROUTE", "DEFER"]
    route_to_nota: str | None = None

    @model_validator(mode="after")
    def validate_route_consistency(self) -> ExceptionRule:
        if self.outcome_if_true in {"ROUTE", "DEFER"} and not self.route_to_nota:
            raise ValueError(
                f"Rule {self.rule_id}: outcome_if_true={self.outcome_if_true} "
                "requires route_to_nota to be set"
            )
        return self


class GuidanceDoseRule(BaseRule):
    rule_type: Literal["GUIDANCE_DOSE"] = "GUIDANCE_DOSE"
    flag_type: Literal["DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"]
    detail: str = ""


class GuidancePrefRule(BaseRule):
    rule_type: Literal["GUIDANCE_PREF"] = "GUIDANCE_PREF"
    detail: str = ""


class GuidanceWarnRule(BaseRule):
    rule_type: Literal["GUIDANCE_WARN"] = "GUIDANCE_WARN"
    detail: str = ""


# Discriminated union of all rule types
RuleSpec = Annotated[
    ScopeRule | ExclHardRule | InclusionRule | PathwayRule | ExceptionRule | GuidanceDoseRule | GuidancePrefRule | GuidanceWarnRule,
    Field(discriminator="rule_type"),
]
