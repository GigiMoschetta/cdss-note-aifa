# CDSS neuro-simbolico per la verifica della rimborsabilità delle Note AIFA

Sistema di supporto alla decisione clinica (CDSS) che verifica la rimborsabilità
dei farmaci soggetti a **Nota AIFA**, separando in modo netto **la decisione** dalla
**spiegazione**:

- la decisione di rimborsabilità è affidata interamente a un **rule engine
  deterministico e ispezionabile** (regole YAML, logica trivalente di Kleene);
- la spiegazione clinica è prodotta da un **Large Language Model** locale inserito
  in una pipeline **Retrieval-Augmented Generation (RAG)** sulle Note ufficiali AIFA,
  vincolato a citare i passaggi normativi recuperati.

La decisione è quindi corretta per costruzione e verificabile a prescindere dalla
qualità della generazione testuale; ogni affermazione della spiegazione è
riconducibile al testo della Nota.

Il sistema è sviluppato e valutato su quattro Note AIFA (01, 13, 66, 97) e su un
dataset *gold* di 122 casi clinici annotati manualmente.

## Struttura della repository

| Cartella | Contenuto |
|---|---|
| `Note_AIFA/aifa_rule_engine/` | Rule engine deterministico (regole YAML, logica di Kleene, API FastAPI) |
| `Note_AIFA/rag_pipeline/` | Ingestione PDF, retrieval ChromaDB + reranker, orchestratore, backend LLM |
| `Note_AIFA/evaluation/` | Dataset gold, metriche, baseline, report dei risultati |
| `Note_AIFA/demo/`, `Note_AIFA/webapp/` | Interfacce dimostrative (Streamlit e web app) |
| `Note_AIFA/docker/`, `docker-compose.yml`, `Makefile` | Deployment e automazione |
| `tesi/` | Elaborato finale: sorgenti LaTeX e PDF delle due versioni |

Per i dettagli tecnici, il setup e i comandi vedere
[`Note_AIFA/README.md`](Note_AIFA/README.md).

## Riproducibilità

L'intera valutazione è riproducibile end-to-end, dai PDF normativi ai numeri
finali. Le dipendenze sono fissate con hash in `Note_AIFA/requirements.lock`; lo
script di *cleanroom* cancella gli indici, reindicizza i PDF da zero, esegue la
suite di test e ricalcola tutte le metriche.

## L'elaborato

La cartella [`tesi/`](tesi/) contiene i PDF e i sorgenti LaTeX dell'elaborato in due
versioni con lo stesso contenuto:

- `Tesi_Zamar_intro_aggiornata.pdf` — introduzione rivista e correzioni applicate
  lungo tutto il testo;
- `Tesi_Zamar_feedback_integrato.pdf` — indice e corpo riorganizzati attorno alle
  domande di ricerca.

---

Prova finale di laurea — Corso di Laurea in Intelligenza Artificiale e Analisi dei
Dati, Università degli Studi di Trieste. Autore: **Francesco Zamar**.
