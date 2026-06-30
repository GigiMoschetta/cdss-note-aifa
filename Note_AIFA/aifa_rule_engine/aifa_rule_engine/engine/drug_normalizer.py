"""
Drug normalization — closed enum of known drug identifiers.

drug_id from API input is normalized to a canonical snake_case INN key.
Both INN names (e.g. "dabigatran") and brand names (e.g. "Pradaxa") are
accepted; brand names are resolved to the corresponding INN before any
further processing.

Unknown drug_ids raise a validation error at the API boundary.
"""
from __future__ import annotations

import re
from enum import Enum


class DrugId(str, Enum):
    # Nota 97 — DOACs / anticoagulants
    APIXABAN      = "apixaban"
    DABIGATRAN    = "dabigatran"
    EDOXABAN      = "edoxaban"
    RIVAROXABAN   = "rivaroxaban"
    WARFARIN      = "warfarin"
    ACENOCUMAROLO = "acenocumarolo"

    # Nota 01 — PPIs / gastroprotectors
    OMEPRAZOLO   = "omeprazolo"
    PANTOPRAZOLO = "pantoprazolo"
    LANSOPRAZOLO = "lansoprazolo"
    ESOMEPRAZOLO = "esomeprazolo"
    RABEPRAZOLO  = "rabeprazolo"
    MISOPROSTOLO = "misoprostolo"

    # Nota 66 — NSAIDs + coxibs
    # Bug fix (audit Day 1, finding F1-N66-Div#1 BLOCCANTE):
    # - Added AMTOLMETINA_GUACILE and NABUMETONE (in PDF lista chiusa, were missing)
    # - Removed DEXKETOPROFENE and KETOROLAC from N66_INCL_001 allowed_set (rules YAML);
    #   kept here in DrugId enum so that requests can be parsed without API rejection,
    #   but a request `(note=66, drug=ketorolac)` will now be NON_RIMBORSABILE because
    #   the drug is not in N66_INCL_001 allowed_set per PDF.
    #   (PDF Allegato 4 AV-12: ketorolac is EMA-restricted for high gastrolesivity.)
    DICLOFENAC              = "diclofenac"
    DICLOFENAC_MISOPROSTOLO = "diclofenac_misoprostolo"
    IBUPROFENE              = "ibuprofene"
    IBUPROFENE_CODEINA      = "ibuprofene_codeina"
    KETOPROFENE             = "ketoprofene"
    NAPROSSENE              = "naprossene"
    NIMESULIDE              = "nimesulide"
    MELOXICAM               = "meloxicam"
    PIROXICAM               = "piroxicam"
    INDOMETACINA            = "indometacina"
    CELECOXIB               = "celecoxib"
    ETORICOXIB              = "etoricoxib"
    ACECLOFENAC             = "aceclofenac"
    DEXIBUPROFENE           = "dexibuprofene"
    FLURBIPROFENE           = "flurbiprofene"
    SULINDAC                = "sulindac"
    TENOXICAM               = "tenoxicam"
    LORNOXICAM              = "lornoxicam"
    ACEMETACINA             = "acemetacina"
    ACIDO_MEFENAMICO        = "acido_mefenamico"
    ACIDO_TIAPROFENICO      = "acido_tiaprofenico"
    CINNOXICAM              = "cinnoxicam"
    DEXKETOPROFENE          = "dexketoprofene"  # NOT in N66 allowed_set per PDF
    FENTIAZAC               = "fentiazac"
    FURPROFENE              = "furprofene"
    KETOROLAC               = "ketorolac"  # NOT in N66 allowed_set per PDF (EMA-restricted)
    OXAPROZINA              = "oxaprozina"
    PROGLUMETACINA          = "proglumetacina"
    AMTOLMETINA_GUACILE     = "amtolmetina_guacile"  # PDF p.2 lista chiusa
    NABUMETONE              = "nabumetone"           # PDF p.2 lista chiusa

    # Nota 13 — lipid-lowering
    ATORVASTATINA          = "atorvastatina"
    ROSUVASTATINA          = "rosuvastatina"
    SIMVASTATINA           = "simvastatina"
    PRAVASTATINA           = "pravastatina"
    FLUVASTATINA           = "fluvastatina"
    LOVASTATINA            = "lovastatina"
    EZETIMIBE              = "ezetimibe"
    EZETIMIBE_SIMVASTATINA = "ezetimibe_simvastatina"

    # Other known drugs (outside all 4 Note scopes → always NON_RIMBORSABILE via SCOPE)
    ASPIRINA = "aspirina"   # acetylsalicylic acid — not in any nota closed list


