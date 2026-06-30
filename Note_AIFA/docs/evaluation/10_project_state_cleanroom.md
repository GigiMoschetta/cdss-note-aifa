# 10 — Project State: Clean-Room Verification Report

**Session:** 14 (2026-02-28)
**Procedure:** Full end-to-end clean-room verification (Steps 0-10)
**Verdict:** **PASS** — all gates green, `make verify-cleanroom` exits 0

---

## A. Environment Snapshot

| Item | Value |
|------|-------|
| CWD | `/home/gigimoschetta/Desktop/Tesi Triennale/Note_AIFA/` |
| OS | Linux 6.17.0-14-generic |
| Python | 3.12.3 |
| venv | `aifa_rule_engine/.venv/` |
| pytest | 9.0.2 |
| LLM | Ollama llama3.1:8b @ http://localhost:11434 (GPU: RTX 3060 12GB) |
| ChromaDB | `rag_pipeline/chroma_db/` (rebuilt from scratch) |
| Embedding model | `paraphrase-multilingual-mpnet-base-v2` |
| Rule Engine version | v3.3.0 |
| Rules | 39 rules across 4 Note (97, 01, 13, 66) |

### Source PDFs (7 files)

| PDF | Note |
|-----|------|
| `nota-97.pdf` | Nota 97 (anticoagulanti orali) |
| `nota-97-all-2.pdf` | Nota 97 allegato 2 |
| `nota-97-all-3.pdf` | Nota 97 allegato 3 (perioperatorio, out-of-scope) |
| `Nota_01.pdf` | Nota 01 (IPP) |
| `nota-13.pdf` | Nota 13 (ipolipemizzanti) |
| `Nota_66.pdf` | Nota 66 (FANS) |
| `Nota_66 .pdf` | Nota 66 (seconda sezione, con spazio nel nome) |

### Makefile Targets

| Target | Purpose |
|--------|---------|
| `make ingest-local` | Clean-room PDF ingestion → ChromaDB |
| `make test-local` | Unit tests (both `aifa_rule_engine/tests/` and `rag_pipeline/orchestrator/tests/`) |
| `make eval-rule-engine` | Gold standard regression (100 cases) |
| `make up-local` / `make down-local` | Start/stop services (rule engine :8000, orchestrator :8001) |
| `make eval-pipeline` | Pipeline evaluation with LLM (100 cases) |
| `make eval-retrieval` | Retrieval metrics (Recall@k, MRR) |
| `make verify-cleanroom` | End-to-end: wipe + ingest + test + eval-all |

---

## B. Commands Executed and Results

### Step 1: Clean-room wipe

```
rm -rf rag_pipeline/chroma_db/ evaluation/results/
```

Verified: both directories deleted.

### Step 2: Rebuild ChromaDB index

```
make ingest-local
# → aifa_rule_engine/.venv/bin/python rag_pipeline/ingest.py --reset
```

**Result:** 7 PDFs → 97 chunks, 4 collections (`nota_97`, `nota_01`, `nota_13`, `nota_66`).

Metadata verification:
- `page` and `page_end` fields stored as `int` (not str)
- Filename normalization handles `Nota_66 .pdf` (with space)

### Step 3: Unit tests

```
make test-local
# → pytest aifa_rule_engine/tests/ rag_pipeline/orchestrator/tests/ -v
```

**Result: 382/382 PASS (2.43s)**

Test breakdown:
| File | Tests |
|------|-------|
| `test_derived_vars.py` | 29 |
| `test_expression_eval.py` | 28 |
| `test_nota_01.py` | 10 |
| `test_nota_13.py` | 27 |
| `test_nota_66.py` | 16 |
| `test_nota_97.py` | 22 |
| `test_startup_validation.py` | 8 |
| `test_three_valued.py` | 54 |
| `test_properties.py` | 6 |
| `test_drug_normalizer.py` | 90 |
| `test_evidence_utils.py` | 14 |
| `test_validators.py` | 33 |
| `test_justification.py` | 22 |
| `test_retriever_anchor.py` | 23 |
| **Total** | **382** |

### Step 4: Rule engine evaluation (gold standard)

```
make eval-rule-engine
```

**Result: 100/100 PASS (100.0%), Macro F1 = 1.0000**

| Nota | Cases | Result |
|------|-------|--------|
| Nota 97 | 34 | 34/34 PASS |
| Nota 01 | 18 | 18/18 PASS |
| Nota 13 | 22 | 22/22 PASS |
| Nota 66 | 26 | 26/26 PASS |

