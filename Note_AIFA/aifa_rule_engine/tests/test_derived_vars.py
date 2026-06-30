"""
Unit tests for derived variable computation.

Covers: cha2ds2vasc_range, threshold, apixaban_riduzione_count,
        categoria_rischio.
"""
import pytest

from aifa_rule_engine.logic.derived_vars import (
    compute_apixaban_riduzione_count,
    compute_categoria_rischio,
    compute_cha2ds2vasc_range,
    compute_cha2ds2vasc_threshold,
    compute_derived_variables,
)
from aifa_rule_engine.logic.three_valued import TruthValue
from aifa_rule_engine.models.results import ScoreRange

T = TruthValue.TRUE
F = TruthValue.FALSE
U = TruthValue.UNKNOWN


# ---------------------------------------------------------------------------
# cha2ds2vasc_range
# ---------------------------------------------------------------------------

class TestCha2ds2vascRange:

    def _patient(self, **kwargs):
        base = {
            "scompenso_cardiaco": None,
            "ipertensione_arteriosa": None,
            "diabete_mellito": None,
            "pregresso_ictus_tia_te": None,
            "vasculopatia": None,
            "paziente_sesso": None,
            "paziente_eta": None,
        }
        base.update(kwargs)
        return base

    def test_all_true_male_age75(self):
        p = self._patient(
            scompenso_cardiaco=True,
            ipertensione_arteriosa=True,
            diabete_mellito=True,
            pregresso_ictus_tia_te=True,
            vasculopatia=True,
            paziente_sesso="M",  # +0
            paziente_eta=75,     # A2: +2
        )
        r = compute_cha2ds2vasc_range(p)
        # C(1)+H(1)+D(1)+S2(2)+V(1)+A2(2) = 8
        assert r.min == 8
        assert r.max == 8
        assert r.unknown_components == []

    def test_all_true_female_age65_74(self):
        p = self._patient(
            scompenso_cardiaco=True,
            ipertensione_arteriosa=True,
            diabete_mellito=True,
            pregresso_ictus_tia_te=True,
            vasculopatia=True,
            paziente_sesso="F",  # Sc: +1
            paziente_eta=70,     # A: +1
        )
        r = compute_cha2ds2vasc_range(p)
        # C(1)+H(1)+D(1)+S2(2)+V(1)+Sc(1)+A(1) = 8
        assert r.min == 8
        assert r.max == 8

    def test_partial_unknown(self):
        p = self._patient(
            scompenso_cardiaco=True,  # +1
            ipertensione_arteriosa=False,
            diabete_mellito=None,      # UNKNOWN +1
            pregresso_ictus_tia_te=False,
            vasculopatia=False,
            paziente_sesso="M",
            paziente_eta=72,  # A component +1
        )
        r = compute_cha2ds2vasc_range(p)
        assert r.min == 2   # scompenso(1) + A(1)
        assert r.max == 3   # + diabete(1)
        assert "diabete_mellito" in r.unknown_components

    def test_age_none_contributes_max2(self):
        p = self._patient(
            scompenso_cardiaco=True,  # +1
            ipertensione_arteriosa=False,
            diabete_mellito=False,
            pregresso_ictus_tia_te=False,
            vasculopatia=False,
            paziente_sesso="M",
            paziente_eta=None,  # UNKNOWN → max +2
        )
        r = compute_cha2ds2vasc_range(p)
        assert r.min == 1   # scompenso only
        assert r.max == 3   # + max age contribution (2)
        assert "paziente_eta" in r.unknown_components

    def test_age_none_does_not_over_inflate(self):
        # V3.3 Patch 4 — age=None should add max 2 (A2), not 3 (A2+A)
        # All other components set to False to isolate age contribution
        p = self._patient(
            paziente_eta=None, paziente_sesso="M",
            scompenso_cardiaco=False,
            ipertensione_arteriosa=False,
            diabete_mellito=False,
            pregresso_ictus_tia_te=False,
            vasculopatia=False,
        )
        r = compute_cha2ds2vasc_range(p)
        # Only age contributes (sex=M → 0), max = 2 (not 3)
        assert r.max == 2

    def test_age_under65_contributes_zero(self):
        p = self._patient(
            scompenso_cardiaco=False,
            ipertensione_arteriosa=False,
            diabete_mellito=False,
            pregresso_ictus_tia_te=False,
            vasculopatia=False,
            paziente_sesso="M",
            paziente_eta=30,
        )
        r = compute_cha2ds2vasc_range(p)
        assert r.min == 0
        assert r.max == 0

    def test_min_lte_max_invariant(self):
        """PROPERTY: min ≤ max always holds."""
        for age in [None, 30, 65, 75, 82]:
            for sesso in [None, "M", "F"]:
                for scompenso in [None, True, False]:
                    p = self._patient(
                        paziente_eta=age, paziente_sesso=sesso,
                        scompenso_cardiaco=scompenso,
                        diabete_mellito=None, ipertensione_arteriosa=None,
                        pregresso_ictus_tia_te=None, vasculopatia=None,
                    )
                    r = compute_cha2ds2vasc_range(p)
                    assert r.min <= r.max


