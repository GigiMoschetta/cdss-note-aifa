"""
Data Dictionary — canonical patient-data fields, types, and notes.

Used at startup for:
- IS_TRUE domain validation (only boolean fields)
- required_variables inference cross-check
"""
from __future__ import annotations

from typing import Literal

FieldType = Literal["boolean", "numeric", "string", "enum"]


FIELD_REGISTRY: dict[str, FieldType] = {
    # ---- Nota 01 / 66 shared ----
    "trattamento_cronico_fans":              "boolean",
    "terapia_antiaggregante_asa":            "boolean",
    "farmaco_prescritto":                    "string",
    "pregresse_emorragie_digestive":         "boolean",
    "ulcera_peptica_non_guarita":            "boolean",
    "terapia_concomitante_anticoagulanti":   "boolean",
    "terapia_concomitante_cortisonici":      "boolean",
    "eta_avanzata":                          "boolean",  # clinician-asserted
    # ---- Nota 66 ----
    "indicazione_clinica":                   "string",
    "uso_breve_durata":                      "boolean",
    "seconda_linea":                         "boolean",
    "ulcera_peptica_attiva_pregressa":       "boolean",
    "scompenso_cardiaco_grave":              "boolean",
    "cardiopatia_ischemica":                 "boolean",
    "patologia_cerebrovascolare":            "boolean",
    "patologia_arteriosa_periferica":        "boolean",
    "scompenso_cardiaco_moderato_grave":     "boolean",
    "epatopatia":                            "boolean",
    # Audit Day 2 fix F1-N66-Div#2 ALTO: nimesulide cofattori PDF p.4 verbatim
    # "controindicata nei pazienti epatopatici, in quelli con una storia di
    # abuso di alcool e negli assuntori di altri farmaci epatotossici"
    "abuso_alcool":                          "boolean",  # clinician-asserted
    "farmaci_epatotossici_concomitanti":     "boolean",  # clinician-asserted
    # Audit Day 2 fix F1-N66-Div#3 ALTO: allergia ad ASA o FANS (PDF p.4)
    # "controindicati nei soggetti con anamnesi positiva per allergia ad
    # aspirina o a un altro FANS, inclusi coloro in cui un episodio di
    # asma, angioedema, orticaria o rinite sia stato scatenato dall'assunzione
    # di aspirina o di un altro FANS"
    "allergia_asa_o_fans":                   "boolean",  # clinician-asserted
    "is_coxib":                              "boolean",  # derived
    "dolore_acuto_moderato":                 "boolean",
    "non_controllato_con_singoli":           "boolean",
    # ---- Nota 97 ----
    "diagnosi_fanv":                         "boolean",
    "ecg_confermato":                        "boolean",
    "valutazione_clinica_eseguita":          "boolean",
    "scompenso_cardiaco":                    "boolean",
    "ipertensione_arteriosa":                "boolean",
    "diabete_mellito":                       "boolean",
    "pregresso_ictus_tia_te":               "boolean",
    "vasculopatia":                          "boolean",
    "protesi_valvolari_meccaniche":          "boolean",
    "fa_valvolare":                          "boolean",
    "paziente_eta":                          "numeric",
    "paziente_sesso":                        "enum",     # "M" | "F"
    "paziente_peso_kg":                      "numeric",
    "creatinina_sierica":                    "numeric",
    "vfg_cockroft_gault":                    "numeric",
    "emoglobina":                            "numeric",
    "ttr_sotto_70":                          "boolean",  # clinician-asserted
    "difficolta_monitoraggio_inr":           "boolean",  # clinician-asserted
    "pregressa_emorragia_intracranica":      "boolean",  # clinician-asserted
    "interazioni_farmacologiche_doac":       "boolean",  # clinician-asserted
    "uso_verapamil":                         "boolean",  # clinician-asserted
    "aumentato_rischio_sanguinamento":       "boolean",  # clinician-asserted
    "in_dialisi":                            "boolean",
    "uso_inibitori_pgp":                     "boolean",
    # ---- Nota 97 Allegato 2 controindicazioni assolute ("sconsigliano fortemente") ----
    # Audit Day 2 fix F1-N97-Div#2 BLOC: 4 controindicazioni assolute mancanti
    "emorragia_maggiore_in_atto":            "boolean",  # clinician-asserted
    "diatesi_emorragica_congenita":          "boolean",  # clinician-asserted
    "gravidanza":                            "boolean",  # clinician-asserted
    "ipersensibilita_farmaco":               "boolean",  # clinician-asserted
    # Derived (Nota 97)
    "cha2ds2vasc_range":                     "string",   # ScoreRange object
    "cha2ds2vasc_threshold":                 "numeric",
    "apixaban_riduzione_count":              "boolean",  # derived from COUNT_GEQ(eta≥80, peso≤60, creat≥1.5)
    # ---- Nota 13 ----
    "dislipidemia_diagnosticata":            "boolean",
    "dieta_seguita_almeno_3_mesi":           "boolean",  # clinician-asserted
    "ipotiroidismo_escluso":                 "boolean",
    "risk_score_cvd_fatale_10y":             "numeric",
    "colesterolo_ldl":                       "numeric",
    "colesterolo_hdl":                       "numeric",
    "trigliceridi":                          "numeric",
    "malattia_coronarica_documentata":       "boolean",
    "pregresso_ictus_ischemico":             "boolean",
    "arteriopatia_periferica":               "boolean",
    "diabete_con_fattori_rischio_cv":        "boolean",
    "irc_moderata":                          "boolean",
    "irc_grave":                             "boolean",
    "terapia_primo_livello_tentata":         "boolean",  # clinician-asserted
    "target_raggiunto_con_primo_livello":    "boolean",  # clinician-asserted
    "intolleranza_statine":                  "boolean",  # clinician-asserted
    "in_terapia_haart":                      "boolean",
    "tipo_dislipidemia_familiare":           "boolean",
    "egfr_ckdepi":                           "numeric",
    # Derived (Nota 13)
    "categoria_rischio":                     "string",
    "target_ldl":                            "numeric",
    "categoria_molto_alto":                  "boolean",
    "categoria_alto":                        "boolean",
    "categoria_moderato":                    "boolean",
    "categoria_medio":                       "boolean",  # audit Day 2 fix F1-N13-Div#3
    "categoria_basso":                       "boolean",
    # API-level synthetic field
    "farmaco":                               "string",   # drug_id injected
}


BOOLEAN_FIELDS: frozenset[str] = frozenset(
    k for k, v in FIELD_REGISTRY.items() if v == "boolean"
)

NUMERIC_FIELDS: frozenset[str] = frozenset(
    k for k, v in FIELD_REGISTRY.items() if v == "numeric"
)


def get_field_type(field_name: str) -> FieldType | None:
    return FIELD_REGISTRY.get(field_name)


def is_boolean_field(field_name: str) -> bool:
    return field_name in BOOLEAN_FIELDS