Per-class metrics:
| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| RIMBORSABILE | 1.0000 | 1.0000 | 1.0000 | 48 |
| NON_RIMBORSABILE | 1.0000 | 1.0000 | 1.0000 | 41 |
| NON_DETERMINABILE | 1.0000 | 1.0000 | 1.0000 | 10 |
| ROUTED | 1.0000 | 1.0000 | 1.0000 | 1 |

### Step 5: Start services + readiness check

```
make up-local
curl -sf http://localhost:8001/health  # → {"status": "ok", "llm": "ollama/llama3.1:8b"}
```

Both services responsive: Rule Engine :8000, Orchestrator :8001.

### Step 6: Pipeline evaluation

```
make eval-pipeline  # includes --save-explanations --timeout 200
```

**Result: 100/100 PASS (100.0%)**

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Decision consistency rate | 1.0000 | =1.0 | PASS |
| Citation coverage rate | 1.0000 | >=0.90 | PASS |
| Hallucination rate | 0.0000 | <=0.10 | PASS |
| Section completeness rate | 1.0000 | =1.0 | PASS |
| Justification snippet coverage rate | 1.0000 | =1.0 | PASS |

Token usage:
| Stat | Prompt | Completion | Total |
|------|--------|------------|-------|
| Mean | 7635 | 504 | 8139 |
| Median | 7089 | 523 | 7653 |
| Max | 10558 | 716 | 11104 |

Saved explanations: 100 files in `evaluation/results/pipeline_explanations/`.

### Step 7: Sample output inspection

Three explanations sampled (one per decision type):

**N97-001 (RIMBORSABILE):**
- 5 sections present (DECISIONE, MOTIVAZIONE, RACCOMANDAZIONI, DATI MANCANTI, FONTI)
- Deterministic FONTI: 9 entries (nota-97.pdf p.1/2/3/4, nota-97-all-2.pdf p.1/2/3/6/7)
- No PROVA NORMATIVA box (RIMBORSABILE = no blocking rule)

**N66-008 (NON_RIMBORSABILE):**
- 5 sections present
- Deterministic FONTI: 5 entries (Nota_66.pdf p.2, Nota_66 .pdf p.1/2/3/4)
- PROVA NORMATIVA evidence box present:
  ```
  --- PROVA NORMATIVA ---
  Regola: N66_SCOPE_001
  snippet_id: 6f4dc43a00
  Fonte: Nota_66.pdf, p. 2
  Testo: "flurbiprofene; furprofene; ibuprofene; ..."
  --- FINE ---
  ```

**N13-014 (NON_RIMBORSABILE):**
- 5 sections present
- Deterministic FONTI: 6 entries (nota-13.pdf p.1/3/5/6/10/11)
- PROVA NORMATIVA evidence box present:
  ```
  --- PROVA NORMATIVA ---
  Regola: N13_INCL_001
  snippet_id: 9b1983efc7
  Fonte: nota-13.pdf, p. 1
  Testo: "Ipolipemizzanti ..."
  --- FINE ---
  ```

**N97-008 (NON_DETERMINABILE):**
- 5 sections present
- DATI MANCANTI lists missing fields: paziente_sesso, difficolta_monitoraggio_inr, etc.
- Deterministic FONTI: 8 entries

### Step 8: Stop services

```
make down-local
# → Orchestrator stopped, Rule Engine stopped
```

### Step 9: Retrieval evaluation

```
make eval-retrieval
```

**Result:**

| Metric | Value |
|--------|-------|
| Recall@3 | 0.8525 |
| Recall@5 | 0.8900 |
| Recall@10 | 0.9100 |
| Precision@3 | 0.2633 |
| Precision@5 | 0.2420 |
| MRR | 0.9100 |
| Stage A (anchor-guided) | 56.5% |
| Stage B (semantic+reranked) | 43.5% |

### Step 10: `make verify-cleanroom`

```
make verify-cleanroom
```

**Result: Exit code 0 — all gates passed.**

The single-command target executes Steps 1-9 in sequence:
1. Wipe ChromaDB + results
2. Re-ingest PDFs → 97 chunks
3. Unit tests → 382/382 PASS
4. Rule engine eval → 100/100 PASS (Macro F1=1.0)
5. Start services + readiness check (curl /health loop)
6. Pipeline eval → 100/100 PASS (all 5 metrics at target)
7. Stop services
8. Retrieval eval → Recall@5=0.89, MRR=0.91
9. "Clean-room verification COMPLETE (all gates passed)."

---

## C. Results Summary

