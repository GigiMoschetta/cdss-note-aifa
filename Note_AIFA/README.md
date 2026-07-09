# AIFA CDSS — Sistema di Supporto Decisionale per Note AIFA
### Rule Engine deterministico + RAG/LLM (Llama 3.1 8B locale)

![tests](https://img.shields.io/badge/tests-1025%20passing-brightgreen)
![rule_engine_F1](https://img.shields.io/badge/rule_engine_F1-1.0-brightgreen)
![python](https://img.shields.io/badge/python-3.12-blue)
![scope](https://img.shields.io/badge/scope-Note%201%20%7C%2013%20%7C%2097%20%2B%2066-informational)

Implementazione neuro-simbolica per l'interpretazione delle **Note AIFA 1, 13, 66, 97**.

- **Rule Engine** (`aifa_rule_engine/`) — 44 regole YAML, three-valued Kleene logic, FastAPI service su porta 8000.
- **RAG Pipeline** (`rag_pipeline/`) — ChromaDB + sentence-transformers + Llama 3.1 8B via Ollama, FastAPI su porta 8001.
- **Evaluation** (`evaluation/`) — 122 gold standard cases, 3 track metriche.

## Setup rapido (Docker — raccomandato)

### Prerequisiti host

| Componente                          | Versione           | Verifica                                    |
|-------------------------------------|--------------------|---------------------------------------------|
| Docker Engine                       | ≥ 24.0             | `docker --version`                          |
| NVIDIA Container Toolkit            | qualsiasi recente  | `make gpu-check`                            |
| Ollama daemon (host)                | ≥ 0.2.0            | `ollama --version`                          |
| Modello Llama 3.1 8B in Ollama      | `llama3.1:8b`      | `ollama list \| grep llama3.1:8b`            |

### Procedura

```bash
# 1. Scaricare modello LLM nell'host (~4.7 GB)
ollama pull llama3.1:8b

# 2. Configurare ambiente
cp .env.example .env
# (.env è già configurato per Ollama; lasciare OPENAI_API_KEY vuoto)

# 3. Verifica prerequisiti
make setup

# 4. Build immagini Docker
make build

# 5. Ingest PDF nella vector DB (one-time, ~30s)
make ingest

# 6. Verifica integrità PDF (controlla SHA256 contro audit/pdf_checksums.json)
python3 tools/verify_pdf_integrity.py --strict

# 7. Avvia servizi
make up

# 8. Test API
curl http://localhost:8000/health
curl http://localhost:8001/health

# 9. Esegui valutazione completa
make eval-rule-engine    # ~1s, no LLM
make eval-pipeline       # ~10-30 min con Llama (richiede make up)
make eval-retrieval      # offline da pipeline_report.json

# 10. End-to-end clean room (riproducibilità completa)
make verify-cleanroom
```

## Setup locale (sviluppo, no Docker)

```bash
# 1. Crea venv + installa
make install-local

# 2. Ingest locale
make ingest-local

# 3. Test
make test-local

# 4. Avvia servizi locali
make up-local
```

## Architettura

```
                       PDF Note AIFA (Note_AIFA/*.pdf)
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
   Rule Engine (38+1 regole YAML)         RAG ingest (PyMuPDF + NLTK + sent-transformers)
   aifa_rule_engine/                      rag_pipeline/ingest.py
              │                                       │
              ▼                                       ▼
    POST /evaluate (port 8000)              ChromaDB persistente
    Three-valued Kleene logic               (rag_pipeline/chroma_db/)
    Pipeline 10-fasi fail-fast                       │
    Audit trail strutturato                          │
              │                                       │
              └───────────────┬───────────────────────┘
                              ▼
                   POST /explain (port 8001)
                   rag_pipeline/orchestrator/
                        ├─ Two-stage retrieval (anchor + semantic + cross-encoder rerank)
                        ├─ Hardened prompt (decisione FIRST, anti-allucinazione)
                        ├─ Llama 3.1 8B (Ollama, temp=0)
                        ├─ Deterministic FONTI post-compose
                        ├─ Evidence boxes "PROVA NORMATIVA" verbatim
                        └─ Validators (decision, citation, hallucination, justification)
                              │
                              ▼
                      CDSSResponse JSON
                      {decision, explanation, sources, validation flags}
```

## Note AIFA implementate

| Nota | Argomento                                 | Regole | PDF                                    |
|------|-------------------------------------------|--------|----------------------------------------|
| 01   | Gastroprotettori (PPI, misoprostolo)      | 4      | Nota_01.pdf                            |
| 13   | Ipolipemizzanti (statine, ezetimibe, ...) | 7      | nota-13.pdf                            |
| 66   | FANS (antinfiammatori non steroidei)      | 10     | Nota_66 .pdf                           |
| 97   | Anticoagulanti orali in FANV              | 18     | nota-97.pdf + 3 allegati               |

**Versioning PDF:** ogni `aifa_rule_engine/rules/nota_{N}/_catalog.yaml` riporta MD5/SHA256/URL/data download del PDF su cui sono state estratte le regole. `tools/verify_pdf_integrity.py` valida l'integrità.

## Documentazione tecnica

- **Operativo / difesa:** `RUNBOOK.md` — comando unico cleanroom + lista verifica pre-difesa + diagnostica fail-mode.
- **Limiti dichiarati:** `LIMITATIONS.md` — scope (Note 1, 13, 97 + 66 bonus), Allegato 3 N97 fuori scope, M3 NLI lower-bound, RAGAS subset stratificato, modello LLM Q4_K_M, dataset sintetico.
- **Audit completo del progetto:** `audit/REPORT_FINALE.md` (riassunto) + `audit/0X_*.md` (dettagli per fase: PDF→regole, implementazione, profili, LLM, metriche, riproducibilità).
- **Refactor v2:** `REFACTOR_V2_SUMMARY.md`.
- **Tesi LaTeX:** `tesi_latex/` — sorgenti del manoscritto.
- **Plan piano evolutivo:** `NOTE_AIFA_Improvement_Plan_v1_1_1.md`.

## Limitazioni note

Vedi `LIMITATIONS.md` per l'elenco completo. In sintesi: Allegato 3 N97 dichiarato `not_implemented_in_scope`, modello LLM quantizzato Q4_K_M, M3 NLI lower-bound conservativo, dataset gold sintetico (122 casi), RAGAS subset stratificato n=20, `requires_passed` dichiarativo (non enforced runtime), audit trail in-memory.

## Licenza & contatti

Progetto di tesi triennale, Università degli Studi di Trieste (UniTS).
Autore: **Francesco Zamar** (matricola SM3201464, sessione estiva 20/07/2026).
Relatore: Prof. Andrea De Lorenzo.
Licenza codice: MIT (vedi `aifa_rule_engine/pyproject.toml`).

## Come citare

Se utilizzi questo lavoro nella tua ricerca, citalo con:

```bibtex
@thesis{zamar2026aifa,
  title  = {Un Sistema di Supporto alla Decisione Clinica Neuro-Simbolico
            per la Verifica della Rimborsabilità delle Note AIFA},
  author = {Zamar, Francesco},
  school = {Università degli Studi di Trieste},
  type   = {Tesi di Laurea Triennale in Informatica},
  year   = {2026}
}
```
