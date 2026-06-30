"""
Property / invariant tests.

These tests verify system-wide invariants that must hold for any input.
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

# ---------------------------------------------------------------------------
# Shared patient scenarios
# ---------------------------------------------------------------------------

NOTA_97_SCENARIOS = [
    # (label, drug_id, patient_data, expected_not)
    ("rimb_full", "apixaban", {
        "diagnosi_fanv": True, "ecg_confermato": True,
        "valutazione_clinica_eseguita": True,
        "paziente_sesso": "M", "paziente_eta": 72,
        "scompenso_cardiaco": True, "ipertensione_arteriosa": True,
        "diabete_mellito": True,
        "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
        "vfg_cockroft_gault": 85.0,
    }, "NON_RIMBORSABILE"),

    ("non_rimb_score0", "apixaban", {
        "diagnosi_fanv": True, "ecg_confermato": True,
        "valutazione_clinica_eseguita": True,
        "paziente_sesso": "M", "paziente_eta": 30,
        "scompenso_cardiaco": False, "ipertensione_arteriosa": False,
        "diabete_mellito": False, "pregresso_ictus_tia_te": False,
        "vasculopatia": False,
        "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
    }, "RIMBORSABILE"),
]


class TestPropertyGuidanceNotInCoverageTrace:
    """PROPERTY: GUIDANCE_* rules must never appear in coverage_trace."""

    def test_nota_97_guidance_not_in_trace(self, rule_index: RuleIndex):
        guidance_types = {"GUIDANCEDOSE", "GUIDANCEPREF", "GUIDANCEWARN",
                         "GUIDANCE_DOSE", "GUIDANCE_PREF", "GUIDANCE_WARN"}
        patient = {
            "diagnosi_fanv": True, "ecg_confermato": True,
            "valutazione_clinica_eseguita": True,
            "paziente_sesso": "M", "paziente_eta": 72,
            "scompenso_cardiaco": True, "ipertensione_arteriosa": True,
            "diabete_mellito": True,
            "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
            "vfg_cockroft_gault": 85.0,
            "paziente_peso_kg": 70.0, "creatinina_sierica": 0.9,
        }
        r = run("97", "apixaban", patient, rule_index)
        for entry in r.coverage_trace:
            assert "GUIDANCE" not in entry.rule_type.upper(), \
                f"GUIDANCE rule '{entry.rule_id}' found in coverage_trace"


class TestPropertyDoseOnDenial:
    """PROPERTY: NON_RIMBORSABILE → no DOSE_* flags."""

    def test_non_rimb_no_dose_flags(self, rule_index: RuleIndex):
        # score=0 → NON_RIMB (M, age=30 → no age component, all others False → score=0 < threshold=2)
        patient = {
            "diagnosi_fanv": True, "ecg_confermato": True,
            "valutazione_clinica_eseguita": True,
            "paziente_sesso": "M", "paziente_eta": 30,  # age<65 → no age component
            "scompenso_cardiaco": False, "ipertensione_arteriosa": False,
            "diabete_mellito": False, "pregresso_ictus_tia_te": False,
            "vasculopatia": False,
            "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
            "paziente_peso_kg": 55.0, "creatinina_sierica": 1.8,
        }
        r = run("97", "apixaban", patient, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        dose_flags = [
            f for f in r.clinical_flags
            if f.flag_type in {"DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"}
        ]
        assert dose_flags == [], \
            f"SAFETY: DOSE flags must be absent on NON_RIMB: {dose_flags}"


class TestPropertyRoutedDecision:
    """PROPERTY: ROUTED → reimbursement_decision is None."""

    def test_routed_null_decision(self, rule_index: RuleIndex):
        patient = {
            "trattamento_cronico_fans": True,
            "terapia_antiaggregante_asa": False,
            "pregresse_emorragie_digestive": True,
        }
        r = run("01", "diclofenac_misoprostolo", patient, rule_index)
        assert r.decision_status == "ROUTED", (
            f"Expected ROUTED for diclofenac_misoprostolo+pregresse_emorragie, got {r.decision_status}"
        )
        assert r.reimbursement_decision is None


class TestPropertyScoreRangeMonotone:
    """PROPERTY: cha2ds2vasc_range.min ≤ max."""

    def test_score_range_min_lte_max(self, rule_index: RuleIndex):
        from aifa_rule_engine.logic.derived_vars import compute_cha2ds2vasc_range
        from aifa_rule_engine.models.results import ScoreRange
        for age in [None, 30, 65, 75, 82]:
            for sesso in [None, "M", "F"]:
                for sc in [None, True, False]:
                    p = {
                        "paziente_eta": age, "paziente_sesso": sesso,
                        "scompenso_cardiaco": sc,
                        "ipertensione_arteriosa": None,
                        "diabete_mellito": None,
                        "pregresso_ictus_tia_te": None,
                        "vasculopatia": None,
                    }
                    r = compute_cha2ds2vasc_range(p)
                    assert r.min <= r.max, \
                        f"Score range min={r.min} > max={r.max} for {p}"


class TestPropertyScoreRangeGTEBoundary:
    """PROPERTY: score_range = (thr, thr) → eligibility = TRUE."""

    def test_boundary_eligible_true(self):
        from aifa_rule_engine.logic.three_valued import eval_condition
        from aifa_rule_engine.models.conditions import ScoreRangeGTENode
        from aifa_rule_engine.models.results import ScoreRange

        node = ScoreRangeGTENode(
            operator="SCORE_RANGE_GTE",
            score_range_var="cha2ds2vasc_range",
            threshold_var="cha2ds2vasc_threshold",
            anchor_note="97",
        )
        for thr in [2, 3]:
            data = {
                "cha2ds2vasc_range": ScoreRange(min=thr, max=thr),
                "cha2ds2vasc_threshold": thr,
            }
            tv, _ = eval_condition(node, data)
            from aifa_rule_engine.logic.three_valued import TruthValue
            assert tv == TruthValue.TRUE, \
                f"score_range=({thr},{thr}), threshold={thr} should be TRUE, got {tv}"


class TestPropertySafetyFalseRimbZero:
    """SAFETY: false_RIMBORSABILE = 0 for all gold standard NON_RIMB cases."""

    GOLD_NON_RIMB = [
        # Nota 97: scope fails (no diagnosis)
        ("97", "apixaban", {"diagnosi_fanv": False, "ecg_confermato": True,
                             "valutazione_clinica_eseguita": True,
                             "paziente_sesso": "M", "paziente_eta": 72,
                             "scompenso_cardiaco": True}),
        # Nota 97: score = 0 male
        ("97", "apixaban", {"diagnosi_fanv": True, "ecg_confermato": True,
                             "valutazione_clinica_eseguita": True,
                             "paziente_sesso": "M", "paziente_eta": 30,
                             "scompenso_cardiaco": False,
                             "ipertensione_arteriosa": False,
                             "diabete_mellito": False,
                             "pregresso_ictus_tia_te": False,
                             "vasculopatia": False,
                             "protesi_valvolari_meccaniche": False,
                             "fa_valvolare": False}),
        # Nota 66: invalid indication
        ("66", "ibuprofene", {"indicazione_clinica": "allergia",
                               "uso_breve_durata": True, "seconda_linea": True,
                               "ulcera_peptica_attiva_pregressa": False,
                               "scompenso_cardiaco_grave": False,
                               "cardiopatia_ischemica": False,
                               "patologia_cerebrovascolare": False,
                               "patologia_arteriosa_periferica": False,
                               "scompenso_cardiaco_moderato_grave": False,
                               "epatopatia": False, "is_coxib": False,
                               "terapia_antiaggregante_asa": False}),
    ]

    def test_false_rimb_zero(self, rule_index: RuleIndex):
        false_rimb = 0
        for nota_id, drug_id, patient_data in self.GOLD_NON_RIMB:
            r = run(nota_id, drug_id, patient_data, rule_index)
            if r.decision_status == "FINAL":
                if r.reimbursement_decision == "RIMBORSABILE":
                    false_rimb += 1
        assert false_rimb == 0, f"SAFETY VIOLATION: {false_rimb} false RIMBORSABILE cases"