| Gate | Command | Result |
|------|---------|--------|
| Ingestion | `make ingest-local` | 7 PDFs → 97 chunks, 4 collections |
| Unit tests | `make test-local` | **382/382 PASS** (2.43s) |
| Gold standard | `make eval-rule-engine` | **100/100 PASS** (Macro F1=1.0000) |
| Pipeline | `make eval-pipeline` | **100/100 PASS** (decision_consistency=100%, citation=100%, halluc=0%, justification=100%) |
| Retrieval | `make eval-retrieval` | Recall@5=0.89, MRR=0.91 |
| Clean-room gate | `make verify-cleanroom` | **Exit 0** |

---

## D. Evidence: Sampled Explanations

### D.1 — N97-001 (RIMBORSABILE, apixaban + FANV)

```
1. DECISIONE
   Il farmaco è: RIMBORSABILE

2. MOTIVAZIONE
   Il farmaco apixaban è stato valutato per la sua efficacia e sicurezza nella
   prevenzione del rischio trombo-embolico nei pazienti con fibrillazione atriale
   non valvolare (FANV). Il punteggio CHA2DS2-VASc è stato calcolato e risulta
   essere [4, 4], che supera la soglia di 2.

3. RACCOMANDAZIONI
   Nessuna raccomandazione aggiuntiva.

4. DATI MANCANTI
   Dati completi.

5. FONTI
- nota-97.pdf, p. 1
- nota-97.pdf, p. 4
- nota-97-all-2.pdf, p. 6
- nota-97.pdf, p. 3
- nota-97-all-2.pdf, p. 1
- nota-97-all-2.pdf, p. 7
- nota-97.pdf, p. 2
- nota-97-all-2.pdf, p. 2
- nota-97-all-2.pdf, p. 3
```

Verified: 5/5 sections present; deterministic FONTI with structured pdf+page references.

### D.2 — N66-008 (NON_RIMBORSABILE, ibuprofene + wrong indication)

```
1. DECISIONE
   Il farmaco è: NON_RIMBORSABILE

5. FONTI
- Nota_66.pdf, p. 2
- Nota_66 .pdf, p. 2
- Nota_66 .pdf, p. 1
- Nota_66 .pdf, p. 3
- Nota_66 .pdf, p. 4

--- PROVA NORMATIVA ---
Regola: N66_SCOPE_001
snippet_id: 6f4dc43a00
Fonte: Nota_66.pdf, p. 2
Testo: "flurbiprofene; furprofene; ibuprofene; indometacina; ketoprofene; ..."
--- FINE ---
```

Verified: deterministic FONTI + PROVA NORMATIVA evidence box with snippet_id.

### D.3 — N13-014 (NON_RIMBORSABILE, atorvastatina + no indication)

```
1. DECISIONE
   Il farmaco è: NON_RIMBORSABILE

5. FONTI
- nota-13.pdf, p. 1
- nota-13.pdf, p. 5
- nota-13.pdf, p. 3
- nota-13.pdf, p. 6
- nota-13.pdf, p. 11
- nota-13.pdf, p. 10

--- PROVA NORMATIVA ---
Regola: N13_INCL_001
snippet_id: 9b1983efc7
Fonte: nota-13.pdf, p. 1
Testo: "Ipolipemizzanti Fibrati Statine Altri ..."
--- FINE ---
```

Verified: deterministic FONTI + PROVA NORMATIVA evidence box with snippet_id.

---

## E. Verdict

**PASS** — The AIFA CDSS project is reproducible from a clean state. All verification gates pass:

1. **Ingestion reproducibility:** 7 PDFs → 97 chunks (identical to previous runs)
2. **Unit test coverage:** 382/382 tests across rule engine + orchestrator
3. **Gold standard accuracy:** 100/100 cases, Macro F1=1.0000 (all 4 decision classes)
4. **Pipeline quality:** 100/100 with all 5 metrics at target:
   - decision_consistency_rate = 1.0
   - citation_coverage_rate = 1.0
   - hallucination_rate = 0.0
   - section_completeness_rate = 1.0
   - justification_snippet_coverage_rate = 1.0
5. **Retrieval quality:** Recall@5=0.89, MRR=0.91
6. **Single-command gate:** `make verify-cleanroom` exits 0
7. **Explanation quality:** Deterministic FONTI post-compose + PROVA NORMATIVA evidence boxes with SHA-1 snippet_id verified in 3 sampled outputs

**The project is ready for thesis write-up (Phase C).**

---

*Report generated: 2026-02-28, Session 14*
