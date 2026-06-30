"""
Derived variable computation (Phase 0 — before rule evaluation).

All computations are purely functional (no I/O, no side effects).
Results are stored in the enriched patient data dict under well-known keys.
"""
from __future__ import annotations

from typing import Any

from ..models.results import ScoreRange
from .three_valued import TruthValue

# ---------------------------------------------------------------------------
# CHA2DS2-VASc (interval arithmetic — Fix 1.1 / V3.3 patch 4)
# ---------------------------------------------------------------------------

def compute_cha2ds2vasc_range(patient: dict[str, Any]) -> ScoreRange:
    """Compute CHA2DS2-VASc as an interval [min, max] with unknown tracking.

    Component weights (nota-97.pdf p.2, Tab.1):
      C  — scompenso_cardiaco          weight=1
      H  — ipertensione_arteriosa      weight=1
      A2 — paziente_eta >= 75          weight=2  (age block)
      D  — diabete_mellito             weight=1
      S2 — pregresso_ictus_tia_te      weight=2
      V  — vasculopatia                weight=1
      A  — 65 <= paziente_eta < 75     weight=1  (age block — mutually exclusive with A2)
      Sc — paziente_sesso == "F"       weight=1

    Mutual exclusivity: A2 and A cannot both be TRUE. Age is handled in a
    dedicated block that contributes at most max(2, 1) = 2 to max_score.
    """
    min_score = 0
    max_score = 0
    unknown_components: list[str] = []

    # Non-age boolean components
    NON_AGE_COMPONENTS: list[tuple[str, str, int]] = [
        # (variable_name, test_kind, weight)
        # test_kind: "is_true" or "eq_F"
        ("scompenso_cardiaco",     "is_true", 1),
        ("ipertensione_arteriosa", "is_true", 1),
        ("diabete_mellito",        "is_true", 1),
        ("pregresso_ictus_tia_te", "is_true", 2),
        ("vasculopatia",           "is_true", 1),
    ]

    for var, _, weight in NON_AGE_COMPONENTS:
        val = patient.get(var)
        if val is True:
            min_score += weight
            max_score += weight
        elif val is None:
            max_score += weight
            unknown_components.append(var)
        # False: no change

    # Sex component (Sc — Sesso femminile, weight=1)
    sesso = patient.get("paziente_sesso")
    if sesso is None:
        max_score += 1
        unknown_components.append("paziente_sesso")
    elif sesso == "F":
        min_score += 1
        max_score += 1
    # "M" or other: +0

    # Age — mutually exclusive block (A2 and A cannot both be TRUE)
    # Maximum possible age contribution = 2 (A2 weight, not 2+1)
    age = patient.get("paziente_eta")
    if age is None:
        max_score += 2   # maximum possible (A2 weight)
        unknown_components.append("paziente_eta")
    elif age >= 75:
        min_score += 2   # A2 component
        max_score += 2
    elif age >= 65:
        min_score += 1   # A component
        max_score += 1
    # else age < 65: +0

    return ScoreRange(
        min=min_score,
        max=max_score,
        unknown_components=unknown_components,
    )


def compute_cha2ds2vasc_threshold(patient: dict[str, Any]) -> int | None:
    """Return sex-dependent threshold (M=2, F=3) or None if sex unknown.

    Thresholds per nota-97.pdf p.3 (OCR-corrected, ≥2 M / ≥3 F):
    - Males:   score ≥ 2 → eligible (threshold = 2)
    - Females: score ≥ 3 → eligible (threshold = 3)
    - Unknown sex → threshold = None → eligibility = UNKNOWN
    """
    sesso = patient.get("paziente_sesso")
    if sesso == "M":
        return 2
    if sesso == "F":
        return 3
    return None


# ---------------------------------------------------------------------------
# Apixaban dose-reduction criterion count
# ---------------------------------------------------------------------------

