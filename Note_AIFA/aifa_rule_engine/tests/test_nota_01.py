"""
Integration tests for Nota 01 (gastroprotectors).
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

BASE_01 = {
    "trattamento_cronico_fans": True,
    "terapia_antiaggregante_asa": False,
    "farmaco_prescritto": "omeprazolo",
    "pregresse_emorragie_digestive": False,
    "ulcera_peptica_non_guarita": False,
    "terapia_concomitante_anticoagulanti": False,
    "terapia_concomitante_cortisonici": False,
    "eta_avanzata": False,
}


class TestNota01Scope:

    def test_fans_only_scope_pass(self, rule_index: RuleIndex):
        r = run("01", "omeprazolo", BASE_01, rule_index)
        assert r.decision_status == "FINAL"

    def test_asa_only_scope_pass(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = False
        p["terapia_antiaggregante_asa"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.decision_status == "FINAL"

    def test_neither_fans_nor_asa_non_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = False
        p["terapia_antiaggregante_asa"] = False
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_scope_unknown_fans_asa_true(self, rule_index: RuleIndex):
        """OR short-circuit: if ASA=True, FANS=None → still passes scope."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = None
        p["terapia_antiaggregante_asa"] = True
        p["eta_avanzata"] = True
        r = run("01", "omeprazolo", p, rule_index)
        # Scope should pass (OR short-circuit on ASA=True)
        assert r.reimbursement_decision == "RIMBORSABILE"
        # missing_fields_coverage should NOT include trattamento_cronico_fans
        assert "trattamento_cronico_fans" not in r.missing_fields_coverage


class TestNota01Inclusion:

    def test_pregresse_emorragie_gives_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["pregresse_emorragie_digestive"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_eta_avanzata_gives_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["eta_avanzata"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_no_risk_factor_non_rimb(self, rule_index: RuleIndex):
        r = run("01", "omeprazolo", BASE_01, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_anticoagulante_gives_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["terapia_concomitante_anticoagulanti"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    # N01_TC_V3_001: FANS, emorragie_GI=TRUE, eta_avanzata=None → RIMB; missing=[]
    def test_or_short_circuit_inclusion(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["pregresse_emorragie_digestive"] = True
        p["eta_avanzata"] = None  # missing, but OR is already TRUE
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        assert r.missing_fields_coverage == []


class TestNota01Exception:

    def test_diclofenac_misoprostolo_routes_to_66(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["pregresse_emorragie_digestive"] = True
        r = run("01", "diclofenac_misoprostolo", p, rule_index)
        assert r.decision_status == "ROUTED"
        assert r.route_to == "66"
        assert r.reimbursement_decision is None


class TestNota01Guidance:

    def test_triple_therapy_warning(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["terapia_concomitante_anticoagulanti"] = True
        p["trattamento_cronico_fans"] = True
        r = run("01", "omeprazolo", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N01_GWARN_001" in warn_ids

    # T-2.2a: eta_avanzata=TRUE → no N01_GWARN_001 (rule removed in V3.1)
    def test_no_redundant_eta_warning(self, rule_index: RuleIndex):
        p = dict(BASE_01)
        p["eta_avanzata"] = True
        r = run("01", "omeprazolo", p, rule_index)
        # N01_GWARN_001 may exist in some versions; current plan has it for FANS+anticoag
        # The "removed" rule (per V3.1 Fix 2.2) was the standalone eta_avanzata warning
        # which no longer exists. The current N01_GWARN_001 is FANS+anticoag.
        # So eta_avanzata alone must NOT trigger N01_GWARN_001.
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        # Without anticoagulant, no warning should fire
        assert "N01_GWARN_001" not in warn_ids


class TestNota01NewRiskFactors:

    def test_ulcera_peptica_non_guarita_rimb(self, rule_index: RuleIndex):
        """N01_INCL_001: ulcera_peptica_non_guarita=True → RIMBORSABILE."""
        p = dict(BASE_01)
        p["ulcera_peptica_non_guarita"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_cortisonici_rimb(self, rule_index: RuleIndex):
        """N01_INCL_001: terapia_concomitante_cortisonici=True → RIMBORSABILE."""
        p = dict(BASE_01)
        p["terapia_concomitante_cortisonici"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"


class TestNota01MissingData:

    def test_scope_both_null_non_determinabile(self, rule_index: RuleIndex):
        """FANS=null, ASA=null + emorragie=True → scope UNKNOWN but inclusion passes
        (OR short-circuit) → pending_non_det resolves to NON_DETERMINABILE at finalization."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = None
        p["terapia_antiaggregante_asa"] = None
        p["pregresse_emorragie_digestive"] = True   # inclusion passes via OR short-circuit
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"

    def test_scope_fans_null_asa_false_non_determinabile(self, rule_index: RuleIndex):
        """FANS=null, ASA=false + emorragie=True → OR(UNKNOWN, FALSE)=UNKNOWN in scope
        + inclusion passes → NON_DETERMINABILE."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = None
        p["terapia_antiaggregante_asa"] = False
        p["pregresse_emorragie_digestive"] = True   # inclusion passes via OR short-circuit
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"

    def test_inclusion_all_factors_null_non_determinabile(self, rule_index: RuleIndex):
        """FANS=true, all 5 inclusion factors null → NON_DETERMINABILE."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = True
        p["pregresse_emorragie_digestive"] = None
        p["ulcera_peptica_non_guarita"] = None
        p["terapia_concomitante_anticoagulanti"] = None
        p["terapia_concomitante_cortisonici"] = None
        p["eta_avanzata"] = None
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"


class TestNota01AsaOnlyPaths:

    def test_asa_only_emorragie_rimb(self, rule_index: RuleIndex):
        """ASA-only scope + pregresse_emorragie=True → RIMBORSABILE."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = False
        p["terapia_antiaggregante_asa"] = True
        p["pregresse_emorragie_digestive"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_asa_only_no_risk_non_rimb(self, rule_index: RuleIndex):
        """ASA-only scope + no risk factors → NON_RIMBORSABILE."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = False
        p["terapia_antiaggregante_asa"] = True
        # all risk factors remain False (from BASE_01)
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


class TestNota01AllFactorsAndDrugs:

    def test_all_factors_with_gwarn(self, rule_index: RuleIndex):
        """All 5 risk factors + FANS + anticoagulanti → RIMBORSABILE + N01_GWARN_001."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = True
        p["pregresse_emorragie_digestive"] = True
        p["ulcera_peptica_non_guarita"] = True
        p["terapia_concomitante_anticoagulanti"] = True
        p["terapia_concomitante_cortisonici"] = True
        p["eta_avanzata"] = True
        r = run("01", "omeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N01_GWARN_001" in warn_ids

    def test_esomeprazolo_asa_ulcera_rimb(self, rule_index: RuleIndex):
        """esomeprazolo + ASA scope + ulcera_peptica → RIMBORSABILE."""
        p = dict(BASE_01)
        p["trattamento_cronico_fans"] = False
        p["terapia_antiaggregante_asa"] = True
        p["ulcera_peptica_non_guarita"] = True
        r = run("01", "esomeprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_lansoprazolo_fans_cortisonici_no_gwarn(self, rule_index: RuleIndex):
        """lansoprazolo + FANS + cortisonici → RIMBORSABILE, no N01_GWARN_001 (no anticoag)."""
        p = dict(BASE_01)
        p["terapia_concomitante_cortisonici"] = True
        r = run("01", "lansoprazolo", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N01_GWARN_001" not in warn_ids
