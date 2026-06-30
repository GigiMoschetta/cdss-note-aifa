"""
Request-time evaluation pipeline — Phases 0-10.

Phase 0:  Input validation + derived variables
Phase 1:  SCOPE evaluation
Phase 2:  EXCEPTION evaluation (ROUTE/BYPASS before EXCL_HARD)
Phase 3:  EXCL_HARD evaluation (fail-fast on TRUE)
Phase 4:  INCLUSION evaluation (fail-fast on FALSE)
Phase 5:  PATHWAY evaluation (fail-fast on FALSE)
Phase 6:  GUIDANCE_DOSE evaluation
Phase 7:  GUIDANCE_PREF evaluation
Phase 8:  GUIDANCE_WARN evaluation
Phase 9:  Guidance conflict resolution
Phase 10: Finalization + invariant enforcement
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from ..logic.derived_vars import compute_derived_variables
from ..logic.three_valued import TruthValue, eval_condition
from ..models.results import (
    AuditEntry,
    ClinicalFlag,
    CoverageTraceEntry,
    EvaluationResult,
    ScoreRange,
    ScoreRangeResult,
)
from ..models.rules import (
    BaseRule,
    ExceptionRule,
    ExclHardRule,
    GuidanceDoseRule,
    GuidancePrefRule,
    GuidanceWarnRule,
    InclusionRule,
    PathwayRule,
    ScopeRule,
)
from .rag_builder import build_rag_payload
from .rule_loader import RuleIndex

log = logging.getLogger(__name__)

# Audit V3-M2 (2026-05-06) considered importing ENGINE_VERSION from the package
# single source of truth. Reverted because the import path is brittle when the
# evaluator is loaded by tooling whose working directory contains a sibling
# directory named "aifa_rule_engine" without __init__.py (e.g. orchestrator
# tests collected from Note_AIFA/ shadow the editable install). The literal is
# kept aligned by a regression test that asserts equality with __init__.py.
ENGINE_VERSION = "3.4.0"

DOSE_FLAG_PRIORITY: dict[str, int] = {
    "DOSE_CONTROINDICATA": 3,
    "DOSE_RIDOTTA": 2,
    "DOSE_STANDARD": 1,
}


# ---------------------------------------------------------------------------
# Coverage phase descriptor (refactor RE-M1)
#
# Phases SCOPE / EXCL_HARD / INCLUSION / PATHWAY share an identical evaluation
# pattern: iterate rules, write audit, branch on Kleene outcome (fail-fast on
# the phase-specific failure truth-value, accumulate UNKNOWN as pending). The
# pattern was previously copy-pasted four times (~170 LOC). The descriptor
# below + the dispatcher loop in `evaluate()` collapse the duplication.
#
# EXCEPTION is intentionally NOT modelled here — its outcome map
# (ROUTE/BYPASS/NON_RIMB/DEFER) is genuinely different from the other phases.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _CoveragePhase:
    """One row of the coverage-phase dispatch table."""

    name: str                                       # human label (debug only)
    phase: int                                      # phase index (1..5)
    fail_tv: TruthValue                             # TV that triggers fail-fast
    blocking_tv: Literal["FALSE", "TRUE"]           # value to pass to _finalize_non_rimb
    skip_if_bypassed: bool                          # True only for INCLUSION


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate(
    nota_id: str,
    drug_id: str,
    patient_data: dict[str, Any],
    clinician_asserted: dict[str, Any],
    rule_index: RuleIndex,
) -> EvaluationResult:
    """Run the full evaluation pipeline and return an EvaluationResult."""

    # ---- Phase 0: merge inputs + derived variables ----
    merged = dict(patient_data)
    # Bug fix RE-D1 (audit): record any clinician_asserted override in the
    # audit_trail so that subsequent reviewers can see when a clinician's
    # assertion overrode a value from patient_data (medical-legal trail).
    overrides: list[tuple[str, Any, Any]] = []
    for k, v in (clinician_asserted or {}).items():
        if k in patient_data and patient_data[k] != v:
            overrides.append((k, patient_data[k], v))
    merged.update(clinician_asserted)           # clinician_asserted takes precedence
    merged["farmaco"] = drug_id                 # inject drug as synthetic field

    enriched = compute_derived_variables(merged)

    # Pipeline state
    coverage_trace: list[CoverageTraceEntry] = []
    audit_trail: list[AuditEntry] = []
    # Emit override marker entries (RE-D1)
    for field, old, new in overrides:
        audit_trail.append(AuditEntry(
            rule_id=f"CLINICIAN_OVERRIDE::{field}",
            rule_type="OVERRIDE",
            truth_value="TRUE",
            phase=0,
            note=f"clinician_asserted overrode patient_data: {field}={old!r} → {new!r}",
        ))
    clinical_flags: list[ClinicalFlag] = []
    missing_fields_coverage: frozenset[str] = frozenset()
    missing_fields_guidance: frozenset[str] = frozenset()
    pending_non_det = False
    bypassed: set[str] = set()

    rules = rule_index.rules_for_nota(nota_id)

    # Separate by type
    scope_rules     = [r for r in rules if isinstance(r, ScopeRule)]
    excl_hard_rules = [r for r in rules if isinstance(r, ExclHardRule)]
    exception_rules = [r for r in rules if isinstance(r, ExceptionRule)]
    inclusion_rules = [r for r in rules if isinstance(r, InclusionRule)]
    pathway_rules   = [r for r in rules if isinstance(r, PathwayRule)]
    dose_rules      = [r for r in rules if isinstance(r, GuidanceDoseRule)]
    pref_rules      = [r for r in rules if isinstance(r, GuidancePrefRule)]
    warn_rules      = [r for r in rules if isinstance(r, GuidanceWarnRule)]

    # Coverage phases that share the iter-eval-branch pattern.
    # EXCEPTION is handled separately because its outcome map is non-uniform.
    SCOPE_PHASE = _CoveragePhase("SCOPE", 1, TruthValue.FALSE, "FALSE", False)
    EXCL_PHASE = _CoveragePhase("EXCL_HARD", 3, TruthValue.TRUE, "TRUE", False)
    INCL_PHASE = _CoveragePhase("INCLUSION", 4, TruthValue.FALSE, "FALSE", True)
    PATH_PHASE = _CoveragePhase("PATHWAY", 5, TruthValue.FALSE, "FALSE", False)

    def _run_coverage_phase(spec: _CoveragePhase, ruleset: list[BaseRule]):
        """Generic dispatcher for SCOPE/EXCL_HARD/INCLUSION/PATHWAY phases.

        Mutates `coverage_trace`, `audit_trail`, `pending_non_det`,
        `missing_fields_coverage` via closure. Returns an EvaluationResult
        when the phase fails (caller must propagate); None when the phase
        completed without triggering a denial.
        """
        nonlocal pending_non_det, missing_fields_coverage
        for rule in ruleset:
            if spec.skip_if_bypassed and rule.rule_id in bypassed:
                _record_audit(
                    audit_trail, rule, TruthValue.TRUE, spec.phase,
                    frozenset(), note="BYPASSED",
                )
                continue
            tv, missing = eval_condition(rule.condition, enriched)
            _record_audit(audit_trail, rule, tv, spec.phase, missing)

            if tv == spec.fail_tv:
                entry = _trace_entry(
                    rule, tv, "NON_RIMBORSABILE", spec.phase, enriched, missing,
                )
                coverage_trace.append(entry)
                return _finalize_non_rimb(
                    nota_id, drug_id, enriched, coverage_trace, audit_trail,
                    clinical_flags, missing_fields_coverage, missing_fields_guidance,
                    rule_index, blocking_rule=rule, blocking_tv=spec.blocking_tv,
                )

            if tv == TruthValue.UNKNOWN:
                pending_non_det = True
                missing_fields_coverage = missing_fields_coverage | missing
                entry = _trace_entry(
                    rule, tv, "UNKNOWN_PENDING", spec.phase, enriched, missing,
                )
            else:
                entry = _trace_entry(
                    rule, tv, "PROCEED", spec.phase, enriched, missing,
                )
            coverage_trace.append(entry)
        return None

    # ---- Phase 1: SCOPE ----
    if (denial := _run_coverage_phase(SCOPE_PHASE, scope_rules)) is not None:
        return denial

    # ---- Phase 2: EXCEPTION (ROUTE/BYPASS before EXCL_HARD) ----
    for rule in exception_rules:
        tv, missing = eval_condition(rule.condition, enriched)
        _record_audit(audit_trail, rule, tv, 2, missing)

        if tv == TruthValue.TRUE:
            if rule.outcome_if_true == "ROUTE":
                entry = _trace_entry(rule, tv, "ROUTE", 2, enriched, missing)
                coverage_trace.append(entry)
                return _finalize_routed(
                    nota_id, drug_id, enriched, coverage_trace, audit_trail,
                    rule, rule_index,
                )
            elif rule.outcome_if_true == "NON_RIMBORSABILE":
                entry = _trace_entry(rule, tv, "NON_RIMBORSABILE", 2, enriched, missing)
                coverage_trace.append(entry)
                return _finalize_non_rimb(
                    nota_id, drug_id, enriched, coverage_trace, audit_trail,
                    clinical_flags, missing_fields_coverage, missing_fields_guidance,
                    rule_index, blocking_rule=rule, blocking_tv="TRUE",
                )
            elif rule.outcome_if_true == "BYPASS":
                for bypass_id in rule.bypasses:
                    bypassed.add(bypass_id)
                entry = _trace_entry(rule, tv, "BYPASS", 2, enriched, missing)
                coverage_trace.append(entry)
                continue
            elif rule.outcome_if_true == "DEFER":
                entry = _trace_entry(rule, tv, "ROUTE", 2, enriched, missing)
                coverage_trace.append(entry)
                return _finalize_routed(
                    nota_id, drug_id, enriched, coverage_trace, audit_trail,
                    rule, rule_index,
                )
        elif tv == TruthValue.UNKNOWN:
            pending_non_det = True
            missing_fields_coverage = missing_fields_coverage | missing
            entry = _trace_entry(rule, tv, "UNKNOWN_PENDING", 2, enriched, missing)
            coverage_trace.append(entry)
        else:
            entry = _trace_entry(rule, tv, "PROCEED", 2, enriched, missing)
            coverage_trace.append(entry)

    # ---- Phase 3: EXCL_HARD (fail-fast on TRUE) ----
    if (denial := _run_coverage_phase(EXCL_PHASE, excl_hard_rules)) is not None:
        return denial

    # ---- Phase 4: INCLUSION (fail-fast on FALSE; honors `bypassed`) ----
    if (denial := _run_coverage_phase(INCL_PHASE, inclusion_rules)) is not None:
        return denial

    # ---- Phase 5: PATHWAY (fail-fast on FALSE) ----
    if (denial := _run_coverage_phase(PATH_PHASE, pathway_rules)) is not None:
        return denial

    # ---- Phase 6: GUIDANCE_DOSE ----
    for rule in dose_rules:
        tv, missing = eval_condition(rule.condition, enriched)
        _record_audit(audit_trail, rule, tv, 6, missing)
        if tv == TruthValue.TRUE:
            flag = _make_dose_flag(rule, enriched)
            clinical_flags.append(flag)
        elif tv == TruthValue.UNKNOWN:
            missing_fields_guidance = missing_fields_guidance | missing

    # ---- Phase 7: GUIDANCE_PREF ----
    for rule in pref_rules:
        tv, missing = eval_condition(rule.condition, enriched)
        _record_audit(audit_trail, rule, tv, 7, missing)
        if tv == TruthValue.TRUE:
            flag = ClinicalFlag(
                rule_id=rule.rule_id,
                flag_type="PREFERENCE",
                detail=rule.detail,
                facts_used=_gather_facts(rule, enriched),
                anchor=rule.normative_anchor,
            )
            clinical_flags.append(flag)
        elif tv == TruthValue.UNKNOWN:
            missing_fields_guidance = missing_fields_guidance | missing

    # ---- Phase 8: GUIDANCE_WARN ----
    for rule in warn_rules:
        tv, missing = eval_condition(rule.condition, enriched)
        _record_audit(audit_trail, rule, tv, 8, missing)
        if tv == TruthValue.TRUE:
            flag = ClinicalFlag(
                rule_id=rule.rule_id,
                flag_type="WARNING",
                detail=rule.detail,
                facts_used=_gather_facts(rule, enriched),
                anchor=rule.normative_anchor,
            )
            clinical_flags.append(flag)
        elif tv == TruthValue.UNKNOWN:
            missing_fields_guidance = missing_fields_guidance | missing

    # ---- Phase 9: Guidance conflict resolution ----
    clinical_flags, audit_trail = _resolve_dose_conflicts(clinical_flags, audit_trail)

    # ---- Phase 10: Finalization ----
    if pending_non_det:
        decision = "NON_DETERMINABILE"
    else:
        decision = "RIMBORSABILE"

    # Invariant I-1: Dose-on-Denial suppression
    if decision == "NON_RIMBORSABILE":
        # (Can't happen here since NON_RIMB returns early, but guard anyway)
        clinical_flags = [
            f for f in clinical_flags
            if f.flag_type not in {"DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"}
        ]
        for flag in clinical_flags:
            flag.informational_only = True
    elif decision == "NON_DETERMINABILE":
        # Keep DOSE flags but warn guidance is uncertain
        pass

    # Compute score objects for RagPayload
    computed_scores = _build_computed_scores(enriched)

    rag_payload = build_rag_payload(
        decision_status="FINAL",
        reimbursement_decision=decision,
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        missing_fields_coverage=list(sorted(missing_fields_coverage)),
        computed_scores=computed_scores,
        nota_id=nota_id,
        drug_id=drug_id,
    )

    return EvaluationResult(
        schema_version="3.3",
        decision_status="FINAL",
        reimbursement_decision=decision,  # type: ignore[arg-type]
        nota_evaluated=nota_id,
        drug_evaluated=drug_id,
        clinical_flags=clinical_flags,
        missing_fields_coverage=sorted(missing_fields_coverage),
        missing_fields_guidance=sorted(missing_fields_guidance),
        rag_payload=rag_payload,
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        engine_version=ENGINE_VERSION,
        rule_catalog_version=rule_index.catalog_version(nota_id),
        evaluation_timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Finalization helpers
# ---------------------------------------------------------------------------

def _finalize_non_rimb(
    nota_id: str,
    drug_id: str,
    enriched: dict[str, Any],
    coverage_trace: list[CoverageTraceEntry],
    audit_trail: list[AuditEntry],
    clinical_flags: list[ClinicalFlag],
    missing_fields_coverage: frozenset[str],
    missing_fields_guidance: frozenset[str],
    rule_index: RuleIndex,
    blocking_rule: BaseRule,
    blocking_tv: str,
) -> EvaluationResult:
    """Finalize a NON_RIMBORSABILE decision (Invariant I-1: suppress DOSE flags)."""
    # Suppress all DOSE flags
    cleaned_flags = [
        f for f in clinical_flags
        if f.flag_type not in {"DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"}
    ]
    # Mark remaining guidance as informational_only
    for flag in cleaned_flags:
        flag.informational_only = True

    computed_scores = _build_computed_scores(enriched)

    rag_payload = build_rag_payload(
        decision_status="FINAL",
        reimbursement_decision="NON_RIMBORSABILE",
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        missing_fields_coverage=sorted(missing_fields_coverage),
        computed_scores=computed_scores,
        nota_id=nota_id,
        drug_id=drug_id,
    )

    return EvaluationResult(
        schema_version="3.3",
        decision_status="FINAL",
        reimbursement_decision="NON_RIMBORSABILE",
        nota_evaluated=nota_id,
        drug_evaluated=drug_id,
        clinical_flags=cleaned_flags,
        missing_fields_coverage=sorted(missing_fields_coverage),
        missing_fields_guidance=sorted(missing_fields_guidance),
        rag_payload=rag_payload,
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        engine_version=ENGINE_VERSION,
        rule_catalog_version=rule_index.catalog_version(nota_id),
        evaluation_timestamp=datetime.now(UTC),
    )


def _finalize_routed(
    nota_id: str,
    drug_id: str,
    enriched: dict[str, Any],
    coverage_trace: list[CoverageTraceEntry],
    audit_trail: list[AuditEntry],
    rule: ExceptionRule,
    rule_index: RuleIndex,
) -> EvaluationResult:
    computed_scores = _build_computed_scores(enriched)

    rag_payload = build_rag_payload(
        decision_status="ROUTED",
        reimbursement_decision=None,
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        missing_fields_coverage=[],
        computed_scores=computed_scores,
        nota_id=nota_id,
        drug_id=drug_id,
    )

    return EvaluationResult(
        schema_version="3.3",
        decision_status="ROUTED",
        reimbursement_decision=None,
        nota_evaluated=nota_id,
        drug_evaluated=drug_id,
        route_to=rule.route_to_nota,
        route_reason=rule.description_it,
        clinical_flags=[],
        missing_fields_coverage=[],
        missing_fields_guidance=[],
        rag_payload=rag_payload,
        coverage_trace=coverage_trace,
        audit_trail=audit_trail,
        engine_version=ENGINE_VERSION,
        rule_catalog_version=rule_index.catalog_version(nota_id),
        evaluation_timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Phase 9: Guidance conflict resolution
# ---------------------------------------------------------------------------

def _resolve_dose_conflicts(
    clinical_flags: list[ClinicalFlag],
    audit_trail: list[AuditEntry],
) -> tuple[list[ClinicalFlag], list[AuditEntry]]:
    """Per drug: keep only the most conservative DOSE flag."""
    dose_flags: list[ClinicalFlag] = []
    non_dose_flags: list[ClinicalFlag] = []

    for flag in clinical_flags:
        if flag.flag_type in DOSE_FLAG_PRIORITY:
            dose_flags.append(flag)
        else:
            non_dose_flags.append(flag)

    if len(dose_flags) <= 1:
        return clinical_flags, audit_trail

    # Resolve all DOSE flags as one group (per-drug evaluation).
    best_flag = max(dose_flags, key=lambda f: DOSE_FLAG_PRIORITY.get(f.flag_type, 0))
    suppressed = [f for f in dose_flags if f is not best_flag]

    # Bug fix RE-B4 (audit): preserve concurrent justifications.
    # Previously the suppressed flags were dropped → clinician saw a single
    # rationale even when multiple parallel rules supported the same dose.
    # Now we attach all SAME-PRIORITY anchors (e.g. another DOSE_RIDOTTA from
    # a different criterion) to best_flag.additional_anchors.
    for sup in suppressed:
        # Only collapse same-priority concurrent rationales (don't promote
        # lower-priority "DOSE_STANDARD" to additional anchor of "DOSE_RIDOTTA")
        if DOSE_FLAG_PRIORITY.get(sup.flag_type, 0) == DOSE_FLAG_PRIORITY.get(best_flag.flag_type, 0):
            best_flag.additional_anchors.append(sup.anchor)
            best_flag.additional_rule_ids.append(sup.rule_id)

    for suppressed_flag in suppressed:
        msg = (
            f"DOSE conflict resolution: suppressed {suppressed_flag.flag_type} "
            f"({suppressed_flag.rule_id}) in favour of {best_flag.flag_type} "
            f"({best_flag.rule_id})"
        )
        same_priority = (
            DOSE_FLAG_PRIORITY.get(suppressed_flag.flag_type, 0)
            == DOSE_FLAG_PRIORITY.get(best_flag.flag_type, 0)
        )
        if same_priority:
            msg += " — anchor preserved in additional_anchors"
        log.warning(msg)
        audit_trail.append(AuditEntry(
            rule_id=suppressed_flag.rule_id,
            rule_type="GUIDANCE_DOSE",
            truth_value="TRUE",
            phase=9,
            note=f"SUPPRESSED: {msg}",
        ))

    return [best_flag] + non_dose_flags, audit_trail


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _build_computed_scores(
    enriched: dict[str, Any],
) -> dict[str, ScoreRangeResult]:
    """Build computed_scores dict for RagPayload."""
    from ..models.rules import NormativeAnchor

    scores: dict[str, ScoreRangeResult] = {}

    score_range: ScoreRange | None = enriched.get("cha2ds2vasc_range")
    threshold: int | None = enriched.get("cha2ds2vasc_threshold")

    if score_range is not None:
        from .._resolve_tv import _score_eligible
        eligible = _score_eligible(score_range, threshold)
        scores["cha2ds2vasc"] = ScoreRangeResult(
            score_name="CHA2DS2-VASc",
            min_score=score_range.min,
            max_score=score_range.max,
            threshold=threshold,
            eligible=eligible.value,
            missing_components=list(score_range.unknown_components),
            anchor=NormativeAnchor(
                pdf_file="nota-97.pdf",
                page=3,
                section="Percorso C",
                excerpt="CHA2DS2-VASc threshold ≥2 M / ≥3 F (OCR-corrected)",
            ),
        )

    return scores


# ---------------------------------------------------------------------------
# Trace / audit helpers
# ---------------------------------------------------------------------------

def _trace_entry(
    rule: BaseRule,
    tv: TruthValue,
    outcome: str,
    phase: int,
    enriched: dict[str, Any],
    missing: frozenset[str],
) -> CoverageTraceEntry:
    return CoverageTraceEntry(
        rule_id=rule.rule_id,
        rule_type=type(rule).__name__.replace("Rule", "").upper(),
        truth_value=tv.value,
        outcome=outcome,
        phase=phase,
        facts_used=_gather_facts(rule, enriched),
        anchor=rule.normative_anchor,
        missing_fields=sorted(missing),
    )


def _record_audit(
    audit_trail: list[AuditEntry],
    rule: BaseRule,
    tv: TruthValue,
    phase: int,
    missing: frozenset[str],
    note: str = "",
) -> None:
    audit_trail.append(AuditEntry(
        rule_id=rule.rule_id,
        rule_type=type(rule).__name__.replace("Rule", "").upper(),
        truth_value=tv.value,
        phase=phase,
        missing_fields=sorted(missing),
        note=note,
    ))


def _gather_facts(rule: BaseRule, enriched: dict[str, Any]) -> dict[str, Any]:
    """Collect values of variables referenced by this rule.

    Bug fix RE-B2: previously filtered out keys ending in '_range' or '_threshold'
    which left CHA2DS2-VASc PATH_001 with facts_used = {} (empty audit trail on
    the most decisive rule of Nota 97). Now we keep them, but render structured
    objects (ScoreRange) as a compact dict for JSON serialization.

    `inferred_variables` is a proper Pydantic field set during rule_loader S4;
    no more `getattr` with silent default that would mask refactor regressions.
    """
    inferred: frozenset[str] = rule.inferred_variables
    out: dict[str, Any] = {}
    for k in sorted(inferred):
        v = enriched.get(k)
        # ScoreRange or other dataclasses → dict
        if hasattr(v, "model_dump"):
            out[k] = v.model_dump()
        elif hasattr(v, "__dict__") and not isinstance(v, (int, float, str, bool, list, dict)):
            try:
                out[k] = {kk: getattr(v, kk) for kk in v.__dict__ if not kk.startswith("_")}
            except Exception:
                out[k] = str(v)
        else:
            out[k] = v
    return out


def _make_dose_flag(rule: GuidanceDoseRule, enriched: dict[str, Any]) -> ClinicalFlag:
    return ClinicalFlag(
        rule_id=rule.rule_id,
        flag_type=rule.flag_type,
        detail=rule.detail,
        facts_used=_gather_facts(rule, enriched),
        anchor=rule.normative_anchor,
    )