def compute_apixaban_riduzione_count(
    patient: dict[str, Any],
) -> tuple[TruthValue, frozenset[str]]:
    """COUNT_GEQ([eta>=80, peso<=60, creat>=1.5], threshold=2) with UNKNOWN propagation.

    Inclusive operators per nota-97-all-2.pdf p.6 Tab.4 (OCR-corrected, V3.3 Patch 6):
      - Età ≥80 (GTE)
      - Peso ≤60 kg (LTE)
      - Creatinina ≥1.5 mg/dl (GTE)

    Returns (TruthValue, frozenset[missing_fields]) using COUNT_GEQ semantics.
    """
    # Build the conditions inline using the AST
    conditions_data = [
        ("paziente_eta",       "GTE", 80.0),
        ("paziente_peso_kg",   "LTE", 60.0),
        ("creatinina_sierica", "GTE", 1.5),
    ]

    known_true = 0
    unknown_n = 0
    all_missing: frozenset[str] = frozenset()

    for var, op, threshold_val in conditions_data:
        val = patient.get(var)
        if val is None:
            unknown_n += 1
            all_missing = all_missing | frozenset({var})
        else:
            if op == "GTE":
                result = val >= threshold_val
            elif op == "LTE":
                result = val <= threshold_val
            else:
                result = False
            if result:
                known_true += 1
            # else: known_false, no change

    thr = 2
    if known_true >= thr:
        return (TruthValue.TRUE, frozenset())
    elif known_true + unknown_n < thr:
        return (TruthValue.FALSE, frozenset())
    else:
        return (TruthValue.UNKNOWN, all_missing)


# ---------------------------------------------------------------------------
# Nota 13 — categoria_rischio derivation
# ---------------------------------------------------------------------------

_MOLTO_ALTO_FLAGS = (
    "malattia_coronarica_documentata",
    "pregresso_ictus_ischemico",
    "arteriopatia_periferica",
    "diabete_con_fattori_rischio_cv",
    "irc_grave",  # FG 15-29 ml/min/1.73m²
)
_ALTO_FLAGS = (
    "tipo_dislipidemia_familiare",
    "irc_moderata",
)


def compute_categoria_rischio(patient: dict[str, Any]) -> str | None:
    """Derive risk category per nota-13.pdf p.6-7 (verbatim PDF prosa).

    Returns: "molto_alto" | "alto" | "medio" | "moderato" | "basso" | None

    Three-valued semantics (audit fix 2026-05-06, finding F-NEW-6 / C1 RIFRAMED):

    The pre-fix logic returned a category as soon as the score-based classifier
    matched, even when a CV escalation flag was *explicitly declared as
    UNKNOWN* by the clinician. For a patient with score=5% who declared
    `malattia_coronarica_documentata=None` (i.e. "not yet examined"), the old
    code returned ALTO (target LDL 100). But if the flag were True, the
    correct category would be MOLTO_ALTO (target LDL 70) — silently picking
    the lower tier is a clinical underprescribing bug.

    Convention used here (matches gold-standard data):
      - field MISSING from `patient` dict   → assumed FALSE (not relevant);
      - field PRESENT and value is None     → UNKNOWN (clinician said: don't
                                              know);
      - field PRESENT and value is bool     → explicit True/False.

    Only EXPLICIT None values produce UNKNOWN propagation. Missing keys are
    treated as False, preserving backward-compat with gold cases that omit
    irrelevant flags.

    PDF anchors:
    - p.7 MOLTO_ALTO: score ≥10% OR (malattia coronarica | stroke | AOP |
      diabete+CV | IRC grave 15-29).
    - p.7 ALTO: score ≥5% OR dislipidemia familiare | IRC moderata 30-59.
    - p.6 MEDIO: score >1% e <4%.
    - p.1 MODERATO: score 4-5%.
    - p.6 BASSO: score ≤1%.
    """
    def _is_explicit_unknown(field: str) -> bool:
        """True iff the field is present in patient dict and its value is None."""
        return field in patient and patient[field] is None

    score = patient.get("risk_score_cvd_fatale_10y")

    # MOLTO ALTO — any flag True is sufficient (clinical short-circuit)
    if any(patient.get(f) is True for f in _MOLTO_ALTO_FLAGS):
        return "molto_alto"

    # Score-based escalation to MOLTO_ALTO: when score alone reaches the
    # molto_alto threshold the patient must be classified accordingly, even
    # when ALTO flags are simultaneously True. Without this guard a score>=10
    # patient with both an ALTO flag True and an explicit-unknown MOLTO_ALTO
    # flag would silently downgrade to "alto", giving a wrong LDL target.
    if score is not None and score >= 10.0:
        return "molto_alto"

    # ALTO — any flag True is sufficient (with UNKNOWN guard for molto_alto)
    if any(patient.get(f) is True for f in _ALTO_FLAGS):
        molto_alto_unknown = any(_is_explicit_unknown(f) for f in _MOLTO_ALTO_FLAGS)
        if molto_alto_unknown and (score is None or score < 10.0):
            return None
        return "alto"

    # No flag True. Check whether any higher-tier flag was explicitly declared
    # UNKNOWN — that suspends the classification unless the score alone proves
    # the higher tier.
    molto_alto_unknown = any(_is_explicit_unknown(f) for f in _MOLTO_ALTO_FLAGS)
    alto_unknown = any(_is_explicit_unknown(f) for f in _ALTO_FLAGS)

    if score is None:
        # No score and any explicit-unknown flag → UNKNOWN
        if molto_alto_unknown or alto_unknown:
            return None
        # No score, all flags either False or missing (assumed False) → UNKNOWN
        # (cannot classify without score).
        return None

    # Score is known. Classify by score, but UNKNOWN if a higher-tier flag was
    # *explicitly* declared None and the score doesn't reach that tier alone.
    if score >= 10.0:
        return "molto_alto"
    if molto_alto_unknown:
        # Score < 10 but an explicit-unknown molto_alto flag could escalate
        return None
    if score >= 5.0:
        return "alto"
    if alto_unknown:
        # Score < 5 but an explicit-unknown alto flag could escalate
        return None
    # PDF distinction medio (>1, <4) vs moderato (4-5):
    if score >= 4.0:
        return "moderato"
    if score > 1.0:
        return "medio"
    # PDF p.6: "score ≤1% rischio basso"
    return "basso"


