"""
Unit tests for drug_normalizer.py.

Covers:
- INN canonical names (existing behaviour, must not regress)
- Brand-name → INN resolution for every nota
- Normalization (case, spaces, hyphens)
- Unknown drug raises ValueError with informative message
"""
from __future__ import annotations

import pytest

from aifa_rule_engine.engine.drug_normalizer import (
    _ALIASES,
    KNOWN_DRUG_IDS,
    normalize_drug_id,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def resolves_to(raw: str, expected_inn: str) -> None:
    """Assert that normalize_drug_id(raw) == expected_inn."""
    assert normalize_drug_id(raw) == expected_inn


# ── INN canonical names (regression guard) ────────────────────────────────────

class TestInnNames:
    """All canonical INN names must continue to pass through unchanged."""

    def test_all_canonical_inn_names_accepted(self):
        for inn in sorted(KNOWN_DRUG_IDS):
            assert normalize_drug_id(inn) == inn, f"INN '{inn}' rejected"

    def test_inn_case_insensitive(self):
        resolves_to("DABIGATRAN",   "dabigatran")
        resolves_to("Apixaban",     "apixaban")
        resolves_to("RIVAROXABAN",  "rivaroxaban")
        resolves_to("Omeprazolo",   "omeprazolo")
        resolves_to("NIMESULIDE",   "nimesulide")
        resolves_to("Atorvastatina","atorvastatina")

    def test_inn_strips_surrounding_whitespace(self):
        resolves_to("  dabigatran  ", "dabigatran")
        resolves_to("\twarfarin\n",   "warfarin")

    def test_inn_with_internal_space_or_hyphen(self):
        # Compound names typed with space or hyphen
        resolves_to("ibuprofene codeina",    "ibuprofene_codeina")
        resolves_to("ibuprofene-codeina",    "ibuprofene_codeina")
        resolves_to("ezetimibe simvastatina","ezetimibe_simvastatina")
        resolves_to("ezetimibe-simvastatina","ezetimibe_simvastatina")
        resolves_to("diclofenac misoprostolo","diclofenac_misoprostolo")


# ── Nota 97 brand names ───────────────────────────────────────────────────────

class TestNota97BrandNames:

    def test_pradaxa_resolves_to_dabigatran(self):
        resolves_to("Pradaxa", "dabigatran")

    def test_eliquis_resolves_to_apixaban(self):
        resolves_to("Eliquis", "apixaban")

    def test_xarelto_resolves_to_rivaroxaban(self):
        resolves_to("Xarelto", "rivaroxaban")

    def test_lixiana_resolves_to_edoxaban(self):
        resolves_to("Lixiana", "edoxaban")

    def test_roteas_resolves_to_edoxaban(self):
        resolves_to("Roteas", "edoxaban")

    def test_coumadin_resolves_to_warfarin(self):
        resolves_to("Coumadin", "warfarin")

    def test_marevan_resolves_to_warfarin(self):
        resolves_to("Marevan", "warfarin")

    def test_sintrom_resolves_to_acenocumarolo(self):
        resolves_to("Sintrom", "acenocumarolo")


# ── Nota 01 brand names ───────────────────────────────────────────────────────

class TestNota01BrandNames:

    def test_nexium_resolves_to_esomeprazolo(self):
        resolves_to("Nexium", "esomeprazolo")

    def test_pariet_resolves_to_rabeprazolo(self):
        resolves_to("Pariet", "rabeprazolo")

    def test_losec_resolves_to_omeprazolo(self):
        resolves_to("Losec", "omeprazolo")

    def test_pantopan_resolves_to_pantoprazolo(self):
        resolves_to("Pantopan", "pantoprazolo")

    def test_pantorc_resolves_to_pantoprazolo(self):
        resolves_to("Pantorc", "pantoprazolo")

    def test_lanzopral_resolves_to_lansoprazolo(self):
        resolves_to("Lanzopral", "lansoprazolo")

    def test_prevacid_resolves_to_lansoprazolo(self):
        resolves_to("Prevacid", "lansoprazolo")

    def test_cytotec_resolves_to_misoprostolo(self):
        resolves_to("Cytotec", "misoprostolo")


# ── Nota 66 brand names ───────────────────────────────────────────────────────

class TestNota66BrandNames:

    def test_voltaren_resolves_to_diclofenac(self):
        resolves_to("Voltaren", "diclofenac")

    def test_dicloreum_resolves_to_diclofenac(self):
        resolves_to("Dicloreum", "diclofenac")

    def test_arthrotec_resolves_to_diclofenac_misoprostolo(self):
        resolves_to("Arthrotec", "diclofenac_misoprostolo")

    def test_brufen_resolves_to_ibuprofene(self):
        resolves_to("Brufen", "ibuprofene")

    def test_moment_resolves_to_ibuprofene(self):
        resolves_to("Moment", "ibuprofene")

    def test_nurofen_resolves_to_ibuprofene(self):
        resolves_to("Nurofen", "ibuprofene")

    def test_nurofen_plus_resolves_to_ibuprofene_codeina(self):
        resolves_to("Nurofen Plus",  "ibuprofene_codeina")
        resolves_to("nurofen_plus",  "ibuprofene_codeina")
        resolves_to("Nurofen-Plus",  "ibuprofene_codeina")

    def test_fastum_resolves_to_ketoprofene(self):
        resolves_to("Fastum", "ketoprofene")

    def test_orudis_resolves_to_ketoprofene(self):
        resolves_to("Orudis", "ketoprofene")

    def test_aleve_resolves_to_naprossene(self):
        resolves_to("Aleve", "naprossene")

    def test_naprosyn_resolves_to_naprossene(self):
        resolves_to("Naprosyn", "naprossene")

    def test_aulin_resolves_to_nimesulide(self):
        resolves_to("Aulin", "nimesulide")

    def test_mesulid_resolves_to_nimesulide(self):
        resolves_to("Mesulid", "nimesulide")

    def test_mobic_resolves_to_meloxicam(self):
        resolves_to("Mobic", "meloxicam")

    def test_movalis_resolves_to_meloxicam(self):
        resolves_to("Movalis", "meloxicam")

    def test_feldene_resolves_to_piroxicam(self):
        resolves_to("Feldene", "piroxicam")

    def test_brexin_resolves_to_piroxicam(self):
        resolves_to("Brexin", "piroxicam")

    def test_indoxen_resolves_to_indometacina(self):
        resolves_to("Indoxen", "indometacina")

    def test_celebrex_resolves_to_celecoxib(self):
        resolves_to("Celebrex", "celecoxib")

    def test_onsenal_resolves_to_celecoxib(self):
        resolves_to("Onsenal", "celecoxib")

    def test_arcoxia_resolves_to_etoricoxib(self):
        resolves_to("Arcoxia", "etoricoxib")

    def test_airtal_resolves_to_aceclofenac(self):
        resolves_to("Airtal", "aceclofenac")

    def test_seractil_resolves_to_dexibuprofene(self):
        resolves_to("Seractil", "dexibuprofene")

    def test_froben_resolves_to_flurbiprofene(self):
        resolves_to("Froben", "flurbiprofene")

    def test_tilcotil_resolves_to_tenoxicam(self):
        resolves_to("Tilcotil", "tenoxicam")

    def test_xefo_resolves_to_lornoxicam(self):
        resolves_to("Xefo", "lornoxicam")

    # New NSAIDs added in P2-3
    def test_acemix_resolves_to_acemetacina(self):
        resolves_to("Acemix", "acemetacina")

    def test_dexofen_resolves_to_dexketoprofene(self):
        resolves_to("Dexofen", "dexketoprofene")

    def test_ketesse_resolves_to_dexketoprofene(self):
        resolves_to("Ketesse", "dexketoprofene")

    def test_toradol_resolves_to_ketorolac(self):
        resolves_to("Toradol", "ketorolac")

    def test_lixidol_resolves_to_ketorolac(self):
        resolves_to("Lixidol", "ketorolac")


# ── Nota 66 new INN names (P2-3) ────────────────────────────────────────────

class TestNota66NewDrugs:
    """INN canonical names for the 10 newly added NSAIDs."""

    @pytest.mark.parametrize("drug", [
        "acemetacina", "acido_mefenamico", "acido_tiaprofenico",
        "cinnoxicam", "dexketoprofene", "fentiazac", "furprofene",
        "ketorolac", "oxaprozina", "proglumetacina",
    ])
    def test_new_inn_accepted(self, drug):
        resolves_to(drug, drug)

    def test_acido_mefenamico_with_space(self):
        resolves_to("acido mefenamico", "acido_mefenamico")

    def test_acido_tiaprofenico_with_hyphen(self):
        resolves_to("acido-tiaprofenico", "acido_tiaprofenico")


# ── Nota 13 brand names ───────────────────────────────────────────────────────

class TestNota13BrandNames:

    def test_torvast_resolves_to_atorvastatina(self):
        resolves_to("Torvast", "atorvastatina")

    def test_lipitor_resolves_to_atorvastatina(self):
        resolves_to("Lipitor", "atorvastatina")

    def test_crestor_resolves_to_rosuvastatina(self):
        resolves_to("Crestor", "rosuvastatina")

    def test_zocor_resolves_to_simvastatina(self):
        resolves_to("Zocor", "simvastatina")

    def test_sinvacor_resolves_to_simvastatina(self):
        resolves_to("Sinvacor", "simvastatina")

    def test_selectin_resolves_to_pravastatina(self):
        resolves_to("Selectin", "pravastatina")

    def test_pravachol_resolves_to_pravastatina(self):
        resolves_to("Pravachol", "pravastatina")

    def test_lescol_resolves_to_fluvastatina(self):
        resolves_to("Lescol", "fluvastatina")

    def test_mevacor_resolves_to_lovastatina(self):
        resolves_to("Mevacor", "lovastatina")

    def test_ezetrol_resolves_to_ezetimibe(self):
        resolves_to("Ezetrol", "ezetimibe")

    def test_zetia_resolves_to_ezetimibe(self):
        resolves_to("Zetia", "ezetimibe")

    def test_inegy_resolves_to_ezetimibe_simvastatina(self):
        resolves_to("Inegy", "ezetimibe_simvastatina")

    def test_vytorin_resolves_to_ezetimibe_simvastatina(self):
        resolves_to("Vytorin", "ezetimibe_simvastatina")


# ── Normalisation of brand-name input ────────────────────────────────────────

class TestBrandNameNormalisation:
    """Brand names must be resolved regardless of case, spaces, or hyphens."""

    def test_brand_name_all_uppercase(self):
        resolves_to("PRADAXA",   "dabigatran")
        resolves_to("ELIQUIS",   "apixaban")
        resolves_to("XARELTO",   "rivaroxaban")
        resolves_to("VOLTAREN",  "diclofenac")
        resolves_to("CELEBREX",  "celecoxib")
        resolves_to("CRESTOR",   "rosuvastatina")

    def test_brand_name_mixed_case(self):
        resolves_to("Pradaxa",   "dabigatran")
        resolves_to("pRadAxA",   "dabigatran")
        resolves_to("voltaren",  "diclofenac")

    def test_brand_name_with_surrounding_whitespace(self):
        resolves_to("  Pradaxa  ", "dabigatran")
        resolves_to("\tXarelto\n", "rivaroxaban")

    def test_brand_name_with_internal_space(self):
        resolves_to("Nurofen Plus", "ibuprofene_codeina")

    def test_brand_name_with_hyphen(self):
        resolves_to("Nurofen-Plus", "ibuprofene_codeina")


# ── Unknown drug raises ValueError ───────────────────────────────────────────

class TestUnknownDrug:

    def test_completely_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown drug_id"):
            normalize_drug_id("aspirin_unknown_brand")

    def test_error_message_contains_input_name(self):
        bad_name = "TotallyFakeDrug"
        with pytest.raises(ValueError, match=bad_name):
            normalize_drug_id(bad_name)

    def test_error_message_format_hint_no_catalog_leak(self):
        """Audit fix 2026-05-06: previous error enumerated 60+ INN + 80+ aliases
        in the ValueError message — leaking the catalogue via Pydantic 422
        responses. The new message hints at format only."""
        import re
        with pytest.raises(ValueError) as exc_info:
            normalize_drug_id("notadrug")
        msg = str(exc_info.value)
        # Format hint must be present
        assert "INN" in msg
        # Must NOT enumerate specific drug names or brands (no catalogue leak)
        assert "dabigatran" not in msg
        assert "pradaxa" not in msg
        # Must report catalogue size (not contents)
        assert re.search(r"\bINN\b", msg) and re.search(r"\baliases\b", msg)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_drug_id("")

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_drug_id("   ")


# ── Alias table integrity ─────────────────────────────────────────────────────

class TestAliasTableIntegrity:
    """Static checks on the _ALIASES dict itself."""

    def test_all_alias_values_are_known_inn(self):
        """Every value in _ALIASES must be a known canonical INN."""
        for alias, inn in _ALIASES.items():
            assert inn in KNOWN_DRUG_IDS, (
                f"Alias '{alias}' maps to '{inn}' which is not a known INN"
            )

    def test_no_alias_key_shadows_inn_name(self):
        """No alias key should equal a canonical INN name (would be redundant)."""
        for alias in _ALIASES:
            assert alias not in KNOWN_DRUG_IDS, (
                f"Alias key '{alias}' is already a canonical INN — remove the alias"
            )

    def test_alias_count_reasonable(self):
        """Sanity check: at least 40 aliases defined (5 per drug on average)."""
        assert len(_ALIASES) >= 40, (
            f"Expected ≥40 aliases, found {len(_ALIASES)}"
        )
