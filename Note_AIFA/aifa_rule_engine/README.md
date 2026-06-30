# AIFA Rule Engine — v3.4.0

Deterministic Rule Engine for AIFA Note (01, 66, 97, 13).
Symbolic layer of a neuro-symbolic RAG-based CDSS (thesis project).

**Stato corrente (2026-05-04):** 44 regole YAML, 960 unit-test passing,
122/122 gold standard cases passing (Macro F1 = 1.000), Wilson 95% CI ≈
[0.969, 1.000]. Vedi `audit/REPORT_FINALE.md` + `audit/09_post_fix_report.md`.

## Architecture

```
POST /evaluate
  ↓
Phase 0: merge clinician_asserted + compute_derived_vars
Phase 1: SCOPE       (fail-fast on FALSE)
Phase 2: EXCEPTION   (ROUTE / BYPASS / NON_RIMB)
Phase 3: EXCL_HARD   (fail-fast on TRUE)
Phase 4: INCLUSION   (fail-fast on FALSE)
Phase 5: PATHWAY     (fail-fast on FALSE)
Phase 6: GUIDANCE_DOSE
Phase 7: GUIDANCE_PREF
Phase 8: GUIDANCE_WARN
Phase 9: Dose conflict resolution
Phase 10: Finalize + Invariant I-1 (Dose-on-Denial)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest tests/ -v
```

## Start server

```bash
uvicorn aifa_rule_engine.api.main:app --reload --port 8000
```

## API example

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "3.3",
    "note_id": "97",
    "drug_id": "apixaban",
    "patient_data": {
      "diagnosi_fanv": true,
      "ecg_confermato": true,
      "valutazione_clinica_eseguita": true,
      "paziente_sesso": "M",
      "paziente_eta": 72,
      "scompenso_cardiaco": true,
      "ipertensione_arteriosa": true,
      "diabete_mellito": true,
      "vfg_cockroft_gault": 85.0
    }
  }' | python3 -m json.tool
```

Expected: `"reimbursement_decision": "RIMBORSABILE"`

## TODOs left from plan

| Rule group | Plan reference | Status | Note |
|---|---|---|---|
| `N97_GWARN_PERIOP_*` | `nota-97-all-3.pdf` Allegato 3 | TODO | Gestione perioperatoria (sospensione/ripresa anticoagulante peri-chirurgico). Richiede 4-6 nuovi campi al data dictionary (es. `procedura_chirurgica_prevista`, `data_intervento`, `livello_rischio_emorragico_chirurgia`). |
| `N97_GWARN_ATTENTION_*` (×9) | `nota-97-all-2.pdf` p.2-3 §"particolare attenzione" + audit `01_nota97_fedelta.md` F1-N97-U1 | TODO | 9 condizioni cliniche da modellare come `GUIDANCE_WARN` (informative, non blocking): piastrinopenia, ipertensione grave non controllata, ulcera GI recente, neoplasie sanguinanti, sindrome da malassorbimento, insufficienza epatica moderata, anziano fragile, polifarmacia, peso estremo. |

Queste regole sono **intenzionalmente non implementate** per vincolo del piano
Sezione B ("Se una regola è TODO nel piano, NON inventarla"). La loro assenza
**non altera** la classificazione `RIMBORSABILE/NON_RIMBORSABILE` del sistema
attuale (sarebbero solo flag informativi addizionali); è discussa nel cap.
"Future Work" della tesi.

**Scelte interpretative documentate:**

| Item | Scelta interpretativa | Riferimento |
|---|---|---|
| CHA2DS2-VASc threshold | `≥` (ESC alignment) anziché `>` letterale del PDF | Test dedicato `test_v34_audit_fixes.py::TestV34_CHA2DS2_Interpretation` + audit `09_post_fix_report.md` F1-N97-Div#1 |