def compute_target_ldl(categoria_rischio: str | None) -> float | None:
    """Return LDL target (mg/dL) per nota-13.pdf p.1-2 tabella.

    Audit Day 2 fix: aggiunto target per categoria "medio" (130 mg/dL).
    """
    mapping = {
        "molto_alto": 70.0,
        "alto": 100.0,
        "moderato": 115.0,
        "medio": 130.0,    # PDF p.1 tabella: "rischio medio score 2-3% → LDL <130"
        "basso": None,     # PDF p.1 footnote (*): solo lifestyle, no target farmacologico
    }
    return mapping.get(categoria_rischio) if categoria_rischio else None


# ---------------------------------------------------------------------------
# Top-level: compute all derived variables
# ---------------------------------------------------------------------------

def compute_derived_variables(patient: dict[str, Any]) -> dict[str, Any]:
    """Compute all derived variables and return an enriched copy of patient data.

    Called in Phase 0 (before rule evaluation). Purely functional — no I/O.
    """
    enriched = dict(patient)

    # CHA2DS2-VASc interval arithmetic
    score_range = compute_cha2ds2vasc_range(enriched)
    threshold = compute_cha2ds2vasc_threshold(enriched)
    enriched["cha2ds2vasc_range"] = score_range
    enriched["cha2ds2vasc_threshold"] = threshold

    # Nota 97 — apixaban dose-reduction criteria count (Plan D.2 Phase 0)
    apc_tv, _apc_missing = compute_apixaban_riduzione_count(enriched)
    enriched["apixaban_riduzione_count"] = {
        TruthValue.TRUE: True,
        TruthValue.FALSE: False,
        TruthValue.UNKNOWN: None,
    }[apc_tv]

    # Nota 66 — is_coxib derived from farmaco (used in N66_EXCL_HARD_003)
    # farmaco is injected as enriched["farmaco"] = drug_id before this call
    farmaco = enriched.get("farmaco")
    if farmaco is not None:
        enriched["is_coxib"] = farmaco in {"celecoxib", "etoricoxib"}

    # Nota 13 risk category
    cat = compute_categoria_rischio(enriched)
    enriched["categoria_rischio"] = cat
    enriched["target_ldl"] = compute_target_ldl(cat)

    # Nota 13 convenience booleans for IS_TRUE rules
    # Audit Day 2: aggiunta categoria "medio" (PDF p.6)
    if cat is not None:
        enriched["categoria_molto_alto"] = (cat == "molto_alto")
        enriched["categoria_alto"] = (cat == "alto")
        enriched["categoria_moderato"] = (cat == "moderato")
        enriched["categoria_medio"] = (cat == "medio")
        enriched["categoria_basso"] = (cat == "basso")
    else:
        enriched["categoria_molto_alto"] = None
        enriched["categoria_alto"] = None
        enriched["categoria_moderato"] = None
        enriched["categoria_medio"] = None
        enriched["categoria_basso"] = None

    return enriched
