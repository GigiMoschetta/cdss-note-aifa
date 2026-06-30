"""
V3.4 audit fix regression tests.

Specific tests for the 5 BLOCCANTE fixes applied during the V3.4 audit (Day 1-3):
1. F1-N97-Div#2 BLOC: 4 controindicazioni assolute Allegato 2 Nota 97
2. F1-N66-Div#1 BLOC: drug list (rimossi ketorolac/dexketoprofene; aggiunti amtolmetina_guacile/nabumetone)
3. F1-N13-Div#1 BLOC: compute_categoria_rischio refactor (IRC moderata + dislip. familiari → alto)
4. F1-N13-Div#2 BLOC: step-care PATHWAY → GUIDANCE_WARN
5. F1-N66-Div#2 ALTO: nimesulide cofattori (epatopatia ∨ alcool ∨ farmaci_epatotossici)
6. F1-N66-Div#3 ALTO: allergia ASA/FANS

Each test references both the audit finding ID and the PDF source.
"""
import pytest

from aifa_rule_engine.engine.rule_loader import RuleIndex
from tests.conftest import run

# ── Baseline patient — RIMBORSABILE for Nota 97 with all V3.4 new fields False ──
BASE_97 = {
    "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
    "paziente_sesso": "M", "paziente_eta": 72,
    "scompenso_cardiaco": True, "ipertensione_arteriosa": True, "diabete_mellito": True,
    "pregresso_ictus_tia_te": False, "vasculopatia": False,
    "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
    "vfg_cockroft_gault": 85.0, "paziente_peso_kg": 75.0, "creatinina_sierica": 0.9,
    # V3.4 new fields
    "emorragia_maggiore_in_atto": False,
    "diatesi_emorragica_congenita": False,
    "gravidanza": False,
    "ipersensibilita_farmaco": False,
}

BASE_66 = {
    "indicazione_clinica": "osteoartrosi_algica",
    "uso_breve_durata": True, "seconda_linea": True,
    "ulcera_peptica_attiva_pregressa": False,
    "scompenso_cardiaco_grave": False,
    "cardiopatia_ischemica": False, "patologia_cerebrovascolare": False,
    "patologia_arteriosa_periferica": False, "scompenso_cardiaco_moderato_grave": False,
    "epatopatia": False,
    "terapia_antiaggregante_asa": False,
    "dolore_acuto_moderato": False, "non_controllato_con_singoli": False,
    # V3.4 new fields
    "abuso_alcool": False,
    "farmaci_epatotossici_concomitanti": False,
    "allergia_asa_o_fans": False,
}


def _blocking_ids(result) -> set[str]:
    return {br.rule_id for br in result.rag_payload.blocking_rules}


# ── F1-N97-Div#2 BLOC: 4 controindicazioni assolute Allegato 2 Nota 97 ──

