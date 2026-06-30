"""
RagPayload builder — structured proof object (Fix 4.1).

Replaces the old rag_query_context: str with a machine-readable RagPayload.
Uses a deterministic template — NO LLM prose.
"""
from __future__ import annotations

from ..models.results import (
    AuditEntry,
    BlockingRule,
    CoverageTraceEntry,
    RagPayload,
    ScoreRangeResult,
)


def build_rag_payload(
    decision_status: str,
    reimbursement_decision: str | None,
    coverage_trace: list[CoverageTraceEntry],
    audit_trail: list[AuditEntry],
    missing_fields_coverage: list[str],
    computed_scores: dict[str, ScoreRangeResult],
    nota_id: str,
    drug_id: str,
) -> RagPayload:
    """Build the structured RagPayload from the evaluation trace."""

    blocking_rules: list[BlockingRule] = []
    passed_rules: list[dict] = []
    unknown_rules: list[dict] = []

    for entry in coverage_trace:
        if entry.outcome in {"NON_RIMBORSABILE"}:
            # Rule that caused denial
            tv_str = entry.truth_value
            if tv_str in {"FALSE", "UNKNOWN"}:
                # SCOPE/INCLUSION/PATHWAY evaluated FALSE, or any rule evaluated UNKNOWN
                # coverage_impact == rule_evaluated_as in these cases
                blocking_rules.append(BlockingRule(
                    rule_id=entry.rule_id,
                    rule_type=entry.rule_type,
                    truth_value=tv_str,          # type: ignore[arg-type]
                    rule_evaluated_as=tv_str,    # type: ignore[arg-type]
                    reason=f"Rule {entry.rule_id} evaluated {tv_str} → {entry.outcome}",
                    anchor=entry.anchor,
                ))
            elif tv_str == "TRUE":
                # EXCL_HARD (or EXCEPTION/NON_RIMBORSABILE) fired TRUE → denial
                # rule_evaluated_as="TRUE" preserves the raw result for the orchestrator
                # truth_value="FALSE" expresses that coverage is blocked (semantic coverage impact)
                blocking_rules.append(BlockingRule(
                    rule_id=entry.rule_id,
                    rule_type=entry.rule_type,
                    truth_value="FALSE",         # coverage impact: DENIED
                    rule_evaluated_as="TRUE",    # raw: the exclusion rule fired TRUE
                    reason=f"Rule {entry.rule_id} evaluated TRUE → exclusion → NON_RIMBORSABILE",
                    anchor=entry.anchor,
                ))
        elif entry.outcome == "PROCEED":
            passed_rules.append({
                "rule_id": entry.rule_id,
                "anchor": entry.anchor.model_dump(),
            })
        elif entry.outcome == "UNKNOWN_PENDING":
            unknown_rules.append({
                "rule_id": entry.rule_id,
                "anchor": entry.anchor.model_dump(),
                "missing_fields": entry.missing_fields,
            })

    summary = _build_clinical_context_summary(
        nota_id=nota_id,
        drug_id=drug_id,
        decision_status=decision_status,
        reimbursement_decision=reimbursement_decision,
        passed_rules=passed_rules,
        blocking_rules=blocking_rules,
        computed_scores=computed_scores,
    )

    # Structured projections (refactor RE-M3): orchestrator can now read
    # these typed fields instead of regex-parsing `clinical_context_summary`.
    score_eligible = None
    if "cha2ds2vasc" in computed_scores:
        score_eligible = computed_scores["cha2ds2vasc"].eligible  # type: ignore[assignment]
    activated_rule_ids = [r["rule_id"] for r in passed_rules]
    blocking_rule_ids = [r.rule_id for r in blocking_rules]
    if reimbursement_decision is not None:
        decision_text = reimbursement_decision
    elif decision_status == "ROUTED":
        decision_text = "ROUTED"
    elif decision_status == "DEFERRED":
        decision_text = "DEFERRED"
    else:
        decision_text = "NON_DETERMINABILE"

    return RagPayload(
        decision_status=decision_status,  # type: ignore[arg-type]
        reimbursement_decision=reimbursement_decision,
        blocking_rules=blocking_rules,
        passed_rules=passed_rules,
        unknown_rules=unknown_rules,
        missing_fields=sorted(set(missing_fields_coverage)),
        computed_scores=computed_scores,
        clinical_context_summary=summary,
        score_eligible=score_eligible,
        activated_rule_ids=activated_rule_ids,
        blocking_rule_ids=blocking_rule_ids,
        decision_text=decision_text,
    )


def _build_clinical_context_summary(
    nota_id: str,
    drug_id: str,
    decision_status: str,
    reimbursement_decision: str | None,
    passed_rules: list[dict],
    blocking_rules: list[BlockingRule],
    computed_scores: dict[str, ScoreRangeResult],
) -> str:
    """Deterministic template — no LLM prose."""
    parts: list[str] = []

    parts.append(f"Nota {nota_id} | Farmaco: {drug_id}")

    # Score info
    if "cha2ds2vasc" in computed_scores:
        sr = computed_scores["cha2ds2vasc"]
        thr_str = str(sr.threshold) if sr.threshold is not None else "N/D"
        parts.append(
            f"CHA2DS2-VASc range [{sr.min_score},{sr.max_score}] "
            f"≥ {thr_str} (threshold). Eligible: {sr.eligible}."
        )

    # Activated rules
    active_ids = [r["rule_id"] for r in passed_rules]
    if active_ids:
        parts.append(f"Regole attivate: {', '.join(active_ids)}.")

    # Blocking rules
    if blocking_rules:
        block_ids = [r.rule_id for r in blocking_rules]
        parts.append(f"Controindicazioni: {', '.join(block_ids)}.")

    # Decision
    if reimbursement_decision:
        parts.append(f"Decisione: {reimbursement_decision}.")
    elif decision_status == "ROUTED":
        parts.append("Decisione: ROUTED (rimandato ad altra Nota).")

    return " ".join(parts)
