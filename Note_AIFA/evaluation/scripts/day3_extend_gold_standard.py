"""
Day 3 audit fix: extend gold standard to address bias coverage gaps.

Adds:
- 10 new Nota 13 cases covering drug diversity (other statins, ezetimibe,
  fibrates, PUFA-N3) — addresses F3-4 ALTO (95% atorvastatina bias).
- 6 new Nota 97 female cases — addresses F3-5 MEDIO (84% male bias).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_GOLD = _HERE.parent / "gold_standard"


# ── Nota 13: drug diversity expansion ────────────────────────────────────────

# Each case here covers a specific drug missing from the existing gold standard
# (which is 95% atorvastatina). Score 6.0 → "alto" risk → standard 1st-line statin
# is appropriate. dieta_seguita_almeno_3_mesi=True for non-bypass cases.
N13_NEW_CASES = [
    {
        "id": "N13-023",
        "description": "RIMBORSABILE — simvastatina, rischio alto (score=6%), terapia 1° livello attempted",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "simvastatina", "nota13", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "simvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Drug diversity case — simvastatina (1st-line statin)"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 1,
            "section": "Box prescrittivo",
            "excerpt": "Ipercolesterolemia non corretta dalla sola dieta, seguita per almeno tre mesi"
        }
    },
    {
        "id": "N13-024",
        "description": "RIMBORSABILE — pravastatina, rischio alto, copertura drug diversity",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "pravastatina", "nota13", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "pravastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Drug diversity case — pravastatina"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 1,
            "section": "Box prescrittivo",
            "excerpt": "Ipercolesterolemia non corretta dalla sola dieta"
        }
    },
    {
        "id": "N13-025",
        "description": "RIMBORSABILE — fluvastatina, rischio alto, drug diversity",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "fluvastatina", "nota13", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "fluvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Drug diversity case — fluvastatina"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 1,
            "section": "Box prescrittivo",
            "excerpt": "Ipercolesterolemia non corretta dalla sola dieta"
        }
    },
    {
        "id": "N13-026",
        "description": "RIMBORSABILE — lovastatina, rischio alto, drug diversity",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "lovastatina", "nota13", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "lovastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Drug diversity case — lovastatina"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 1,
            "section": "Box prescrittivo",
            "excerpt": "Ipercolesterolemia non corretta dalla sola dieta"
        }
    },
    {
        "id": "N13-027",
        "description": "RIMBORSABILE — rosuvastatina, rischio molto alto (score=12%), 1st-line statin",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "rosuvastatina", "nota13", "molto_alto_rischio", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "rosuvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 12.0,
                "colesterolo_ldl": 80.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Drug diversity — rosuvastatina in molto_alto risk"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 2,
            "section": "Tabella categorie di rischio",
            "excerpt": "rosuvastatina nei pazienti in cui ci sia stata evidenza di effetti collaterali severi"
        }
    },
    {
        "id": "N13-028",
        "description": "RIMBORSABILE — ezetimibe in monoterapia con intolleranza statine (V3.4 with new fields)",
        "category": "RIMBORSABILE_bypass_exception",
        "tags": ["rimborsabile", "ezetimibe", "nota13", "intolleranza_statine", "drug_diversity"],
        "input": {
            "nota_id": "13",
            "drug_id": "ezetimibe",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": False,  # bypass via intolleranza
                "intolleranza_statine": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Ezetimibe via intolleranza statine bypass"
        },
        "pdf_reference": {
            "rule_id": "N13_EXCEPT_002",
            "pdf_file": "nota-13.pdf",
            "page": 2,
            "section": "Footnote (**)",
            "excerpt": "Nei pazienti che siano intolleranti alle statine, per il conseguimento del target terapeutico è rimborsato il trattamento con ezetimibe in monoterapia"
        }
    },
    {
        "id": "N13-029",
        "description": "NON_RIMBORSABILE — simvastatina prescritta a paziente neo-diagnosticato senza dieta tentata (regression test for V3.4 step-care fix)",
        "category": "NON_RIMBORSABILE_inclusion",
        "tags": ["non_rimborsabile", "simvastatina", "nota13", "step_care_test"],
        "input": {
            "nota_id": "13",
            "drug_id": "simvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": False,
                "terapia_primo_livello_tentata": False,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N13_INCL_001"],
            "expected_clinical_flag_rule_ids": ["N13_GWARN_001"],
        },
        "explanation_criteria": {
            "must_contain_strings": ["NON_RIMBORSABILE"],
            "must_not_contain_strings": ["RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Step-care V3.4 regression: dieta NOT tried + 1st-line NOT tried → INCL_001 blocks"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 1,
            "section": "Box prescrittivo",
            "excerpt": "Ipercolesterolemia non corretta dalla sola dieta, seguita per almeno tre mesi"
        }
    },
    {
        "id": "N13-030",
        "description": "RIMBORSABILE con WARNING — atorvastatina prescritta come 1st-line a neo-diagnosticato (Day 2 GUIDANCE_WARN — non blocca)",
        "category": "RIMBORSABILE_with_guidance",
        "tags": ["rimborsabile", "atorvastatina", "nota13", "step_care_warning"],
        "input": {
            "nota_id": "13",
            "drug_id": "atorvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": False,  # neo-prescritta
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": ["N13_GWARN_001"],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "V3.4: neo-prescribed atorvastatina with no prior 1st-line → RIMB + WARN"
        },
        "pdf_reference": {
            "rule_id": "N13_GWARN_001",
            "pdf_file": "nota-13.pdf",
            "page": 4,
            "section": "Approfondimenti",
            "excerpt": "L'impiego di farmaci di seconda ed eventualmente terza scelta può essere ammesso solo quando il trattamento di prima linea"
        }
    },
    {
        "id": "N13-031",
        "description": "RIMBORSABILE — categoria_medio (score=2.5%, V3.4 new category) target LDL 130",
        "category": "RIMBORSABILE_standard",
        "tags": ["rimborsabile", "atorvastatina", "nota13", "categoria_medio_v34"],
        "input": {
            "nota_id": "13",
            "drug_id": "atorvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 2.5,  # categoria_medio
                "colesterolo_ldl": 140.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "V3.4 new category 'medio' (score >1% e <4% per PDF p.6)"
        },
        "pdf_reference": {
            "rule_id": "N13_INCL_001",
            "pdf_file": "nota-13.pdf",
            "page": 6,
            "section": "Classificazione in base al livello di rischio",
            "excerpt": "I pazienti con risk score >1% e <4% sono da considerare a rischio medio"
        }
    },
    {
        "id": "N13-032",
        "description": "NON_RIMBORSABILE — paziente intollerante statine prescritto simvastatina (V3.4 regression test for N13_EXCEPT_002 drug-aware fix is FUTURE work; current behavior: bypass fires anyway)",
        "category": "RIMBORSABILE_bypass_exception",
        "tags": ["rimborsabile", "simvastatina", "nota13", "intolleranza_test"],
        "input": {
            "nota_id": "13",
            "drug_id": "simvastatina",
            "patient_data": {
                "dislipidemia_diagnosticata": True,
                "ipotiroidismo_escluso": True,
                "risk_score_cvd_fatale_10y": 6.0,
                "colesterolo_ldl": 130.0,
            },
            "clinician_asserted": {
                "dieta_seguita_almeno_3_mesi": False,
                "intolleranza_statine": True,
                "terapia_primo_livello_tentata": True,
            },
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Bypass intolleranza_statine fires for any drug (current; F1-N13-Div#6 ALTO future fix would require drug-aware bypass)"
        },
        "pdf_reference": {
            "rule_id": "N13_EXCEPT_002",
            "pdf_file": "nota-13.pdf",
            "page": 2,
            "section": "Footnote (**)",
            "excerpt": "Nei pazienti che siano intolleranti alle statine, per il conseguimento del target terapeutico è rimborsato il trattamento con ezetimibe in monoterapia"
        }
    },
]


# ── Nota 97: female cases expansion ──────────────────────────────────────────

N97_NEW_CASES = [
    {
        "id": "N97-035",
        "description": "RIMBORSABILE — F, age 72, scompenso+HTN+DM+Sc (score=5, F threshold=3) → eligible",
        "category": "RIMBORSABILE_female",
        "tags": ["rimborsabile", "apixaban", "nota97", "cha2ds2vasc", "female"],
        "input": {
            "nota_id": "97",
            "drug_id": "apixaban",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "F", "paziente_eta": 72,
                "scompenso_cardiaco": True, "ipertensione_arteriosa": True, "diabete_mellito": True,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 85.0, "paziente_peso_kg": 70.0, "creatinina_sierica": 0.9,
                "emorragia_maggiore_in_atto": False, "diatesi_emorragica_congenita": False,
                "gravidanza": False, "ipersensibilita_farmaco": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "F sex coverage — should mention F threshold 3"
        },
        "pdf_reference": {"rule_id": "N97_PATH_001", "pdf_file": "nota-97.pdf", "page": 3, "section": "Percorso C", "excerpt": "in tutti i pazienti con punteggio CHA2DS2-VASc"}
    },
    {
        "id": "N97-036",
        "description": "NON_RIMBORSABILE — F, score=2 (HTN+Sc only) below F threshold=3",
        "category": "NON_RIMBORSABILE_pathway",
        "tags": ["non_rimborsabile", "apixaban", "nota97", "cha2ds2vasc", "female"],
        "input": {
            "nota_id": "97",
            "drug_id": "apixaban",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "F", "paziente_eta": 60,
                "scompenso_cardiaco": False, "ipertensione_arteriosa": True, "diabete_mellito": False,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 85.0, "paziente_peso_kg": 65.0, "creatinina_sierica": 0.9,
                "emorragia_maggiore_in_atto": False, "diatesi_emorragica_congenita": False,
                "gravidanza": False, "ipersensibilita_farmaco": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N97_PATH_001"],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["NON_RIMBORSABILE"],
            "must_not_contain_strings": ["RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "F score=2 below threshold 3"
        },
        "pdf_reference": {"rule_id": "N97_PATH_001", "pdf_file": "nota-97.pdf", "page": 3, "section": "Percorso C", "excerpt": "≥3 (se femmine)"}
    },
    {
        "id": "N97-037",
        "description": "NON_RIMBORSABILE — F gravidanza (V3.4 EXCL_HARD_ALL2_GRAVIDANZA)",
        "category": "NON_RIMBORSABILE_excl_hard",
        "tags": ["non_rimborsabile", "warfarin", "nota97", "gravidanza", "female", "v3_4_allegato2"],
        "input": {
            "nota_id": "97",
            "drug_id": "warfarin",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "F", "paziente_eta": 32,
                "scompenso_cardiaco": False, "ipertensione_arteriosa": True, "diabete_mellito": False,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 95.0, "paziente_peso_kg": 60.0, "creatinina_sierica": 0.7,
                "emorragia_maggiore_in_atto": False, "diatesi_emorragica_congenita": False,
                "gravidanza": True,  # ← controindicazione assoluta Allegato 2
                "ipersensibilita_farmaco": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N97_EXCL_HARD_ALL2_GRAVIDANZA"],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["NON_RIMBORSABILE"],
            "must_not_contain_strings": ["RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "Allegato 2 absolute contraindication — gravidanza"
        },
        "pdf_reference": {"rule_id": "N97_EXCL_HARD_ALL2_GRAVIDANZA", "pdf_file": "nota-97-all-2.pdf", "page": 2, "section": "Principali controindicazioni/avvertenze", "excerpt": "sconsigliano fortemente l'inizio di una terapia anticoagulante con AVK o NAO/DOAC: la gravidanza"}
    },
    {
        "id": "N97-038",
        "description": "NON_RIMBORSABILE — emorragia maggiore in atto (V3.4 EXCL_HARD_ALL2_EMORRAGIA)",
        "category": "NON_RIMBORSABILE_excl_hard",
        "tags": ["non_rimborsabile", "apixaban", "nota97", "emorragia_atto", "v3_4_allegato2"],
        "input": {
            "nota_id": "97",
            "drug_id": "apixaban",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "M", "paziente_eta": 72,
                "scompenso_cardiaco": True, "ipertensione_arteriosa": True, "diabete_mellito": True,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 85.0, "paziente_peso_kg": 75.0, "creatinina_sierica": 0.9,
                "emorragia_maggiore_in_atto": True,  # ← controindicazione assoluta
                "diatesi_emorragica_congenita": False,
                "gravidanza": False, "ipersensibilita_farmaco": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N97_EXCL_HARD_ALL2_EMORRAGIA"],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["NON_RIMBORSABILE"],
            "must_not_contain_strings": ["RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "V3.4 Allegato 2: emorragia maggiore in atto"
        },
        "pdf_reference": {"rule_id": "N97_EXCL_HARD_ALL2_EMORRAGIA", "pdf_file": "nota-97-all-2.pdf", "page": 2, "section": "Principali controindicazioni/avvertenze", "excerpt": "una emorragia maggiore in atto"}
    },
    {
        "id": "N97-039",
        "description": "RIMBORSABILE — F, age 76 (Sc=F + age≥75=A2 +HTN = score 4) eligible",
        "category": "RIMBORSABILE_female",
        "tags": ["rimborsabile", "dabigatran", "nota97", "cha2ds2vasc", "female", "elderly"],
        "input": {
            "nota_id": "97",
            "drug_id": "dabigatran",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "F", "paziente_eta": 76,
                "scompenso_cardiaco": False, "ipertensione_arteriosa": True, "diabete_mellito": False,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 60.0, "paziente_peso_kg": 65.0, "creatinina_sierica": 1.0,
                "emorragia_maggiore_in_atto": False, "diatesi_emorragica_congenita": False,
                "gravidanza": False, "ipersensibilita_farmaco": False,
                "uso_verapamil": False, "aumentato_rischio_sanguinamento": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": ["N97_GWARN_004"],  # Block B 75-80 + VFG 30-50
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "F elderly + dabigatran 75-80 Block B"
        },
        "pdf_reference": {"rule_id": "N97_GWARN_004", "pdf_file": "nota-97-all-2.pdf", "page": 6, "section": "Tab. 4", "excerpt": "fra i 75 e gli 80 anni"}
    },
    {
        "id": "N97-040",
        "description": "RIMBORSABILE — F, score=4 (HTN+DM+Sc), apixaban — eligible (above F threshold)",
        "category": "RIMBORSABILE_female",
        "tags": ["rimborsabile", "apixaban", "nota97", "female"],
        "input": {
            "nota_id": "97",
            "drug_id": "apixaban",
            "patient_data": {
                "diagnosi_fanv": True, "ecg_confermato": True, "valutazione_clinica_eseguita": True,
                "paziente_sesso": "F", "paziente_eta": 68,
                "scompenso_cardiaco": True, "ipertensione_arteriosa": True, "diabete_mellito": True,
                "pregresso_ictus_tia_te": False, "vasculopatia": False,
                "protesi_valvolari_meccaniche": False, "fa_valvolare": False,
                "vfg_cockroft_gault": 75.0, "paziente_peso_kg": 70.0, "creatinina_sierica": 0.95,
                "emorragia_maggiore_in_atto": False, "diatesi_emorragica_congenita": False,
                "gravidanza": False, "ipersensibilita_farmaco": False,
            },
            "clinician_asserted": {},
        },
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "explanation_criteria": {
            "must_contain_strings": ["RIMBORSABILE"],
            "must_not_contain_strings": ["NON_RIMBORSABILE"],
            "required_sections": ["1. DECISIONE", "2. MOTIVAZIONE", "3. RACCOMANDAZIONI", "4. DATI MANCANTI", "5. FONTI"],
            "expected_citation_count_min": 1,
            "notes": "F sex coverage standard apixaban"
        },
        "pdf_reference": {"rule_id": "N97_PATH_001", "pdf_file": "nota-97.pdf", "page": 3, "section": "Percorso C", "excerpt": "in tutti i pazienti con punteggio CHA2DS2-VASc"}
    },
]


def main() -> int:
    # Nota 13
    path13 = _GOLD / "nota_13_cases.json"
    with open(path13, encoding="utf-8") as f:
        data13 = json.load(f)
    n_existing_13 = len(data13["cases"])
    data13["cases"].extend(N13_NEW_CASES)
    with open(path13, "w", encoding="utf-8") as f:
        json.dump(data13, f, indent=2, ensure_ascii=False)
    print(f"Nota 13: {n_existing_13} → {len(data13['cases'])} cases (+{len(N13_NEW_CASES)} drug diversity)")

    # Nota 97
    path97 = _GOLD / "nota_97_cases.json"
    with open(path97, encoding="utf-8") as f:
        data97 = json.load(f)
    n_existing_97 = len(data97["cases"])
    data97["cases"].extend(N97_NEW_CASES)
    with open(path97, "w", encoding="utf-8") as f:
        json.dump(data97, f, indent=2, ensure_ascii=False)
    print(f"Nota 97: {n_existing_97} → {len(data97['cases'])} cases (+{len(N97_NEW_CASES)} female + Allegato 2)")

    print(f"\nTotal: 100 → {len(data13['cases']) + 26 + len(data97['cases']) + 18} gold cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
