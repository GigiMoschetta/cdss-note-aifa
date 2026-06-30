"""
Unit tests for Nota 13 (Ipolipemizzanti — statine, ezetimibe, PUFA-N3).

Coverage:
  - N13_SCOPE_001:   dislipidemia + ipotiroidismo_escluso prerequisite
  - N13_INCL_001:    diet ≥3 months requirement
  - N13_EXCEPT_001:  diet bypass for molto_alto+LDL>70 or alto+LDL>100
  - N13_EXCEPT_002:  statin intolerance → ezetimibe monotherapy bypass
  - N13_PATH_001:    risk category not "basso" pathway gate
  - N13_PATH_002:    first-line therapy attempted pathway gate
  - N13_GDOSE_001:   IRC moderata + TG≥500 → DOSE_STANDARD (PUFA-N3)
  - Missing-data:    NON_DETERMINABILE for decisive unknown fields
  - Drug scope:      drug not in N13 list → NON_RIMBORSABILE
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

# ---------------------------------------------------------------------------
# Base patient profile — all criteria met for RIMBORSABILE (alto rischio)
# ---------------------------------------------------------------------------

BASE_13 = {
    "dislipidemia_diagnosticata": True,
    "ipotiroidismo_escluso": True,
    "dieta_seguita_almeno_3_mesi": True,
    "terapia_primo_livello_tentata": True,
    "risk_score_cvd_fatale_10y": 6.0,          # → alto (>5%, <10%)
    "malattia_coronarica_documentata": False,
    "pregresso_ictus_ischemico": False,
    "arteriopatia_periferica": False,
    "diabete_con_fattori_rischio_cv": False,
    "irc_moderata": False,
    "irc_grave": False,
    "in_terapia_haart": False,
    "tipo_dislipidemia_familiare": False,
    "intolleranza_statine": False,
    "colesterolo_ldl": 105.0,
    "trigliceridi": 150.0,
}


def _blocking_rule_ids(r) -> list[str]:
    """Return rule_ids whose coverage_trace outcome is NON_RIMBORSABILE."""
    return [e.rule_id for e in r.coverage_trace if e.outcome == "NON_RIMBORSABILE"]

# Clinician asserts boolean criteria
CLINICIAN_BASE = {
    "dieta_seguita_almeno_3_mesi": True,
    "terapia_primo_livello_tentata": True,
}


# ---------------------------------------------------------------------------
# Scope tests — N13_SCOPE_001
# ---------------------------------------------------------------------------

class TestNota13Scope:

    def test_valid_scope_passes(self, rule_index: RuleIndex):
        """Both scope conditions true → evaluation proceeds past scope."""
        r = run("13", "atorvastatina", BASE_13, rule_index, CLINICIAN_BASE)
        assert r.decision_status == "FINAL"

    def test_dislipidemia_not_diagnosed_non_rimb(self, rule_index: RuleIndex):
        """N13_SCOPE_001: dislipidemia_diagnosticata=False → NON_RIMBORSABILE."""
        p = dict(BASE_13)
        p["dislipidemia_diagnosticata"] = False
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N13_SCOPE_001" in _blocking_rule_ids(r)

    def test_ipotiroidismo_not_excluded_non_rimb(self, rule_index: RuleIndex):
        """N13_SCOPE_001: ipotiroidismo_escluso=False → NON_RIMBORSABILE."""
        p = dict(BASE_13)
        p["ipotiroidismo_escluso"] = False
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N13_SCOPE_001" in _blocking_rule_ids(r)

    def test_dislipidemia_unknown_non_determinabile(self, rule_index: RuleIndex):
        """N13_SCOPE_001: dislipidemia_diagnosticata=None → NON_DETERMINABILE."""
        p = dict(BASE_13)
        p["dislipidemia_diagnosticata"] = None
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"
        assert "dislipidemia_diagnosticata" in r.missing_fields_coverage

    def test_scope_evaluates_clinical_not_drug(self, rule_index: RuleIndex):
        """Nota 13 scope is clinical-only (no drug list constraint).
        Any drug passes scope if clinical preconditions are met."""
        r = run("13", "atorvastatina", BASE_13, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"


# ---------------------------------------------------------------------------
# Inclusion tests — N13_INCL_001
# ---------------------------------------------------------------------------

class TestNota13Inclusion:

    def test_diet_followed_rimborsabile(self, rule_index: RuleIndex):
        """N13_INCL_001: dieta=True → RIMBORSABILE (full path met)."""
        r = run("13", "atorvastatina", BASE_13, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_diet_not_followed_non_rimb(self, rule_index: RuleIndex):
        """N13_INCL_001: dieta=False + no bypass → NON_RIMBORSABILE.
        Uses LDL=85 (below 100) so N13_EXCEPT_001 (alto+LDL≥100) does NOT fire."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["colesterolo_ldl"] = 85.0   # < 100 → N13_EXCEPT_001 bypass does NOT trigger
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N13_INCL_001" in _blocking_rule_ids(r)

    def test_diet_unknown_non_determinabile(self, rule_index: RuleIndex):
        """N13_INCL_001: dieta=None + no bypass → NON_DETERMINABILE (decisive missing)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = None
        # Use score 3.0 (moderato) so N13_EXCEPT_001 bypass does not fire
        p["risk_score_cvd_fatale_10y"] = 3.0
        p["colesterolo_ldl"] = 105.0
        p["intolleranza_statine"] = False
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"
        assert "dieta_seguita_almeno_3_mesi" in r.missing_fields_coverage


# ---------------------------------------------------------------------------
# Exception tests — N13_EXCEPT_001 (diet bypass: high/very-high risk + LDL)
# ---------------------------------------------------------------------------

class TestNota13Except001:

    def test_molto_alto_ldl_above_70_bypasses_diet(self, rule_index: RuleIndex):
        """N13_EXCEPT_001: molto_alto + LDL=120 (≥70) + dieta=False → RIMBORSABILE."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["malattia_coronarica_documentata"] = True     # → molto_alto
        p["risk_score_cvd_fatale_10y"] = None
        p["colesterolo_ldl"] = 120.0
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_alto_ldl_above_100_bypasses_diet(self, rule_index: RuleIndex):
        """N13_EXCEPT_001: alto (score=7%) + LDL=110 (>100) + dieta=False → RIMBORSABILE."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["risk_score_cvd_fatale_10y"] = 7.0
        p["colesterolo_ldl"] = 110.0
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_molto_alto_ldl_below_70_no_bypass(self, rule_index: RuleIndex):
        """N13_EXCEPT_001: molto_alto + LDL=50 (<70) + dieta=False → NON_RIMBORSABILE (bypass not triggered)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["malattia_coronarica_documentata"] = True
        p["risk_score_cvd_fatale_10y"] = None
        p["colesterolo_ldl"] = 50.0
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_moderato_no_ldl_threshold_no_bypass(self, rule_index: RuleIndex):
        """N13_EXCEPT_001: moderato (score=3%) + dieta=False → NON_RIMBORSABILE (N13_EXCEPT_001 does not cover moderato)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["risk_score_cvd_fatale_10y"] = 3.0
        p["colesterolo_ldl"] = 150.0
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


# ---------------------------------------------------------------------------
# Exception tests — N13_EXCEPT_002 (statin intolerance → ezetimibe)
# ---------------------------------------------------------------------------

class TestNota13Except002:

    def test_statin_intolerance_ezetimibe_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_002: intolleranza=True + ezetimibe + dieta=False → RIMBORSABILE."""
        p = dict(BASE_13)
        p["intolleranza_statine"] = True
        p["dieta_seguita_almeno_3_mesi"] = False
        r = run("13", "ezetimibe", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_no_statin_intolerance_diet_missing_non_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_002: intolleranza=False + dieta=False → NON_RIMBORSABILE (bypass not triggered).
        Uses LDL=85 to prevent N13_EXCEPT_001 from firing (alto+LDL≥100 would bypass diet)."""
        p = dict(BASE_13)
        p["intolleranza_statine"] = False
        p["dieta_seguita_almeno_3_mesi"] = False
        p["colesterolo_ldl"] = 85.0   # < 100 → EXCEPT_001 does NOT fire
        r = run("13", "ezetimibe", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_statin_intolerance_statina_still_rimb(self, rule_index: RuleIndex):
        """Intolleranza to statine with a statina drug + diet met → RIMBORSABILE (statina still evaluates normally)."""
        p = dict(BASE_13)
        p["intolleranza_statine"] = True
        p["dieta_seguita_almeno_3_mesi"] = True
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        # With diet met, the path proceeds normally to RIMBORSABILE regardless of intolerance flag
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_statin_intolerance_statina_no_diet_non_rimb(self, rule_index: RuleIndex):
        """AUDIT FIX G03-01 (2026-05-29): intolleranza=True ma farmaco=statina
        (non ezetimibe) + dieta=False → NON_RIMBORSABILE. Il bypass N13_EXCEPT_002
        vale SOLO per ezetimibe in monoterapia (PDF p.4), non per qualunque farmaco
        in un paziente intollerante. Prima del fix questo caso bypassava la dieta
        producendo (erroneamente) RIMBORSABILE.
        LDL=85 (<100) per evitare che scatti il bypass N13_EXCEPT_001 (alto+LDL>100)."""
        p = dict(BASE_13)
        p["intolleranza_statine"] = True
        p["dieta_seguita_almeno_3_mesi"] = False
        p["colesterolo_ldl"] = 85.0   # < 100 → N13_EXCEPT_001 non scatta
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N13_INCL_001" in _blocking_rule_ids(r)


# ---------------------------------------------------------------------------
# Pathway tests — N13_PATH_001 (risk category not basso)
# ---------------------------------------------------------------------------

class TestNota13Path001:

    def test_basso_rischio_non_rimb(self, rule_index: RuleIndex):
        """N13_PATH_001: risk_score=0.5% → basso → NON_RIMBORSABILE."""
        p = dict(BASE_13)
        p["risk_score_cvd_fatale_10y"] = 0.5
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N13_PATH_001" in _blocking_rule_ids(r)

    def test_moderato_rischio_rimborsabile(self, rule_index: RuleIndex):
        """N13_PATH_001: risk_score=3.0% → moderato → passes PATH gate."""
        p = dict(BASE_13)
        p["risk_score_cvd_fatale_10y"] = 3.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_molto_alto_rischio_rimborsabile(self, rule_index: RuleIndex):
        """N13_PATH_001: malattia_coronarica=True → molto_alto → passes PATH gate."""
        p = dict(BASE_13)
        p["malattia_coronarica_documentata"] = True
        p["risk_score_cvd_fatale_10y"] = None
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_risk_score_unknown_non_determinabile(self, rule_index: RuleIndex):
        """N13_PATH_001: risk_score=None + no explicit molto_alto flag → NON_DETERMINABILE."""
        p = dict(BASE_13)
        p["risk_score_cvd_fatale_10y"] = None
        # All molto_alto conditions also None/False → categoria_rischio = None → UNKNOWN
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        # categoria_rischio cannot be determined → NON_DETERMINABILE
        assert r.reimbursement_decision == "NON_DETERMINABILE"


# ---------------------------------------------------------------------------
# Pathway tests — N13_PATH_002 (first-line attempted)
# ---------------------------------------------------------------------------

class TestNota13Path002:
    """V3.4 audit fix F1-N13-Div#2 BLOC: ex-PATHWAY ora GUIDANCE_WARN.
    Pre-fix: PATHWAY fail-fast su FALSE → paziente neo-diagnosticato a 1° linea
    veniva NON_RIMBORSABILE. Post-fix: WARNING informativo (rule_id N13_GWARN_001),
    decisione resta RIMBORSABILE.
    """

    def test_primo_livello_not_attempted_warning(self, rule_index: RuleIndex):
        """V3.4: terapia_primo_livello_tentata=False → RIMBORSABILE + WARNING (no longer fail-fast)."""
        p = dict(BASE_13)
        p["terapia_primo_livello_tentata"] = False
        r = run("13", "atorvastatina", p, rule_index, {"dieta_seguita_almeno_3_mesi": True})
        # Decisione non bloccata (warning informativo solo)
        assert r.reimbursement_decision == "RIMBORSABILE"
        # Warning emesso
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N13_GWARN_001" in warn_ids

    def test_primo_livello_attempted_no_warning(self, rule_index: RuleIndex):
        """V3.4: terapia_primo_livello_tentata=True → RIMBORSABILE no warning."""
        r = run("13", "atorvastatina", BASE_13, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N13_GWARN_001" not in warn_ids

    def test_primo_livello_unknown_no_block(self, rule_index: RuleIndex):
        """V3.4: terapia_primo_livello=None → RIMBORSABILE (warning UNKNOWN, no longer decisive)."""
        p = dict(BASE_13)
        p["terapia_primo_livello_tentata"] = None
        r = run("13", "atorvastatina", p, rule_index, {"dieta_seguita_almeno_3_mesi": True})
        # Pre-fix: NON_DETERMINABILE; post-fix: RIMBORSABILE (warning non blocca)
        assert r.reimbursement_decision == "RIMBORSABILE"


# ---------------------------------------------------------------------------
# Guidance dose tests — N13_GDOSE_001
# ---------------------------------------------------------------------------

class TestNota13GuidanceDose:

    def test_irc_tg_high_triggers_dose_flag(self, rule_index: RuleIndex):
        """N13_GDOSE_001: irc_moderata=True + TG=620 (≥500) → DOSE_STANDARD flag fires."""
        p = dict(BASE_13)
        p["irc_moderata"] = True
        p["trigliceridi"] = 620.0
        # Note: irc_moderata=True → categoria_rischio=molto_alto, so all path gates pass
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" in flag_ids

    def test_irc_grave_tg_high_triggers_dose_flag(self, rule_index: RuleIndex):
        """AUDIT FIX G03-03 (2026-05-29): irc_grave=True + TG=620 (≥500) →
        DOSE_STANDARD (PUFA-N3) fires. Il PDF (p.3, "insufficienza renale cronica
        moderata e grave") prevede PUFA-N3 sia per IRC moderata SIA grave; prima
        la regola copriva solo irc_moderata."""
        p = dict(BASE_13)
        p["irc_grave"] = True
        p["trigliceridi"] = 620.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" in flag_ids

    def test_irc_but_tg_below_500_no_flag(self, rule_index: RuleIndex):
        """N13_GDOSE_001: irc_moderata=True + TG=400 (<500) → flag does NOT fire."""
        p = dict(BASE_13)
        p["irc_moderata"] = True
        p["trigliceridi"] = 400.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" not in flag_ids

    def test_tg_high_no_irc_no_flag(self, rule_index: RuleIndex):
        """N13_GDOSE_001: TG=620 + irc_moderata=False → flag does NOT fire (both conditions required)."""
        p = dict(BASE_13)
        p["irc_moderata"] = False
        p["trigliceridi"] = 620.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" not in flag_ids


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestNota13SafetyInvariants:

    def test_non_rimb_no_dose_flags(self, rule_index: RuleIndex):
        """Invariant I-1: NON_RIMBORSABILE → no DOSE flags emitted."""
        p = dict(BASE_13)
        p["dislipidemia_diagnosticata"] = False
        p["irc_moderata"] = True
        p["trigliceridi"] = 620.0
        r = run("13", "atorvastatina", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        dose_flags = [f for f in r.clinical_flags if f.flag_type in {"DOSE_STANDARD", "DOSE_RIDOTTA", "DOSE_CONTROINDICATA"}]
        assert dose_flags == []

    def test_full_missing_data_non_determinabile(self, rule_index: RuleIndex):
        """All decisive fields missing → NON_DETERMINABILE with populated missing_fields_coverage."""
        r = run("13", "atorvastatina", {}, rule_index)
        # G02-F01 fix (2026-05-29): con tutti i campi decisivi assenti l'esito è
        # univocamente NON_DETERMINABILE (lo scope dislipidemia_diagnosticata=None
        # → UNKNOWN). L'assertion duale precedente non discriminava i due outcome.
        assert r.reimbursement_decision == "NON_DETERMINABILE"
        assert "dislipidemia_diagnosticata" in r.missing_fields_coverage


# ---------------------------------------------------------------------------
# Boundary tests — N13_EXCEPT_001 (LDL thresholds)
# ---------------------------------------------------------------------------

class TestNota13BoundaryLDL:

    def test_alto_ldl_exactly_100_no_bypass_non_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: alto + LDL=100 exactly → NON_RIMBORSABILE.
        PDF (nota-13.pdf p.5): '>100 mg/dL' (strict GT). GT(100,100)=False → no bypass.
        Patched: 2026-02-28 per improvement plan v1.1.2."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["risk_score_cvd_fatale_10y"] = 7.0   # → alto
        p["colesterolo_ldl"] = 100.0            # GT(100, 100) = False
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_alto_ldl_101_bypass_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: alto + LDL=101 → RIMBORSABILE. GT(101,100)=True → bypass fires."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["risk_score_cvd_fatale_10y"] = 7.0   # → alto
        p["colesterolo_ldl"] = 101.0            # GT(101, 100) = True
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_alto_ldl_99_no_bypass_non_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: alto + LDL=99 → NON_RIMBORSABILE (GT(99,100)=False)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["risk_score_cvd_fatale_10y"] = 7.0
        p["colesterolo_ldl"] = 99.0
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_molto_alto_ldl_exactly_70_no_bypass_non_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: molto_alto + LDL=70 exactly → NON_RIMBORSABILE.
        PDF (nota-13.pdf p.5): '>70 mg/dL' (strict GT). GT(70,70)=False → no bypass.
        Patched: 2026-02-26 per 06_tier2_pdf_audit_report.md (N13-015)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["malattia_coronarica_documentata"] = True  # → molto_alto
        p["risk_score_cvd_fatale_10y"] = None
        p["colesterolo_ldl"] = 70.0                  # GT(70, 70) = False → no bypass
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_molto_alto_ldl_71_bypass_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: molto_alto + LDL=71 → RIMBORSABILE. GT(71,70)=True → bypass fires."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["malattia_coronarica_documentata"] = True
        p["risk_score_cvd_fatale_10y"] = None
        p["colesterolo_ldl"] = 71.0                  # GT(71, 70) = True → bypass
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_molto_alto_ldl_69_no_bypass_non_rimb(self, rule_index: RuleIndex):
        """N13_EXCEPT_001 boundary: molto_alto + LDL=69 → NON_RIMBORSABILE (GT(69,70)=False)."""
        p = dict(BASE_13)
        p["dieta_seguita_almeno_3_mesi"] = False
        p["malattia_coronarica_documentata"] = True
        p["risk_score_cvd_fatale_10y"] = None
        p["colesterolo_ldl"] = 69.0
        r = run("13", "atorvastatina", p, rule_index, {"terapia_primo_livello_tentata": True})
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


# ---------------------------------------------------------------------------
# Molto alto risk variants — N13_PATH_001
# ---------------------------------------------------------------------------

class TestNota13MoltoAltoVariants:

    def test_molto_alto_via_ictus_rimb(self, rule_index: RuleIndex):
        """molto_alto via pregresso_ictus_ischemico=True → RIMBORSABILE."""
        p = dict(BASE_13)
        p["pregresso_ictus_ischemico"] = True
        p["risk_score_cvd_fatale_10y"] = None
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_molto_alto_via_arteriopatia_rimb(self, rule_index: RuleIndex):
        """molto_alto via arteriopatia_periferica=True → RIMBORSABILE."""
        p = dict(BASE_13)
        p["arteriopatia_periferica"] = True
        p["risk_score_cvd_fatale_10y"] = None
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_molto_alto_via_dislipidemia_familiare_rimb(self, rule_index: RuleIndex):
        """molto_alto via tipo_dislipidemia_familiare=True → RIMBORSABILE."""
        p = dict(BASE_13)
        p["tipo_dislipidemia_familiare"] = True
        p["risk_score_cvd_fatale_10y"] = None
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"


# ---------------------------------------------------------------------------
# GDOSE_001 boundary tests
# ---------------------------------------------------------------------------

class TestNota13GdoseBoundary:

    def test_tg_exactly_500_triggers_flag(self, rule_index: RuleIndex):
        """N13_GDOSE_001 boundary: irc_moderata=True + TG=500 exactly → flag fires (GTE(500,500)=True)."""
        p = dict(BASE_13)
        p["irc_moderata"] = True
        p["trigliceridi"] = 500.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        assert r.reimbursement_decision == "RIMBORSABILE"
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" in flag_ids

    def test_tg_499_no_flag(self, rule_index: RuleIndex):
        """N13_GDOSE_001 boundary: irc_moderata=True + TG=499 → flag does NOT fire (GTE(499,500)=False)."""
        p = dict(BASE_13)
        p["irc_moderata"] = True
        p["trigliceridi"] = 499.0
        r = run("13", "atorvastatina", p, rule_index, CLINICIAN_BASE)
        flag_ids = [f.rule_id for f in r.clinical_flags]
        assert "N13_GDOSE_001" not in flag_ids
