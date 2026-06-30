"""
Integration + regression tests for Nota 97 (anticoagulants in FANV).

Includes all V3.2 regression tests from Section K of the plan.
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

# ── Baseline patient (all required fields, RIMBORSABILE by default) ────────

BASE_97 = {
    "diagnosi_fanv": True,
    "ecg_confermato": True,
    "valutazione_clinica_eseguita": True,
    "paziente_sesso": "M",
    "paziente_eta": 72,
    "scompenso_cardiaco": True,
    "ipertensione_arteriosa": True,
    "diabete_mellito": True,
    "pregresso_ictus_tia_te": False,
    "vasculopatia": False,
    "protesi_valvolari_meccaniche": False,
    "fa_valvolare": False,
    "vfg_cockroft_gault": 85.0,
    "paziente_peso_kg": 75.0,
    "creatinina_sierica": 0.9,
    # Audit Day 2 fix F1-N97-Div#2 BLOC: 4 nuove controindicazioni Allegato 2.
    # Nel paziente standard (RIMBORSABILE by default) sono tutte False.
    "emorragia_maggiore_in_atto": False,
    "diatesi_emorragica_congenita": False,
    "gravidanza": False,
    "ipersensibilita_farmaco": False,
}


def fanv_apixaban(extra: dict | None = None):
    p = dict(BASE_97)
    if extra:
        p.update(extra)
    return p


# ── Scope tests ─────────────────────────────────────────────────────────────

class TestScope:
    def test_scope_missing_ecg(self, rule_index: RuleIndex):
        p = fanv_apixaban({"ecg_confermato": False})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_scope_missing_diagnosis(self, rule_index: RuleIndex):
        p = fanv_apixaban({"diagnosi_fanv": False})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_scope_all_present(self, rule_index: RuleIndex):
        r = run("97", "apixaban", fanv_apixaban(), rule_index)
        assert r.reimbursement_decision != "NON_RIMBORSABILE"  # passes scope


# ── EXCL_HARD tests ──────────────────────────────────────────────────────────

class TestExclHard:
    def test_doac_protesi_meccaniche(self, rule_index: RuleIndex):
        p = fanv_apixaban({"protesi_valvolari_meccaniche": True})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_doac_fa_valvolare(self, rule_index: RuleIndex):
        p = fanv_apixaban({"fa_valvolare": True})
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_warfarin_protesi_meccaniche_ok(self, rule_index: RuleIndex):
        # Warfarin is NOT a DOAC → excl_hard_001/002 do not apply
        p = fanv_apixaban({"protesi_valvolari_meccaniche": True,
                           "scompenso_cardiaco": True,
                           "ipertensione_arteriosa": True,
                           "diabete_mellito": True})
        r = run("97", "warfarin", p, rule_index)
        # Warfarin passes exclusions
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_dabigatran_vfg_below30(self, rule_index: RuleIndex):
        # T-1.2 family: VFG=25 → NON_RIMB
        p = fanv_apixaban({"vfg_cockroft_gault": 25.0})
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_apixaban_vfg_below30_ok(self, rule_index: RuleIndex):
        # Apixaban has no EXCL_HARD for VFG<30 (only warning)
        p = fanv_apixaban({"vfg_cockroft_gault": 12.0})
        r = run("97", "apixaban", p, rule_index)
        # Should not be denied by excl_hard for apixaban
        assert r.reimbursement_decision == "RIMBORSABILE"


# ── Pathway: CHA2DS2-VASc ────────────────────────────────────────────────────

class TestPathwayCha2ds2vasc:

    # T-1.1a: M, score=2 → RIMBORSABILE (V3.2 threshold correction ≥2)
    def test_m_score2_rimborsabile(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_sesso": "M",
            "paziente_eta": 30,       # no age component
            "scompenso_cardiaco": True,   # +1
            "ipertensione_arteriosa": True, # +1
            "diabete_mellito": False,
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    # T-1.1b: M, score=1 → NON_RIMBORSABILE
    def test_m_score1_non_rimborsabile(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_sesso": "M",
            "paziente_eta": 30,
            "scompenso_cardiaco": True,   # +1 only
            "ipertensione_arteriosa": False,
            "diabete_mellito": False,
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    # T-1.1c: sex missing → NON_DETERMINABILE, missing = ["paziente_sesso"]
    def test_sex_missing_non_determinabile(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_sesso": None,
            "paziente_eta": 30,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "pregresso_ictus_tia_te": True,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"
        assert "paziente_sesso" in r.missing_fields_coverage

    # T-1.1d: M, straddle → NON_DETERMINABILE + missing_components
    def test_range_straddles_non_determinabile(self, rule_index: RuleIndex):
        # age=30 (no age component), scompenso=TRUE(1), diabete=None(1 UNKNOWN)
        # range=[1,2], threshold=2 → straddle → NON_DET
        p = fanv_apixaban({
            "paziente_sesso": "M",
            "paziente_eta": 30,
            "scompenso_cardiaco": True,  # +1
            "ipertensione_arteriosa": False,
            "diabete_mellito": None,     # UNKNOWN +1
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"
        assert "diabete_mellito" in r.missing_fields_coverage

    def test_f_score3_rimborsabile(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_sesso": "F",
            "paziente_eta": 30,
            "scompenso_cardiaco": True,    # +1
            "ipertensione_arteriosa": True, # +1
            "diabete_mellito": True,        # +1
            # Sc(F): +1
            # Total: 4
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_f_score2_non_rimborsabile(self, rule_index: RuleIndex):
        # F: scompenso(1) + Sc(F=1) = 2 < threshold=3
        p = fanv_apixaban({
            "paziente_sesso": "F",
            "paziente_eta": 30,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": False,
            "diabete_mellito": False,
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


# ── Guidance Dose ─────────────────────────────────────────────────────────────

class TestGuidanceDose:

    # T-1.2a: dabigatran η≥80 → DOSE_RIDOTTA 110mg
    def test_dabigatran_eta80_dose_ridotta(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 82,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 65.0,
        })
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        dose_flags = [f for f in r.clinical_flags if f.flag_type == "DOSE_RIDOTTA"]
        assert any("N97_GDOSE_001" == f.rule_id for f in dose_flags), \
            f"Expected N97_GDOSE_001 in {[f.rule_id for f in dose_flags]}"

    # T-1.2d: verapamil standalone (any age <75) → DOSE_RIDOTTA 110mg
    def test_dabigatran_verapamil_standalone_dose_ridotta(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 65,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "uso_verapamil": True,
            "vfg_cockroft_gault": 70.0,
        })
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        dose_flags = [f for f in r.clinical_flags if "DOSE_RIDOTTA" in f.flag_type]
        assert any("N97_GDOSE_001" == f.rule_id for f in dose_flags)

    # T-1.2b: 75-80 + VFG=40 + no verapamil → WARNING (not DOSE)
    def test_dabigatran_75_80_ckd_warning_not_dose(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 77,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 40.0,
            "uso_verapamil": None,  # NOT relevant for N97_GWARN_004
        })
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        dose_flags = [f for f in r.clinical_flags if f.flag_type in {
            "DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"
        }]
        # N97_GDOSE_001 should NOT fire (age=77 not ≥80, no verapamil)
        assert not any("N97_GDOSE_001" == f.rule_id for f in dose_flags)
        # N97_GWARN_004 should fire
        warn_flags = [f for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert any("N97_GWARN_004" == f.rule_id for f in warn_flags)

    # T-1.2c: age=70 → no caso-per-caso warning
    def test_dabigatran_age70_no_warning(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 70,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 40.0,
            "uso_verapamil": None,
        })
        r = run("97", "dabigatran", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N97_GWARN_004" not in warn_ids
        dose_ids = [f.rule_id for f in r.clinical_flags if "DOSE" in f.flag_type]
        assert "N97_GDOSE_001" not in dose_ids

    # T-1.3a: rivaroxaban VFG=22 → DOSE + WARN (both N97_GDOSE_005 + N97_GWARN_005)
    def test_rivaroxaban_vfg22_dose_and_warn(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 22.0,
        })
        r = run("97", "rivaroxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_005" in flag_ids, f"Expected N97_GDOSE_005 in {flag_ids}"
        assert "N97_GWARN_005" in flag_ids, f"Expected N97_GWARN_005 in {flag_ids}"

    # T-1.3b: rivaroxaban VFG=35 → DOSE only, no cautela warning
    def test_rivaroxaban_vfg35_dose_only(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 35.0,
        })
        r = run("97", "rivaroxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_005" in flag_ids
        assert "N97_GWARN_005" not in flag_ids

    # T-2.1a: apixaban COUNT_GEQ 2/3 with UNKNOWN
    def test_apixaban_count_geq_2of3_with_unknown(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 82,           # TRUE
            "paziente_peso_kg": 55,       # TRUE
            "creatinina_sierica": None,   # UNKNOWN
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_002" in flag_ids
        # missing_fields_guidance should NOT include creatinina (threshold already met)
        assert "creatinina_sierica" not in r.missing_fields_guidance

    # T-2.1b: apixaban 1/3 with UNKNOWN → no dose flag
    def test_apixaban_count_geq_1of3_no_dose(self, rule_index: RuleIndex):
        p = fanv_apixaban({
            "paziente_eta": 65,        # FALSE
            "paziente_peso_kg": 70,    # FALSE
            "creatinina_sierica": None, # UNKNOWN → max=1 < 2 → FALSE
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
        })
        r = run("97", "apixaban", p, rule_index)
        dose_ids = [f.rule_id for f in r.clinical_flags if "DOSE" in f.flag_type]
        assert "N97_GDOSE_002" not in dose_ids


# ── Safety invariants ────────────────────────────────────────────────────────

class TestSafetyInvariants:

    def test_dose_suppressed_on_non_rimb(self, rule_index: RuleIndex):
        # T-V3_005: M, score=0 → NON_RIMB; apixaban, eta=82 → DOSE suppressed
        # Use age=30 (no age component) so score=0 for M (threshold=2) → NON_RIMB
        p = fanv_apixaban({
            "paziente_sesso": "M",
            "paziente_eta": 30,       # age<65 → no age component → score=0
            "scompenso_cardiaco": False,
            "ipertensione_arteriosa": False,
            "diabete_mellito": False,
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
            "paziente_peso_kg": 55.0,    # these would trigger DOSE_RIDOTTA for apixaban
            "creatinina_sierica": 1.8,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        # Safety: no DOSE flags when denied
        dose_flags = [
            f for f in r.clinical_flags
            if f.flag_type in {"DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"}
        ]
        assert dose_flags == [], f"DOSE flags must be suppressed on NON_RIMB: {dose_flags}"

    def test_safety_false_rimb_zero(self, rule_index: RuleIndex):
        """SAFETY: NON_RIMBORSABILE cases must never produce RIMBORSABILE."""
        # Score=0, M → NON_RIMB
        p = fanv_apixaban({
            "paziente_sesso": "M",
            "paziente_eta": 30,
            "scompenso_cardiaco": False,
            "ipertensione_arteriosa": False,
            "diabete_mellito": False,
            "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
        })
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE", \
            "SAFETY VIOLATION: false RIMBORSABILE for score=0 M"

    def test_guidance_not_in_coverage_trace(self, rule_index: RuleIndex):
        """PROPERTY: GUIDANCE_* rules must never appear in coverage_trace."""
        r = run("97", "apixaban", fanv_apixaban(), rule_index)
        guidance_ids = {"N97_GDOSE_001", "N97_GDOSE_002", "N97_GDOSE_003",
                       "N97_GDOSE_004", "N97_GDOSE_005", "N97_GPREF_001",
                       "N97_GPREF_002", "N97_GPREF_003", "N97_GWARN_001",
                       "N97_GWARN_002", "N97_GWARN_003", "N97_GWARN_004",
                       "N97_GWARN_005"}
        trace_ids = {e.rule_id for e in r.coverage_trace}
        overlap = trace_ids & guidance_ids
        assert overlap == set(), f"GUIDANCE rules in coverage_trace: {overlap}"

    def test_t22a_n01_gwarn_001_is_guidance_warn_not_blocking(self, rule_index: RuleIndex):
        """T-2.2a: N01_GWARN_001 (triplice terapia AC+FANS+PPI) must be GUIDANCE_WARN
        — not a blocking rule. Audit fix 2026-05-06: previous test asserted the rule
        was removed (with `or True` tautology that never failed). The rule is in fact
        a legitimate normative warning per Nota 01 PDF p.3 and must remain, but its
        type must stay GUIDANCE_WARN so it never blocks rimborsabilità.
        """
        rule_by_id = {r.rule_id: r for r in rule_index.rules}
        rule = rule_by_id.get("N01_GWARN_001")
        assert rule is not None, "N01_GWARN_001 must exist (PDF p.3 normative warning)"
        assert rule.rule_type == "GUIDANCE_WARN", (
            f"N01_GWARN_001 must remain GUIDANCE_WARN (got {rule.rule_type}) — "
            "promoting it to blocking would invalidate Nota 01 rimborsabilità tests"
        )


# ── V3 addition: short-circuit missing ──────────────────────────────────────

class TestShortCircuitMissing:

    def test_excl_hard_dabigatran_vfg25_no_missing(self, rule_index: RuleIndex):
        # N97_TC_V3_004: dabigatran VFG=25 → NON_RIMB; missing_fields=[]
        p = fanv_apixaban({
            "vfg_cockroft_gault": 25.0,
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
        })
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert r.missing_fields_coverage == []

    def test_dose_conflict_single_flag(self, rule_index: RuleIndex):
        # T-V3_006: rivaroxaban, VFG=20 → only one DOSE_RIDOTTA flag after conflict resolution
        p = fanv_apixaban({
            "scompenso_cardiaco": True,
            "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "vfg_cockroft_gault": 20.0,
        })
        r = run("97", "rivaroxaban", p, rule_index)
        dose_flags = [f for f in r.clinical_flags if "DOSE" in f.flag_type]
        # Should have at most 1 DOSE flag after conflict resolution
        assert len(dose_flags) <= 1, \
            f"Expected ≤1 DOSE flag after conflict resolution: {dose_flags}"


# ── Edoxaban tests ────────────────────────────────────────────────────────────

class TestNota97Edoxaban:

    def test_edoxaban_standard_rimb(self, rule_index: RuleIndex):
        """edoxaban + standard profile → RIMBORSABILE (no exclusions, score=3 M ≥2)."""
        r = run("97", "edoxaban", fanv_apixaban(), rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_edoxaban_vfg35_gdose004(self, rule_index: RuleIndex):
        """N97_GDOSE_004: edoxaban + VFG=35 (BETWEEN 15-50) → RIMBORSABILE + N97_GDOSE_004."""
        p = fanv_apixaban({"vfg_cockroft_gault": 35.0})
        r = run("97", "edoxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_004" in flag_ids

    def test_edoxaban_peso58_gdose004(self, rule_index: RuleIndex):
        """N97_GDOSE_004: edoxaban + peso=58 kg (LTE(58,60)) → RIMBORSABILE + N97_GDOSE_004."""
        p = fanv_apixaban({"paziente_peso_kg": 58.0, "vfg_cockroft_gault": 80.0})
        r = run("97", "edoxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_004" in flag_ids

    def test_edoxaban_vfg12_gwarn002_gpref002(self, rule_index: RuleIndex):
        """N97_GWARN_002 + N97_GPREF_002: edoxaban + VFG=12 (<15) → both warnings fire."""
        p = fanv_apixaban({"vfg_cockroft_gault": 12.0})
        r = run("97", "edoxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GWARN_002" in flag_ids
        assert "N97_GPREF_002" in flag_ids


# ── Apixaban renal dose/warn tests ───────────────────────────────────────────

class TestNota97ApixabanRenal:

    def test_apixaban_vfg22_gdose003(self, rule_index: RuleIndex):
        """N97_GDOSE_003: apixaban + VFG=22 (BETWEEN 15-29) → RIMBORSABILE + N97_GDOSE_003."""
        p = fanv_apixaban({"vfg_cockroft_gault": 22.0})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_003" in flag_ids

    def test_apixaban_vfg12_gwarn001_gpref002(self, rule_index: RuleIndex):
        """N97_GWARN_001 + N97_GPREF_002: apixaban + VFG=12 (<15) → both warnings fire."""
        p = fanv_apixaban({"vfg_cockroft_gault": 12.0})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GWARN_001" in flag_ids
        assert "N97_GPREF_002" in flag_ids


# ── Guidance Preference tests ─────────────────────────────────────────────────

class TestNota97GprefAll:

    def test_gpref001_warfarin_ttr_below_70(self, rule_index: RuleIndex):
        """N97_GPREF_001: warfarin + ttr_sotto_70=True → RIMBORSABILE + N97_GPREF_001."""
        p = fanv_apixaban({"ttr_sotto_70": True})
        r = run("97", "warfarin", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GPREF_001" in flag_ids

    def test_gpref002_interazioni_farmacologiche(self, rule_index: RuleIndex):
        """N97_GPREF_002: apixaban + interazioni_farmacologiche_doac=True → N97_GPREF_002 fires."""
        p = fanv_apixaban({"interazioni_farmacologiche_doac": True})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GPREF_002" in flag_ids

    def test_gpref003_pregressa_emorragia_intracranica(self, rule_index: RuleIndex):
        """N97_GPREF_003: apixaban + pregressa_emorragia_intracranica=True → N97_GPREF_003 fires."""
        p = fanv_apixaban({"pregressa_emorragia_intracranica": True})
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GPREF_003" in flag_ids


# ── Boundary tests ────────────────────────────────────────────────────────────

class TestNota97Boundaries:

    def test_dabigatran_vfg30_not_blocked(self, rule_index: RuleIndex):
        """N97_EXCL_HARD_003 boundary: dabigatran VFG=30 → LT(30,30)=False → RIMBORSABILE."""
        p = fanv_apixaban({"vfg_cockroft_gault": 30.0})
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_rivaroxaban_vfg49_gdose005(self, rule_index: RuleIndex):
        """N97_GDOSE_005 boundary: rivaroxaban VFG=49 (upper bound of BETWEEN 30-49) → N97_GDOSE_005 fires."""
        p = fanv_apixaban({"vfg_cockroft_gault": 49.0})
        r = run("97", "rivaroxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_005" in flag_ids

    def test_rivaroxaban_vfg50_no_gdose005(self, rule_index: RuleIndex):
        """N97_GDOSE_005 boundary: rivaroxaban VFG=50 → above BETWEEN(30-49), no dose flag."""
        p = fanv_apixaban({"vfg_cockroft_gault": 50.0})
        r = run("97", "rivaroxaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N97_GDOSE_005" not in flag_ids