KNOWN_DRUG_IDS: frozenset[str] = frozenset(d.value for d in DrugId)


# ---------------------------------------------------------------------------
# Brand-name → INN alias table
#
# Keys are stored in normalized form (lowercase, spaces and hyphens replaced
# by underscores) so that look-up requires no additional transformation beyond
# the same step already applied to INN names.
#
# Sources: AIFA Banca Dati Farmaci (https://farmaci.agenziafarmaco.gov.it/),
#          EMA product database, and Italian prescribing information leaflets.
# ---------------------------------------------------------------------------
_ALIASES: dict[str, str] = {

    # ── Nota 97 — DOACs / anticoagulants ────────────────────────────────────
    # apixaban
    "eliquis":       "apixaban",          # BMS/Pfizer

    # dabigatran
    "pradaxa":       "dabigatran",        # Boehringer Ingelheim

    # edoxaban
    "lixiana":       "edoxaban",          # Daiichi Sankyo (EU, incl. Italy)
    "roteas":        "edoxaban",          # Daiichi Sankyo (EU alt. trade name)

    # rivaroxaban
    "xarelto":       "rivaroxaban",       # Bayer

    # warfarin
    "coumadin":      "warfarin",          # Bristol-Myers Squibb
    "marevan":       "warfarin",          # Orion

    # acenocumarolo
    "sintrom":       "acenocumarolo",     # Novartis

    # ── Nota 01 — PPIs / gastroprotectors ───────────────────────────────────
    # omeprazolo
    "losec":         "omeprazolo",        # AstraZeneca
    "mepral":        "omeprazolo",        # Alfa Wassermann
    "omeprazen":     "omeprazolo",        # various generic trade names
    "prilosec":      "omeprazolo",        # AstraZeneca (US name, sometimes used)

    # pantoprazolo
    "pantopan":      "pantoprazolo",      # Takeda
    "pantorc":       "pantoprazolo",      # Takeda (IT)
    "zurcazol":      "pantoprazolo",      # Chiesi
    "nolpaza":       "pantoprazolo",      # Almirall

    # lansoprazolo
    "lanzopral":     "lansoprazolo",      # Takeda (IT)
    "lomac":         "lansoprazolo",      # AstraZeneca (IT)
    "prevacid":      "lansoprazolo",      # Takeda (US name)
    "ogastoro":      "lansoprazolo",      # Takeda (IT alt.)

    # esomeprazolo
    "nexium":        "esomeprazolo",      # AstraZeneca

    # rabeprazolo
    "pariet":        "rabeprazolo",       # Eisai / Janssen

    # misoprostolo
    "cytotec":       "misoprostolo",      # Pfizer

    # ── Nota 66 — NSAIDs + coxibs ───────────────────────────────────────────
    # diclofenac
    "voltaren":      "diclofenac",        # Novartis
    "dicloreum":     "diclofenac",        # Alfa Wassermann (IT)
    "flector":       "diclofenac",        # Menarini (topical patch)

    # diclofenac + misoprostolo (fixed combination)
    "arthrotec":     "diclofenac_misoprostolo",  # Pfizer

    # ibuprofene
    "brufen":        "ibuprofene",        # Abbott / Viatris
    "moment":        "ibuprofene",        # Angelini (IT)
    "nurofen":       "ibuprofene",        # Reckitt
    "antalgil":      "ibuprofene",        # Pfizer (IT)

    # ibuprofene + codeina (fixed combination)
    "nurofen_plus":  "ibuprofene_codeina",  # Reckitt (IT/EU)

    # ketoprofene
    "fastum":        "ketoprofene",       # Menarini (IT)
    "orudis":        "ketoprofene",       # Pfizer
    "ketodol":       "ketoprofene",       # Zambon (IT)

    # naprossene
    "aleve":         "naprossene",        # Bayer (OTC)
    "naprosyn":      "naprossene",        # Roche / Alliance
    "momendol":      "naprossene",        # Reckitt (IT)

    # nimesulide
    "aulin":         "nimesulide",        # Boehringer Ingelheim (IT)
    "mesulid":       "nimesulide",        # Helsinn (IT)

    # meloxicam
    "mobic":         "meloxicam",         # Boehringer Ingelheim
    "movalis":       "meloxicam",         # Boehringer Ingelheim (EU alt.)

    # piroxicam
    "feldene":       "piroxicam",         # Pfizer
    "brexin":        "piroxicam",         # Recordati (IT)

    # indometacina
    "indoxen":       "indometacina",      # Recordati (IT)
    "metacen":       "indometacina",      # various

    # celecoxib
    "celebrex":      "celecoxib",         # Pfizer
    "onsenal":       "celecoxib",         # Pfizer (EU alt. trade name)

    # etoricoxib
    "arcoxia":       "etoricoxib",        # MSD (Merck Sharp & Dohme)

    # aceclofenac
    "airtal":        "aceclofenac",       # Almirall (IT)

    # dexibuprofene
    "seractil":      "dexibuprofene",     # Gebro Pharma

    # flurbiprofene
    "froben":        "flurbiprofene",     # Abbott / Viatris

    # tenoxicam
    "tilcotil":      "tenoxicam",         # Roche / Cheplapharm

    # lornoxicam
    "xefo":          "lornoxicam",        # Nycomed / Takeda

    # acemetacina
    "acemix":        "acemetacina",       # generic IT

    # dexketoprofene
    "dexofen":       "dexketoprofene",    # Menarini
    "ketesse":       "dexketoprofene",    # Menarini (IT)

    # ketorolac
    "toradol":       "ketorolac",         # Roche
    "lixidol":       "ketorolac",         # Recordati (IT)

    # ── Nota 13 — lipid-lowering ─────────────────────────────────────────────
    # atorvastatina
    "torvast":       "atorvastatina",     # Pfizer (IT)
    "lipitor":       "atorvastatina",     # Pfizer (US name, widely known)

    # rosuvastatina
    "crestor":       "rosuvastatina",     # AstraZeneca

    # simvastatina
    "zocor":         "simvastatina",      # MSD
    "sinvacor":      "simvastatina",      # Viatris (IT)
    "sivastin":      "simvastatina",      # various (IT)
    "liponorm":      "simvastatina",      # Recordati (IT)

    # pravastatina
    "selectin":      "pravastatina",      # Bristol-Myers Squibb (IT)
    "pravaselect":   "pravastatina",      # various (IT)
    "pravachol":     "pravastatina",      # BMS (US name)

    # fluvastatina
    "lescol":        "fluvastatina",      # Novartis
    "canef":         "fluvastatina",      # Novartis (IT alt.)

    # lovastatina
    "mevacor":       "lovastatina",       # MSD

    # ezetimibe
    "ezetrol":       "ezetimibe",         # MSD / Organon (EU)
    "zetia":         "ezetimibe",         # MSD / Organon (US name)

    # ezetimibe + simvastatina (fixed combination)
    "inegy":         "ezetimibe_simvastatina",  # MSD / SP (EU)
    "vytorin":       "ezetimibe_simvastatina",  # MSD / SP (US name)
}