class TestV34_N97_Allegato2:
    """V3.4 fix F1-N97-Div#2 BLOC.

    PDF nota-97-all-2.pdf p.2: 4 condizioni che 'sconsigliano fortemente l'inizio
    di una terapia anticoagulante con AVK o NAO/DOAC' — ora EXCL_HARD."""

    def test_emorragia_in_atto_blocks_apixaban(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["emorragia_maggiore_in_atto"] = True
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_EXCL_HARD_ALL2_EMORRAGIA" in _blocking_ids(r)

    def test_emorragia_in_atto_blocks_warfarin(self, rule_index: RuleIndex):
        # Should also block AVK (PDF: "AVK o NAO/DOAC")
        p = dict(BASE_97)
        p["emorragia_maggiore_in_atto"] = True
        r = run("97", "warfarin", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_EXCL_HARD_ALL2_EMORRAGIA" in _blocking_ids(r)

    def test_diatesi_emorragica_blocks(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["diatesi_emorragica_congenita"] = True
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_EXCL_HARD_ALL2_DIATESI" in _blocking_ids(r)

    def test_gravidanza_blocks(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["paziente_sesso"] = "F"
        p["paziente_eta"] = 32
        p["gravidanza"] = True
        r = run("97", "warfarin", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_EXCL_HARD_ALL2_GRAVIDANZA" in _blocking_ids(r)

    def test_ipersensibilita_blocks(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["ipersensibilita_farmaco"] = True
        r = run("97", "dabigatran", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_EXCL_HARD_ALL2_IPERSENSIBILITA" in _blocking_ids(r)


# ── F1-N66-Div#1 BLOC: drug list ──

class TestV34_N66_DrugList:
    """V3.4 fix F1-N66-Div#1 BLOC.
    PDF Nota_66.pdf p.2 lista chiusa: amtolmetina_guacile e nabumetone IN, ketorolac e dexketoprofene OUT."""

    def test_amtolmetina_guacile_in_list(self, rule_index: RuleIndex):
        # In V3.4 amtolmetina_guacile is a valid Nota 66 drug.
        p = dict(BASE_66)
        r = run("66", "amtolmetina_guacile", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_nabumetone_in_list(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        r = run("66", "nabumetone", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_ketorolac_NOT_in_list(self, rule_index: RuleIndex):
        # Pre-V3.4: was RIMBORSABILE (bug). Post-V3.4: NON_RIMBORSABILE.
        p = dict(BASE_66)
        r = run("66", "ketorolac", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_INCL_001" in _blocking_ids(r)

    def test_dexketoprofene_NOT_in_list(self, rule_index: RuleIndex):
        # Pre-V3.4: was RIMBORSABILE (bug). Post-V3.4: NON_RIMBORSABILE.
        p = dict(BASE_66)
        r = run("66", "dexketoprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_INCL_001" in _blocking_ids(r)


# ── F1-N66-Div#2 ALTO: nimesulide cofattori ──

class TestV34_N66_NimesulideCofattori:
    """V3.4 fix F1-N66-Div#2 ALTO.
    PDF p.4: 'controindicata nei pazienti epatopatici, in quelli con storia di
    abuso di alcool e negli assuntori di altri farmaci epatotossici'."""

    def test_nimesulide_alcool_blocks(self, rule_index: RuleIndex):
        # Pre-V3.4: passed (only epatopatia checked). Post-V3.4: NON_RIMB.
        p = dict(BASE_66)
        p["abuso_alcool"] = True
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_EXCL_HARD_004" in _blocking_ids(r)

    def test_nimesulide_farmaci_epatotossici_blocks(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["farmaci_epatotossici_concomitanti"] = True
        r = run("66", "nimesulide", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_EXCL_HARD_004" in _blocking_ids(r)

    def test_nimesulide_only_alcool_NOT_other_drug(self, rule_index: RuleIndex):
        # Alcool alone shouldn't block ibuprofene (rule is nimesulide-specific)
        p = dict(BASE_66)
        p["abuso_alcool"] = True
        r = run("66", "ibuprofene", p, rule_index)
        # ibuprofene + alcool: not blocked by N66_EXCL_HARD_004 (nimesulide-specific)
        # — but still has indicazione valida
        assert r.reimbursement_decision == "RIMBORSABILE"


# ── F1-N66-Div#3 ALTO: allergia ASA/FANS ──

class TestV34_N66_AllergiaFANS:
    """V3.4 fix F1-N66-Div#3 ALTO.
    PDF p.4: 'controindicati nei soggetti con anamnesi positiva per allergia
    ad aspirina o a un altro FANS'."""

    def test_allergia_blocks_ibuprofene(self, rule_index: RuleIndex):
        p = dict(BASE_66)
        p["allergia_asa_o_fans"] = True
        r = run("66", "ibuprofene", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_EXCL_HARD_005" in _blocking_ids(r)

    def test_allergia_blocks_celecoxib(self, rule_index: RuleIndex):
        # Anche i COXIB sono controindicati per cross-reactivity ASA
        p = dict(BASE_66)
        p["allergia_asa_o_fans"] = True
        # Bypass scompenso/ischemia checks for COXIB
        p["cardiopatia_ischemica"] = False
        r = run("66", "celecoxib", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N66_EXCL_HARD_005" in _blocking_ids(r)


# ── F1-N13-Div#1 BLOC: classificazione rischio ──
# (test esistenti in test_derived_vars.py V3.4 already cover this — see
# test_alto_irc_moderata, test_alto_dislipidemia_familiare, test_haart_no_classification)


# ── F1-N13-Div#2 BLOC: step-care GUIDANCE_WARN ──
# (test esistenti in test_nota_13.py V3.4 — TestNota13Path002 refactored)


# ── Documented interpretive choice: CHA2DS2-VASc threshold (F1-N97-Div#1) ──

class TestV34_CHA2DS2_Interpretation:
    """V3.4 documented choice F1-N97-Div#1.

    PDF letterale Nota 97 p.3 usa '>' strict ('>2 se maschi'); il sistema
    implementa '≥' (allineamento ESC/RCP). Decisione documentata.
    Questo test valida il comportamento corrente; se in futuro si decide
    di switchare a '>' strict, il test va aggiornato."""

    def test_male_score_2_eligible_ESC_interpretation(self, rule_index: RuleIndex):
        # M score=2 (HTN+CHF) → ≥2 → eligible per V3.4 ESC interpretation
        p = dict(BASE_97)
        p["paziente_eta"] = 60  # no age component
        p["scompenso_cardiaco"] = True
        p["ipertensione_arteriosa"] = True
        p["diabete_mellito"] = False
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_male_score_1_NOT_eligible(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["paziente_eta"] = 60
        p["scompenso_cardiaco"] = False
        p["ipertensione_arteriosa"] = True  # only 1 component
        p["diabete_mellito"] = False
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"
        assert "N97_PATH_001" in _blocking_ids(r)

    def test_female_score_3_eligible(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["paziente_sesso"] = "F"  # +1 (Sc)
        p["paziente_eta"] = 60
        p["scompenso_cardiaco"] = True
        p["ipertensione_arteriosa"] = True  # → score 3
        p["diabete_mellito"] = False
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "RIMBORSABILE"

    def test_female_score_2_NOT_eligible(self, rule_index: RuleIndex):
        p = dict(BASE_97)
        p["paziente_sesso"] = "F"  # +1
        p["paziente_eta"] = 60
        p["scompenso_cardiaco"] = False
        p["ipertensione_arteriosa"] = True  # only +1, total 2
        p["diabete_mellito"] = False
        r = run("97", "apixaban", p, rule_index)
        assert r.reimbursement_decision == "NON_RIMBORSABILE"


class TestV3M2EngineVersionDrift:
    """
    Audit V3-M2 (2026-05-06): the canonical ENGINE_VERSION lives in
    aifa_rule_engine/__init__.py. evaluator.py duplicates the literal because
    importing it back is brittle when tests are collected from a cwd that
    contains a sibling directory of the same name without __init__.py
    (e.g. Note_AIFA/aifa_rule_engine/ shadows the editable install during
    orchestrator test collection). This regression test asserts the two
    literals stay in sync; bump them both whenever the engine version changes.
    """

    def test_engine_version_matches_package(self):
        from aifa_rule_engine import ENGINE_VERSION as PKG
        from aifa_rule_engine.engine.evaluator import ENGINE_VERSION as ENG
        assert PKG == ENG, (
            f"ENGINE_VERSION drift: aifa_rule_engine={PKG!r} vs "
            f"aifa_rule_engine.engine.evaluator={ENG!r}. "
            "Bump both literals together."
        )
