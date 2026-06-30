"""
Output schema models — EvaluationResult V3.3 + RagPayload.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .rules import NormativeAnchor

# ---------------------------------------------------------------------------
# Score range models
# ---------------------------------------------------------------------------

class ScoreRange(BaseModel):
    """Internal derivation result — not serialized directly in API output."""
    min: int
    max: int
    unknown_components: list[str] = []


class ScoreRangeResult(BaseModel):
    """Serialized in RagPayload.computed_scores."""
    score_name: str
    min_score: int
    max_score: int
    threshold: int | None          # None if sex unknown
    eligible: str                  # "TRUE" | "FALSE" | "UNKNOWN"
    missing_components: list[str]  # which score component vars were UNKNOWN
    anchor: NormativeAnchor


# ---------------------------------------------------------------------------
# Clinical flags
# ---------------------------------------------------------------------------

class ClinicalFlag(BaseModel):
    rule_id: str
    flag_type: Literal[
        "DOSE_STANDARD",
        "DOSE_RIDOTTA",
        "DOSE_CONTROINDICATA",
        "PREFERENCE",
        "WARNING",
    ]
    informational_only: bool = False   # True when coverage == NON_RIMBORSABILE
    detail: str = ""
    facts_used: dict[str, Any] = Field(default_factory=dict)
    anchor: NormativeAnchor
    # Bug fix RE-B4 (audit): when multiple DOSE rules fire simultaneously
    # (e.g. apixaban with count≥2 + VFG 15-29 both → DOSE_RIDOTTA), the
    # conflict resolver previously suppressed all but the highest-priority,
    # losing the parallel justifications. We now preserve them here so the
    # clinician sees ALL the reasons leading to the chosen dose.
    additional_anchors: list[NormativeAnchor] = Field(default_factory=list)
    additional_rule_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Coverage trace entry
# ---------------------------------------------------------------------------

class CoverageTraceEntry(BaseModel):
    rule_id: str
    rule_type: str
    truth_value: str           # "TRUE" | "FALSE" | "UNKNOWN"
    outcome: str               # "PROCEED" | "NON_RIMBORSABILE" | "BYPASS" | "ROUTE" | "UNKNOWN_PENDING"
    phase: int
    facts_used: dict[str, Any] = Field(default_factory=dict)
    anchor: NormativeAnchor
    missing_fields: list[str] = []


# ---------------------------------------------------------------------------
# Audit trail entry
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    rule_id: str
    rule_type: str
    truth_value: str
    phase: int
    missing_fields: list[str] = []
    note: str = ""


# ---------------------------------------------------------------------------
# RagPayload — structured proof object (Fix 4.1)
# ---------------------------------------------------------------------------

class BlockingRule(BaseModel):
    rule_id: str
    rule_type: str
    # coverage_impact: FALSE = coverage is denied, UNKNOWN = coverage is uncertain
    truth_value: Literal["FALSE", "UNKNOWN"]
    # rule_evaluated_as: the raw Kleene evaluation result of the rule's own condition
    # For EXCL_HARD: rule_evaluated_as="TRUE" (the exclusion fired) → truth_value="FALSE" (coverage denied)
    # For SCOPE/INCLUSION/PATHWAY: both fields share the same value (FALSE or UNKNOWN)
    rule_evaluated_as: Literal["TRUE", "FALSE", "UNKNOWN"] = "FALSE"
    reason: str
    anchor: NormativeAnchor


class RagPayload(BaseModel):
    decision_status: Literal["FINAL", "ROUTED", "DEFERRED"]
    reimbursement_decision: str | None
    blocking_rules: list[BlockingRule]
    passed_rules: list[dict]            # {rule_id, anchor}
    unknown_rules: list[dict]           # {rule_id, anchor, missing_fields}
    missing_fields: list[str]           # decisive coverage missing fields only
    computed_scores: dict[str, ScoreRangeResult]
    clinical_context_summary: str       # deterministic template, no LLM prose

    # ── Structured fields (refactor RE-M3) ────────────────────────────────────
    # The orchestrator previously regex-parsed `clinical_context_summary` to
    # extract eligibility / activated rules / decision text. These fields are
    # now exposed as typed primitives so consumers can avoid string parsing.
    # The summary string is preserved for human readability inside the prompt.
    score_eligible: Literal["TRUE", "FALSE", "UNKNOWN"] | None = None
    activated_rule_ids: list[str] = Field(default_factory=list)
    blocking_rule_ids: list[str] = Field(default_factory=list)
    decision_text: str = ""


# ---------------------------------------------------------------------------
# Top-level EvaluationResult
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    schema_version: Literal["3.3"] = "3.3"
    decision_status: Literal["FINAL", "ROUTED", "DEFERRED"]
    reimbursement_decision: Literal[
        "RIMBORSABILE",
        "NON_RIMBORSABILE",
        "NON_DETERMINABILE",
    ] | None = None    # None only when decision_status != "FINAL"

    nota_evaluated: str
    drug_evaluated: str

    route_to: str | None = None        # nota_id when ROUTED
    route_reason: str | None = None

    clinical_flags: list[ClinicalFlag] = Field(default_factory=list)

    missing_fields_coverage: list[str] = Field(default_factory=list)
    missing_fields_guidance: list[str] = Field(default_factory=list)

    rag_payload: RagPayload

    coverage_trace: list[CoverageTraceEntry] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)

    engine_version: str = "3.4.0"
    rule_catalog_version: str = ""
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
