"""
Carica i 122 gold standard cases e li arricchisce con un'identità sintetica
deterministica (nome, cognome, avatar, codice fiscale fake, recapito, anamnesi
sintetica, allergie). Niente I/O all'import.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
_GOLD_DIR = _PROJECT / "evaluation" / "gold_standard"
_RULES_DIR = _PROJECT / "aifa_rule_engine" / "rules"
_NAMES_FILE = _HERE / "data" / "italian_names.json"

_RULE_CATALOG_CACHE: dict[str, dict] | None = None


def load_rule_catalog() -> dict[str, dict]:
    """Return {rule_id: {description_it, detail, rule_type, normative_anchor}}.

    Reads every nota_XX/rules.yaml under aifa_rule_engine/rules/ and indexes by
    rule_id. Cached in module-global to avoid re-reading.
    """
    global _RULE_CATALOG_CACHE
    if _RULE_CATALOG_CACHE is not None:
        return _RULE_CATALOG_CACHE
    catalog: dict[str, dict] = {}
    try:
        import yaml  # type: ignore
    except ImportError:
        _RULE_CATALOG_CACHE = {}
        return _RULE_CATALOG_CACHE
    if not _RULES_DIR.exists():
        _RULE_CATALOG_CACHE = {}
        return _RULE_CATALOG_CACHE
    for yaml_file in sorted(_RULES_DIR.glob("*/rules.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        # rules.yaml is a top-level list of rule dicts (audit 2026-05-13 fix).
        if isinstance(data, list):
            rules = data
        elif isinstance(data, dict):
            rules = data.get("rules", [])
        else:
            rules = []
        for r in rules:
            if not isinstance(r, dict):
                continue
            rid = r.get("rule_id")
            if rid:
                catalog[rid] = {
                    "description_it": r.get("description_it", ""),
                    "detail": r.get("detail", ""),
                    "rule_type": r.get("rule_type", ""),
                    "normative_anchor": r.get("normative_anchor", {}),
                }
    _RULE_CATALOG_CACHE = catalog
    return catalog

# Highlight cases for the landing page (one per Nota, varied decisions).
HIGHLIGHT_CASES = [
    "N97-001",  # Standard RIMBORSABILE: apixaban con CHA2DS2-VASc alto
    "N66-005",  # NON RIMBORSABILE: nimesulide controindicata
    "N01-019",  # ROUTED: diclofenac+miso → rinviato a Nota 66
    "N13-002",  # NON RIMBORSABILE: scope/inclusion failure su statina
    "N97-026",  # RIMBORSABILE warfarin + raccomandazioni cliniche
    "N66-020",  # NON_DETERMINABILE: dati mancanti
]


def _load_names() -> dict[str, list[str]]:
    return json.loads(_NAMES_FILE.read_text(encoding="utf-8"))


def _stable_hash(s: str) -> int:
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest(), 16)


# Anamnesi/allergie/comorbidità "vanity" — generate deterministicamente in base a
# (case_id, patient_data) per dare colore alla card senza alterare la logica.
_ALLERGIES = [
    "nessuna nota", "penicillina", "FANS (rash cutaneo)",
    "iodio (mezzo di contrasto)", "lattosio", "polvere/acari", "amoxicillina",
]
_COMORBIDITIES = [
    "Iperuricemia", "BPCO lieve", "Osteoartrosi", "Insonnia cronica",
    "Glaucoma in trattamento", "Cefalea tensiva ricorrente",
    "Reflusso gastroesofageo", "Sindrome metabolica", "Dislipidemia mista",
]
_OCCUPATIONS = [
    "Insegnante in pensione", "Impiegato comunale", "Operaio metalmeccanico",
    "Casalinga", "Imprenditore agricolo", "Infermiere", "Commerciante",
    "Architetto", "Meccanico", "Pensionato statale",
]


def _patient_identity(case_id: str, sesso: str | None) -> dict[str, str]:
    names = _load_names()
    h = _stable_hash(case_id)
    if sesso == "F":
        first = names["first_names_female"][h % len(names["first_names_female"])]
    elif sesso == "M":
        first = names["first_names_male"][h % len(names["first_names_male"])]
    else:
        # No sex: pick deterministically from the union
        pool = names["first_names_male"] + names["first_names_female"]
        first = pool[h % len(pool)]
        # Infer a sex for display purposes only
        sesso = "M" if first in names["first_names_male"] else "F"
    last = names["last_names"][(h // 7) % len(names["last_names"])]
    full = f"{first} {last}"
    initials = (first[:1] + last[:1]).upper()
    # Audit fix 2026-05-06 (A4 P0-4): generate avatar locally as a data-URI
    # SVG with the patient's initials, instead of hitting api.dicebear.com.
    # Previous behaviour leaked the synthetic patient name + viewer's IP to a
    # third-party service on every card render — unacceptable for a clinical
    # demo, even with synthetic data.
    bg_palette = ["b6e3f4", "c0aede", "d1d4f9", "ffd5dc", "ffdfbf"]
    bg = bg_palette[h % len(bg_palette)]
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        f"<rect width='64' height='64' fill='#{bg}'/>"
        f"<text x='32' y='38' text-anchor='middle' font-size='24' "
        f"font-family='sans-serif' fill='#222'>{initials}</text>"
        f"</svg>"
    )
    import base64 as _b64
    avatar_url = "data:image/svg+xml;base64," + _b64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {
        "first_name": first, "last_name": last, "full_name": full,
        "avatar_url": avatar_url, "initials": initials, "inferred_sex": sesso,
    }


def _vanity_profile(case_id: str, ident: dict, age: int | None) -> dict:
    """Genera anamnesi, allergie, occupazione, codice fiscale fake — solo per la demo."""
    h = _stable_hash(case_id + "vanity")
    occ = _OCCUPATIONS[h % len(_OCCUPATIONS)]
    allergy = _ALLERGIES[(h // 11) % len(_ALLERGIES)]
    n_comorb = (h % 3)
    comorbidities = []
    for i in range(n_comorb):
        comorbidities.append(_COMORBIDITIES[(h // (13 + i)) % len(_COMORBIDITIES)])
    # Fake codice fiscale: NomeCognome + age + check digit
    cf_letters = (ident["last_name"][:3] + ident["first_name"][:3]).upper()
    cf_year = 30 + ((h // 17) % 50) if age is None else (
        max(0, min(99, 26 + 50 - age))  # very rough
    )
    cf_month = "ABCDEHLMPRST"[h % 12]
    cf_day = (h // 5) % 28 + 1
    cf = f"{cf_letters}{str(cf_year).zfill(2)}{cf_month}{str(cf_day).zfill(2)}H501Z"  # fake but plausible
    phone = f"+39 3{(h % 9)+1}{(h // 3) % 10} {(h // 7) % 1000:03d} {(h // 11) % 10000:04d}"
    cities = ["Trieste", "Udine", "Pordenone", "Gorizia", "Monfalcone", "Codroipo"]
    city = cities[h % len(cities)]
    return {
        "occupation": occ,
        "allergies": allergy,
        "other_comorbidities": comorbidities,
        "fiscal_code": cf,
        "phone": phone,
        "city": city,
    }


# --- Mappa flag → label/icona/severità per il "quadro clinico" ---
_FLAG_META: dict[str, tuple[str, str, str]] = {
    # nota_id-relevant
    "diagnosi_fanv": ("Fibrillazione atriale non valvolare", "💓", "info"),
    "ecg_confermato": ("ECG di conferma", "📈", "info"),
    "valutazione_clinica_eseguita": ("Valutazione clinica eseguita", "🩺", "info"),
    "scompenso_cardiaco": ("Scompenso cardiaco", "❤️‍🩹", "warn"),
    "scompenso_grave": ("Scompenso grave", "🚨", "danger"),
    "ipertensione_arteriosa": ("Ipertensione arteriosa", "🩸", "warn"),
    "diabete_mellito": ("Diabete mellito", "🍬", "warn"),
    "pregresso_ictus_tia_te": ("Pregresso ictus / TIA / TE", "🧠", "danger"),
    "vasculopatia": ("Vasculopatia periferica", "🦵", "warn"),
    "protesi_valvolari_meccaniche": ("Protesi valvolari meccaniche", "⚙️", "warn"),
    "fa_valvolare": ("FA valvolare (controindicazione DOAC)", "⚙️", "danger"),
    "emorragia_maggiore_in_atto": ("Emorragia maggiore in atto", "🩸", "danger"),
    "diatesi_emorragica_congenita": ("Diatesi emorragica congenita", "🩸", "danger"),
    "gravidanza": ("Gravidanza", "🤰", "warn"),
    "ipersensibilita_farmaco": ("Ipersensibilità al farmaco", "⚠️", "danger"),
    "trattamento_cronico_fans": ("Trattamento cronico con FANS", "💊", "warn"),
    "terapia_antiaggregante_asa": ("Antiaggregante ASA a basse dosi", "💊", "warn"),
    "pregresse_emorragie_digestive": ("Pregresse emorragie digestive", "🩸", "danger"),
    "ulcera_peptica_non_guarita": ("Ulcera peptica non guarita", "🔴", "danger"),
    "terapia_concomitante_anticoagulanti": ("Anticoagulanti concomitanti", "🩸", "warn"),
    "terapia_concomitante_cortisonici": ("Cortisonici concomitanti", "💊", "warn"),
    "eta_avanzata": ("Età avanzata", "🧓", "warn"),
    "ipercolesterolemia_familiare": ("Ipercolesterolemia familiare", "🧬", "warn"),
    "intolleranza_statine": ("Intolleranza alle statine", "🚫", "warn"),
    "comorbidita_grave": ("Comorbidità grave", "🚨", "danger"),
    "rischio_cardiovascolare": ("Rischio cardiovascolare elevato", "⚠️", "warn"),
    "dislipidemia_diagnosticata": ("Dislipidemia diagnosticata", "📉", "warn"),
    "ipotiroidismo_escluso": ("Ipotiroidismo escluso", "✓", "info"),
    "dieta_seguita_almeno_3_mesi": ("Dieta seguita ≥ 3 mesi", "🥗", "info"),
    "pregresse_complicanze_gastriche": ("Pregresse complicanze gastriche", "🩸", "danger"),
    "epatopatia_attiva": ("Epatopatia attiva", "🟡", "danger"),
    "abuso_alcool": ("Abuso di alcool", "🍷", "warn"),
    "farmaci_epatotossici_concomitanti": ("Farmaci epatotossici concomitanti", "💊", "warn"),
}


def _meta_for_flag(key: str) -> tuple[str, str, str]:
    if key in _FLAG_META:
        return _FLAG_META[key]
    return (key.replace("_", " "), "•", "info")


def positive_clinical_flags(patient_data: dict) -> list[dict[str, str]]:
    """Restituisce {label, icon, severity, key} per ogni flag booleano True."""
    out: list[dict[str, str]] = []
    for k, v in patient_data.items():
        if v is True:
            label, icon, sev = _meta_for_flag(k)
            out.append({"label": label, "icon": icon, "severity": sev, "key": k})
    return out


_NUMERIC_LABELS = {
    "paziente_eta": ("Età", "anni"),
    "paziente_peso_kg": ("Peso", "kg"),
    "vfg_cockroft_gault": ("VFG (Cockroft-Gault)", "mL/min"),
    "creatinina_sierica": ("Creatinina sierica", "mg/dL"),
    "ldl_mg_dl": ("LDL", "mg/dL"),
    "rischio_cv_score_pct": ("Rischio CV (10 anni)", "%"),
    "ttr_pct": ("TTR (Time in Therapeutic Range)", "%"),
    "inr": ("INR", ""),
}


def numeric_clinical_values(patient_data: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for k, (lbl, unit) in _NUMERIC_LABELS.items():
        v = patient_data.get(k)
        if v is not None and not isinstance(v, bool):
            out.append({"label": lbl, "value": v, "unit": unit, "key": k})
    return out


# Drug → therapeutic class (per chip card)
_DRUG_CLASS = {
    # DOAC / AVK
    "apixaban": ("Anticoagulante DOAC", "💊", "info"),
    "dabigatran": ("Anticoagulante DOAC", "💊", "info"),
    "edoxaban": ("Anticoagulante DOAC", "💊", "info"),
    "rivaroxaban": ("Anticoagulante DOAC", "💊", "info"),
    "warfarin": ("Anticoagulante AVK", "💊", "info"),
    "acenocumarolo": ("Anticoagulante AVK", "💊", "info"),
    # PPI
    "omeprazolo": ("Inibitore di pompa protonica", "💊", "info"),
    "pantoprazolo": ("Inibitore di pompa protonica", "💊", "info"),
    "lansoprazolo": ("Inibitore di pompa protonica", "💊", "info"),
    "esomeprazolo": ("Inibitore di pompa protonica", "💊", "info"),
    "rabeprazolo": ("Inibitore di pompa protonica", "💊", "info"),
    "misoprostolo": ("Analogo prostaglandinico (gastroprotettore)", "💊", "info"),
    "diclofenac_misoprostolo": ("FANS + gastroprotettore (Nota 66)", "💊", "warn"),
    # Statine
    "atorvastatina": ("Statina", "💊", "info"),
    "rosuvastatina": ("Statina", "💊", "info"),
    "simvastatina": ("Statina", "💊", "info"),
    "pravastatina": ("Statina", "💊", "info"),
    "fluvastatina": ("Statina", "💊", "info"),
    "lovastatina": ("Statina", "💊", "info"),
    "ezetimibe": ("Inibitore assorbimento colesterolo", "💊", "info"),
    "ezetimibe_simvastatina": ("Combinazione ezetimibe + statina", "💊", "info"),
    # FANS
    "diclofenac": ("FANS (acido acetico)", "💊", "info"),
    "ibuprofene": ("FANS (acido propionico)", "💊", "info"),
    "ketoprofene": ("FANS (acido propionico)", "💊", "info"),
    "naprossene": ("FANS (acido propionico)", "💊", "info"),
    "nimesulide": ("FANS (sulfonanilide, epatotossico)", "💊", "danger"),
    "meloxicam": ("FANS (oxicam)", "💊", "info"),
    "piroxicam": ("FANS (oxicam)", "💊", "info"),
    "celecoxib": ("Coxib (COX-2 selettivo)", "💊", "info"),
    "etoricoxib": ("Coxib (COX-2 selettivo)", "💊", "info"),
    "indometacina": ("FANS (acido acetico)", "💊", "info"),
}


def drug_class(drug_id: str) -> tuple[str, str, str]:
    return _DRUG_CLASS.get(drug_id, ("Farmaco", "💊", "info"))


def humanize_category(category: str) -> str:
    """Trasforma 'RIMBORSABILE_inclusion' in 'Caso standard di inclusione', ecc."""
    if not category:
        return ""
    cat = category.lower()
    if "standard" in cat:
        return "Caso standard"
    if "excl_hard" in cat:
        return "Esclusione assoluta"
    if "scope" in cat:
        return "Fuori ambito Nota"
    if "inclusion" in cat:
        return "Criterio di inclusione"
    if "pathway" in cat:
        return "Percorso clinico richiesto"
    if "guidance" in cat or "warning" in cat:
        return "Decisione con avvertenze"
    if "boundary" in cat:
        return "Caso di frontiera"
    if "routed" in cat:
        return "Reindirizzamento ad altra Nota"
    if "bypass" in cat:
        return "Eccezione bypass"
    if "with_warning" in cat or "guidance" in cat:
        return "Con flag di guida clinica"
    if "non_det" in cat or "missing" in cat or "unknown" in cat:
        return "Dati mancanti"
    return category.replace("_", " ").capitalize()


def case_complexity_score(case: dict) -> int:
    """0-3: numero di flag clinici positivi raggruppati in fasce."""
    n = len(positive_clinical_flags(case["patient_data"]))
    if n <= 2:
        return 1
    if n <= 5:
        return 2
    return 3


def load_gold_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for nota in ("01", "13", "66", "97"):
        f = _GOLD_DIR / f"nota_{nota}_cases.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for c in data.get("cases", []):
            pd = c["input"].get("patient_data", {})
            sesso = pd.get("paziente_sesso")
            eta = pd.get("paziente_eta")
            ident = _patient_identity(c["id"], sesso)
            decision = c["expected_rule_engine"].get("reimbursement_decision")
            decision_status = c["expected_rule_engine"].get("decision_status", "")
            d_class, d_icon, d_sev = drug_class(c["input"].get("drug_id", ""))
            cases.append({
                "case_id": c["id"],
                "nota_id": c["input"].get("nota_id", nota),
                "drug_id": c["input"].get("drug_id", ""),
                "drug_class_label": d_class,
                "drug_icon": d_icon,
                "drug_severity": d_sev,
                "category": c.get("category", ""),
                "category_human": humanize_category(c.get("category", "")),
                "description": c.get("description", ""),
                "tags": c.get("tags", []),
                "patient_data": pd,
                "clinician_asserted": c["input"].get("clinician_asserted", {}),
                "expected_decision": decision,
                "expected_status": decision_status,
                "expected_route_to": c["expected_rule_engine"].get("route_to"),
                "expected_blocking_rule_ids": c["expected_rule_engine"].get("expected_blocking_rule_ids", []),
                "pdf_reference": c.get("pdf_reference", {}),
                "patient_sex": sesso or ident.get("inferred_sex"),
                "patient_age": eta,
                "complexity": case_complexity_score({"patient_data": pd}),
                **ident,
                "vanity": _vanity_profile(c["id"], ident, eta),
            })
    cases.sort(key=lambda x: x["case_id"])
    return cases


def get_case_by_id(case_id: str) -> dict | None:
    for c in load_gold_cases():
        if c["case_id"] == case_id:
            return c
    return None


if __name__ == "__main__":
    cs = load_gold_cases()
    print(f"Loaded {len(cs)} cases")
    for c in cs[:3]:
        print(f"  {c['case_id']}: {c['full_name']} ({c['patient_sex']} {c['patient_age']}a) "
              f"-> {c['drug_id']} [{c['drug_class_label']}] -> "
              f"{c['expected_decision']} [{c['category_human']}] complexity={c['complexity']}")
        print(f"    vanity: {c['vanity']}")