# ---------------------------------------------------------------------------
# cha2ds2vasc_threshold
# ---------------------------------------------------------------------------

class TestCha2ds2vascThreshold:
    def test_male(self):
        assert compute_cha2ds2vasc_threshold({"paziente_sesso": "M"}) == 2

    def test_female(self):
        assert compute_cha2ds2vasc_threshold({"paziente_sesso": "F"}) == 3

    def test_none(self):
        assert compute_cha2ds2vasc_threshold({"paziente_sesso": None}) is None

    def test_missing(self):
        assert compute_cha2ds2vasc_threshold({}) is None


# ---------------------------------------------------------------------------
# apixaban_riduzione_count (COUNT_GEQ)
# ---------------------------------------------------------------------------

class TestApixabanRiduzioneCount:

    def test_all_three_true(self):
        p = {"paziente_eta": 82, "paziente_peso_kg": 55, "creatinina_sierica": 1.8}
        tv, missing = compute_apixaban_riduzione_count(p)
        assert tv == T
        assert missing == frozenset()

    def test_two_true_one_false(self):
        p = {"paziente_eta": 82, "paziente_peso_kg": 55, "creatinina_sierica": 1.0}
        tv, missing = compute_apixaban_riduzione_count(p)
        assert tv == T

    def test_one_true_two_false(self):
        p = {"paziente_eta": 82, "paziente_peso_kg": 70, "creatinina_sierica": 1.0}
        tv, missing = compute_apixaban_riduzione_count(p)
        assert tv == F

    def test_two_true_one_unknown(self):
        # T-2.1a: eta=82(T), peso=55(T), creat=None(U) → 2 known ≥ 2 → TRUE
        p = {"paziente_eta": 82, "paziente_peso_kg": 55, "creatinina_sierica": None}
        tv, missing = compute_apixaban_riduzione_count(p)
        assert tv == T
        assert missing == frozenset()  # no missing needed (already ≥ threshold)

    def test_one_false_one_false_one_unknown(self):
        # T-2.1b: eta=65(F), peso=70(F), creat=None(U) → max=1 < 2 → FALSE
        p = {"paziente_eta": 65, "paziente_peso_kg": 70, "creatinina_sierica": None}
        tv, missing = compute_apixaban_riduzione_count(p)
        assert tv == F

    def test_boundary_inclusive_eta_80(self):
        # V3.3 Patch 6: GTE → boundary η=80 is TRUE
        p = {"paziente_eta": 80, "paziente_peso_kg": 55, "creatinina_sierica": 1.0}
        tv, _ = compute_apixaban_riduzione_count(p)
        assert tv == T  # eta(T)+peso(T) = 2 ≥ 2

    def test_boundary_inclusive_peso_60(self):
        # LTE → boundary peso=60 is TRUE
        p = {"paziente_eta": 75, "paziente_peso_kg": 60, "creatinina_sierica": 1.8}
        tv, _ = compute_apixaban_riduzione_count(p)
        assert tv == T  # peso(T)+creat(T) = 2 ≥ 2

    def test_boundary_inclusive_creat_1_5(self):
        # GTE → boundary creat=1.5 is TRUE
        p = {"paziente_eta": 82, "paziente_peso_kg": 70, "creatinina_sierica": 1.5}
        tv, _ = compute_apixaban_riduzione_count(p)
        assert tv == T  # eta(T)+creat(T) = 2 ≥ 2


