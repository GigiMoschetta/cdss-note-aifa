"""
Integration tests for Nota 66 (NSAIDs).

Includes T-1.4a regression test for FANS+ASA warning.
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

BASE_66 = {
    "indicazione_clinica": "osteoartrosi_algica",
    "farmaco_prescritto": "ibuprofene",
    "uso_breve_durata": True,
    "seconda_linea": True,
    "ulcera_peptica_attiva_pregressa": False,
    "scompenso_cardiaco_grave": False,
    "cardiopatia_ischemica": False,
    "patologia_cerebrovascolare": False,
    "patologia_arteriosa_periferica": False,
    "scompenso_cardiaco_moderato_grave": False,
    "epatopatia": False,
    "is_coxib": False,
    "terapia_antiaggregante_asa": False,
    "dolore_acuto_moderato": False,
    "non_controllato_con_singoli": False,
    # Audit Day 2 fix F1-N66-Div#2/Div#3 ALTI: 3 nuovi campi clinician-asserted.
    # Nel paziente standard (RIMBORSABILE by default) sono tutte False.
    "abuso_alcool": False,
    "farmaci_epatotossici_concomitanti": False,
    "allergia_asa_o_fans": False,
}


class TestNota66Scope:

    def test_valid_indication(self, rule_index: RuleIndex):
        r = run("66", "ibuprofene", BASE_66, rule_index)
        assert r.decision_status == "FINAL"

    def test_invalid_indication(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["indicazione_clinica"] = "mal_di_testa"
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_connettivite_valid(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["indicazione_clinica"] = "artropatia_connettivite"
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"


class TestNota66Inclusion:

    def test_ibuprofene_rimborsabile(self, rule_index: RuleIndex):
        r = run("66", "ibuprofene", BASE_66, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_drug_not_in_list(self, rule_index: RuleIndex):
        # warfarin is not in lista_chiusa_26+pa
        r = run("66", "warfarin", BASE_66, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_nimesulide_seconda_linea(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        # GWARN_001 should fire for all nimesulide prescriptions (hepatotoxicity warning)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_001" in warn_ids

    def test_nimesulide_not_seconda_linea(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["seconda_linea"] = False
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_ibuprofene_codeina_requirements(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["dolore_acuto_moderato"] = True
        p["non_controllato_con_singoli"] = True
        p["uso_breve_durata"] = True
        r = run("66", "ibuprofene_codeina", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_ibuprofene_codeina_without_requirements(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["dolore_acuto_moderato"] = False
        r = run("66", "ibuprofene_codeina", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


class TestNota66ExclusionHard:

    def test_ulcera_peptica_non_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["ulcera_peptica_attiva_pregressa"] = True
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_scompenso_grave_non_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["scompenso_cardiaco_grave"] = True
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_coxib_cardiopatia_non_rimb(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["is_coxib"] = True
        p["cardiopatia_ischemica"] = True
        r = run("66", "celecoxib", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_coxib_no_cv_ok(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["is_coxib"] = True
        r = run("66", "celecoxib", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"


class TestNota66Warnings:

    def test_nimesulide_epatopatia_non_rimborsabile(self, rule_index: RuleIndex):
        """nimesulide + epatopatia=True → NON_RIMBORSABILE (N66_EXCL_HARD_004).
        PDF text: 'nimesulide...è controindicata nei pazienti epatopatici'
        (Nota_66 .pdf p.4, Particolari avvertenze). EXCL_HARD_004 blocks before
        GWARN_001 is evaluated (Phase 3 fires before Phase 8).
        Patched: 2026-02-26 per 06_tier2_pdf_audit_report.md."""
        p = dict(BASE_66)
        p["epatopatia"] = True
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        blocking_ids = {br.rule_id for br in r.rag_payload.blocking_rules}
        assert "N66_EXCL_HARD_004" in blocking_ids

    def test_nimesulide_gwarn001_fires_without_epatopatia(self, rule_index: RuleIndex):
        """N66_GWARN_001: nimesulide without epatopatia → general hepatotoxicity warning."""
        p = dict(BASE_66)
        p["epatopatia"] = False
        r = run("66", "nimesulide", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_001" in warn_ids

    def test_nimesulide_gwarn001_with_epatopatia_blocked(self, rule_index: RuleIndex):
        """When epatopatia=True, EXCL_HARD_004 blocks → NON_RIMBORSABILE.
        GWARN_001 may or may not fire depending on engine short-circuit behavior;
        the critical assertion is that the hard block is correct."""
        p = dict(BASE_66)
        p["epatopatia"] = True
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        blocking_ids = {br.rule_id for br in r.rag_payload.blocking_rules}
        assert "N66_EXCL_HARD_004" in blocking_ids

    def test_non_nimesulide_no_gwarn001(self, rule_index: RuleIndex):
        """Non-nimesulide drugs should NOT trigger N66_GWARN_001."""
        p = dict(BASE_66)
        r = run("66", "ibuprofene", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_001" not in warn_ids

    # T-1.4a: FANS + ASA → GUIDANCE_WARN N66_GWARN_002
    def test_fans_asa_warning(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["terapia_antiaggregante_asa"] = True
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_002" in warn_ids

    def test_fans_asa_warning_not_for_ibuprofene_codeina(self, rule_index: RuleIndex):
        """ibuprofene_codeina is NOT in lista_fans → N66_GWARN_002 should NOT fire."""
        p = dict(BASE_66)
        p["terapia_antiaggregante_asa"] = True
        p["dolore_acuto_moderato"] = True
        p["non_controllato_con_singoli"] = True
        r = run("66", "ibuprofene_codeina", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_002" not in warn_ids

    def test_no_asa_no_warning(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["terapia_antiaggregante_asa"] = False
        r = run("66", "ibuprofene", p, rule_index)
        warn_ids = [f.rule_id for f in r.clinical_flags if f.flag_type == "WARNING"]
        assert "N66_GWARN_002" not in warn_ids


class TestNota66ValidIndications:

    def test_gotta_acuta_rimb(self, rule_index: RuleIndex):
        """gotta_acuta is a valid Nota 66 indication → RIMBORSABILE."""
        p = dict(BASE_66)
        p["indicazione_clinica"] = "gotta_acuta"
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_dolore_neoplastico_rimb(self, rule_index: RuleIndex):
        """dolore_neoplastico is a valid Nota 66 indication → RIMBORSABILE."""
        p = dict(BASE_66)
        p["indicazione_clinica"] = "dolore_neoplastico"
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"


class TestNota66ExclHard003Variants:

    def test_coxib_cerebrovascolare_non_rimb(self, rule_index: RuleIndex):
        """N66_EXCL_HARD_003: is_coxib=True + patologia_cerebrovascolare=True → NON_RIMBORSABILE."""
        p = dict(BASE_66)
        p["is_coxib"] = True
        p["patologia_cerebrovascolare"] = True
        r = run("66", "etoricoxib", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_coxib_scompenso_moderato_non_rimb(self, rule_index: RuleIndex):
        """N66_EXCL_HARD_003: is_coxib=True + scompenso_cardiaco_moderato_grave=True → NON_RIMBORSABILE."""
        p = dict(BASE_66)
        p["is_coxib"] = True
        p["scompenso_cardiaco_moderato_grave"] = True
        r = run("66", "celecoxib", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_coxib_arteriosa_periferica_non_rimb(self, rule_index: RuleIndex):
        """N66_EXCL_HARD_003: is_coxib=True + patologia_arteriosa_periferica=True → NON_RIMBORSABILE."""
        p = dict(BASE_66)
        p["is_coxib"] = True
        p["patologia_arteriosa_periferica"] = True
        r = run("66", "celecoxib", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


class TestNota66OtherDrugs:

    def test_aspirina_not_in_lista_non_rimb(self, rule_index: RuleIndex):
        """aspirina not in lista_chiusa_26+pa → NON_RIMBORSABILE (N66_INCL_001)."""
        r = run("66", "aspirina", BASE_66, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"

    def test_ketoprofene_artropatia_rimb(self, rule_index: RuleIndex):
        """ketoprofene + artropatia_connettivite → RIMBORSABILE."""
        p = dict(BASE_66)
        p["indicazione_clinica"] = "artropatia_connettivite"
        r = run("66", "ketoprofene", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_meloxicam_artropatia_rimb(self, rule_index: RuleIndex):
        """meloxicam + artropatia_connettivite → RIMBORSABILE."""
        p = dict(BASE_66)
        p["indicazione_clinica"] = "artropatia_connettivite"
        r = run("66", "meloxicam", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"


class TestNota66DualWarnings:

    def test_nimesulide_epatopatia_and_asa_non_rimborsabile(self, rule_index: RuleIndex):
        """nimesulide + epatopatia=True + ASA → NON_RIMBORSABILE (N66_EXCL_HARD_004 blocks).
        The ASA combination (N66_GWARN_002) is irrelevant once the hard contraindication
        fires. EXCL_HARD_004 fires in Phase 3 before GWARN_001/GWARN_002 in Phase 8.
        Patched: 2026-02-26 per 06_tier2_pdf_audit_report.md."""
        p = dict(BASE_66)
        p["epatopatia"] = True
        p["terapia_antiaggregante_asa"] = True
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


class TestNota66MissingData:

    def test_indicazione_null_non_determinabile(self, rule_index: RuleIndex):
        """indicazione_clinica=null → NON_DETERMINABILE scope (IN(null, set) = UNKNOWN)."""
        p = dict(BASE_66)
        p["indicazione_clinica"] = None
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_DETERMINABILE"


class TestNota66NimesulideConstraints:

    def test_nimesulide_seconda_linea_false_breve_false_non_rimb(self, rule_index: RuleIndex):
        """nimesulide + seconda_linea=False + uso_breve_durata=False → NON_RIMBORSABILE (N66_INCL_002)."""
        p = dict(BASE_66)
        p["seconda_linea"] = False
        p["uso_breve_durata"] = False
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