def normalize_drug_id(raw: str) -> str:
    """
    Return the canonical INN drug_id for the given input, or raise ValueError.

    Accepts:
    - INN names (canonical): "dabigatran", "DABIGATRAN", "Dabigatran"
    - Brand names:           "Pradaxa", "pradaxa", "PRADAXA"

    Normalization applied (same for INN and brand name lookup):
        lowercase → strip whitespace → collapse runs of whitespace/hyphens
        (incl. tabs, double spaces, en/em-dashes) to a single underscore.

    Raises ValueError for unknown names, with a message listing known INN names
    and available brand-name aliases.
    """
    # Audit fix 2026-05-07 (V3-W1-MEDIUM): collapse arbitrary whitespace runs
    # (tabs, double spaces, NBSP) and any hyphen variant into single underscore.
    # Previous `replace(" ", "_")` left "api  xaban" → "api__xaban" → no match.
    normalized = raw.lower().strip()
    normalized = re.sub(r"[\s\-‐-― ]+", "_", normalized)

    # 1. Try canonical INN match first (most common path)
    if normalized in KNOWN_DRUG_IDS:
        return normalized

    # 2. Try brand-name alias resolution
    if normalized in _ALIASES:
        return _ALIASES[normalized]

    # 3. Unknown — produce a helpful error message.
    # Audit fix 2026-05-06: avoid leaking the full INN/alias catalogue in the
    # ValueError (was ~140 names enumerated in Pydantic 422 / HTTP 500
    # responses). Hint at format only — the catalogue is documented in
    # data_dictionary.py and recoverable via a dedicated /catalog endpoint
    # if needed.
    raise ValueError(
        f"Unknown drug_id '{raw}'. "
        f"Expected an INN (e.g. 'apixaban') or registered brand alias. "
        f"Catalogue size: {len(KNOWN_DRUG_IDS)} INN, {len(_ALIASES)} aliases."
    )