# ---------------------------------------------------------------------------
# categoria_rischio
# ---------------------------------------------------------------------------

class TestCategoriaRischio:

    def test_molto_alto_coronarica(self):
        p = {"malattia_coronarica_documentata": True}
        assert compute_categoria_rischio(p) == "molto_alto"

    def test_molto_alto_ictus(self):
        p = {"pregresso_ictus_ischemico": True}
        assert compute_categoria_rischio(p) == "molto_alto"

    def test_molto_alto_irc_grave(self):
        p = {"irc_grave": True}
        assert compute_categoria_rischio(p) == "molto_alto"

    # All-flags-explicit baseline: when CV flags are all explicitly False
    # (not None), the score-based classifier runs deterministically.
    _FLAGS_ALL_FALSE = {
        "malattia_coronarica_documentata": False,
        "pregresso_ictus_ischemico": False,
        "arteriopatia_periferica": False,
        "diabete_con_fattori_rischio_cv": False,
        "irc_grave": False,
        "tipo_dislipidemia_familiare": False,
        "irc_moderata": False,
    }

    def test_alto_score5(self):
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 5.0}
        assert compute_categoria_rischio(p) == "alto"

    # V3.4 audit Day 2 fix F1-N13-Div#3 ALTO: aggiunta categoria "medio"
    # (PDF p.6 verbatim: "score >1% e <4% rischio medio").
    def test_moderato_score4(self):
        # PDF p.1 tab + p.6 prosa: 4-5% è "moderato" (target LDL <115)
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 4.0}
        assert compute_categoria_rischio(p) == "moderato"

    def test_medio_score3(self):
        # PDF p.6 prosa: ">1% e <4%" è "medio" (target LDL <130, lifestyle 6m)
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 3.0}
        assert compute_categoria_rischio(p) == "medio"

    def test_medio_score2(self):
        # PDF p.1 tab: 2-3% rischio medio
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 2.0}
        assert compute_categoria_rischio(p) == "medio"

    def test_basso_score0_5(self):
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 0.5}
        assert compute_categoria_rischio(p) == "basso"

    def test_basso_score1_inclusive(self):
        # V3.4 audit fix: PDF p.6 "≤1%" rischio basso (LE inclusivo, non LT)
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 1.0}
        assert compute_categoria_rischio(p) == "basso"

    def test_alto_dislipidemia_familiare(self):
        # V3.4 audit Day 2 fix F1-N13-Div#1 BLOC: dislip. familiari ora "alto"
        # (PDF p.7), pre-fix era "molto_alto". Need molto_alto flags False to
        # commit ALTO (otherwise UNKNOWN by 3VL semantics — see audit fix C1).
        p = {
            **self._FLAGS_ALL_FALSE,
            "tipo_dislipidemia_familiare": True,
        }
        assert compute_categoria_rischio(p) == "alto"

    def test_alto_irc_moderata(self):
        # V3.4 audit Day 2 fix F1-N13-Div#1 BLOC: IRC moderata ora "alto"
        # (PDF p.7), pre-fix era "molto_alto".
        p = {
            **self._FLAGS_ALL_FALSE,
            "irc_moderata": True,
        }
        assert compute_categoria_rischio(p) == "alto"

    def test_haart_no_classification(self):
        # V3.4 audit Day 2 fix F1-N13-Div#1 BLOC: in_terapia_haart NON è
        # un fattore di risk classification CV (PDF p.12: solo iperlipidemia
        # indotta da farmaci, drug-choice). Pre-fix erroneamente "molto_alto".
        # Senza altro score: None.
        p = {"in_terapia_haart": True}
        assert compute_categoria_rischio(p) is None

    def test_none_if_score_missing(self):
        p = {}
        assert compute_categoria_rischio(p) is None

    # ── Three-valued semantics tests (audit fix 2026-05-06, F-NEW-6 / C1) ──

    def test_unknown_when_molto_alto_flag_explicitly_none_with_alto_score(self):
        """Score=5 + malattia_coronarica_documentata=None EXPLICIT → UNKNOWN.

        If the clinician explicitly declared the field as None ("not yet
        examined"), we cannot commit to ALTO (target LDL 100): if the flag
        were True, the correct category would be MOLTO_ALTO (target LDL 70).
        Silently using the lower tier is a clinical underprescribing bug.

        Note: this test uses EXPLICIT None (key present, value=None), which
        differs from MISSING key (handled by test_alto_score5 — assumed False).
        """
        p = {
            "risk_score_cvd_fatale_10y": 5.0,
            "pregresso_ictus_ischemico": False,
            "arteriopatia_periferica": False,
            "diabete_con_fattori_rischio_cv": False,
            "irc_grave": False,
            "malattia_coronarica_documentata": None,  # EXPLICIT unknown
            "tipo_dislipidemia_familiare": False,
            "irc_moderata": False,
        }
        assert compute_categoria_rischio(p) is None

    def test_alto_score10_overrides_unknown_flag(self):
        """Score≥10% commits MOLTO_ALTO regardless of unknown flags."""
        p = {"risk_score_cvd_fatale_10y": 12.0}  # all flags None
        assert compute_categoria_rischio(p) == "molto_alto"

    def test_unknown_when_alto_flag_explicitly_none_with_medio_score(self):
        """Score=3 + tipo_dislipidemia_familiare=None EXPLICIT → UNKNOWN."""
        p = {
            **self._FLAGS_ALL_FALSE,
            "risk_score_cvd_fatale_10y": 3.0,
        }
        # Set the alto flag to EXPLICIT None
        p["tipo_dislipidemia_familiare"] = None
        assert compute_categoria_rischio(p) is None

    def test_alto_when_score5_and_flags_missing_assumed_false(self):
        """Score=5 + flags missing from dict → ALTO (gold convention).

        Missing keys are treated as False (not relevant). This preserves
        compatibility with the gold standard which omits flags assumed to be
        False rather than declaring them explicitly.
        """
        p = {"risk_score_cvd_fatale_10y": 5.0}  # all flags missing
        assert compute_categoria_rischio(p) == "alto"

    def test_committed_alto_when_score5_and_all_flags_false(self):
        """Score=5 + all flags explicitly False → committed ALTO (no UNKNOWN)."""
        p = {**self._FLAGS_ALL_FALSE, "risk_score_cvd_fatale_10y": 5.0}
        assert compute_categoria_rischio(p) == "alto"

    def test_unknown_when_all_flags_none_no_score(self):
        """All flags None + no score → UNKNOWN."""
        p = {}
        assert compute_categoria_rischio(p) is None


# ---------------------------------------------------------------------------
# compute_derived_variables integration
# ---------------------------------------------------------------------------

class TestComputeDerivedVariables:

    def test_enriched_has_cha2ds2vasc_range(self):
        p = {"paziente_eta": 72, "paziente_sesso": "M"}
        enriched = compute_derived_variables(p)
        assert "cha2ds2vasc_range" in enriched
        assert isinstance(enriched["cha2ds2vasc_range"], ScoreRange)

    def test_enriched_has_threshold(self):
        p = {"paziente_sesso": "M"}
        enriched = compute_derived_variables(p)
        assert enriched["cha2ds2vasc_threshold"] == 2

    def test_original_unchanged(self):
        p = {"paziente_eta": 72, "paziente_sesso": "M"}
        compute_derived_variables(p)
        assert "cha2ds2vasc_range" not in p  # original not mutated
