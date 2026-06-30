# AIFA CDSS — Demo Streamlit

Galleria di pazienti gold standard con avatar e card cliccabili. Per ogni
paziente: valutazione live (rule engine + RAG + LLM), trace regole, fonti PDF,
metriche pre-calcolate, modalità "what-if" per editare i flag e ri-valutare.

## Prerequisiti

- Servizi attivi: `make up-local` (rule_engine :8000 + orchestrator :8001).
- Ollama running con `llama3.1:8b` pullato.
- ChromaDB popolato: `make ingest-local` (one-time).
- Dipendenze demo: `aifa_rule_engine/.venv/bin/pip install -r demo/requirements_demo.txt`.

## Avvio

```bash
cd Note_AIFA/
make demo
# oppure
aifa_rule_engine/.venv/bin/streamlit run demo/app.py --server.port 8501
```

Apri http://localhost:8501.

## Funzionalità

- **Galleria 122 pazienti** con avatar (DiceBear personas, deterministici).
- **Filtri sidebar:** Nota AIFA, decisione attesa, categoria, ricerca testuale.
- **Vista dettaglio** per ogni paziente con quadro clinico (flag positivi + valori numerici).
- **Pulsante "Valuta paziente"** → esegue rule engine + RAG + LLM end-to-end.
- **5 tab:**
  - 📋 Spiegazione Italian a 5 sezioni dell'LLM.
  - ⚙️ Trace regole — phase 0-10, regole valutate, variabili derivate.
  - 📚 Fonti — citazioni FONTI dell'LLM + anchor verbatim del rule engine + viewer PDF.
  - 🧪 Metriche — caricate da `evaluation/results/per_case_reports/`.
  - 🔧 What-if — toggle dei flag clinici / cambio farmaco e ri-valutazione.

## Architettura

```
demo/
├── app.py                  # entry point Streamlit
├── cdss_client.py          # wrapper requests per :8000 + :8001
├── data_loader.py          # carica 122 gold cases + nome/avatar deterministici
├── components/
│   ├── patient_card.py     # card galleria
│   ├── patient_detail.py   # vista dettaglio + tabs
│   ├── trace_view.py       # timeline coverage_trace
│   ├── pdf_view.py         # streamlit-pdf-viewer wrapper
│   ├── metrics_view.py     # metriche da per_case_reports
│   └── what_if.py          # form override patient_data
└── data/
    └── italian_names.json  # 200 nomi + 100 cognomi
```

I servizi sono raggiunti via `RULE_ENGINE_URL` / `ORCHESTRATOR_URL` (default
`http://localhost:8000` e `:8001`).
