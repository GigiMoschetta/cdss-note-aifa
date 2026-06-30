# 02 — Project Intent and Target

**Evidence:** `Descrizione_progetto_tesi.txt`, `AIFA CDSS Full Project.txt`, `PROJECT_STATE_TRACKER.md`
**Last updated:** 2026-02-25 (Session 7)

---

## 1. Problem Statement

Italian physicians must manually interpret **Note AIFA** — dense regulatory documents from Italy's national pharmaceutical regulatory authority (AIFA) — to determine whether a drug is reimbursable by the National Health System (SSN). This is error-prone and legally sensitive. Each Nota specifies conditions (diagnoses, clinical variables, risk scores, drug-specific exclusions) that must all hold simultaneously for a prescription to qualify for SSN reimbursement.

**Source:** `Descrizione_progetto_tesi.txt` (L3-4) — *"il medico nell'interpretazione delle Note AIFA, recuperando automaticamente le parti rilevanti del testo normativo e applicando regole cliniche esplicite sul profilo del paziente, così da restituire una decisione motivata, verificabile e tracciabile"*

---

## 2. Proposed Solution: Neuro-Symbolic CDSS

A two-layer architecture:

### Layer 1 — Symbolic (Rule Engine)
- Deterministic eligibility decision using **Kleene Three-Valued Logic** (TRUE / FALSE / UNKNOWN)
- 38 formalized rules across 4 Note (97, 01, 13, 66) encoded in YAML
- Output: `RIMBORSABILE | NON_RIMBORSABILE | NON_DETERMINABILE`
- Decision is **authoritative** — the LLM never overrides it

**Source:** `Descrizione_progetto_tesi.txt` (L11-18) — *"Il motore a regole confronta tali dati con i criteri previsti dalla Nota e produce un esito deterministico"*

### Layer 2 — Neural (RAG Pipeline)
- **Stage A:** Anchor-guided retrieval — exact (pdf_file, page) match from rule anchors → 100% precision
- **Stage B:** Semantic retrieval — top-k cosine + cross-encoder reranking (LlamaIndex `SentenceTransformerRerank`)
- **LLM:** Generates Italian-language explanation at temperature=0 — *explanation only, no re-determination*
- Validators: decision consistency, citation coverage, hallucination detection

**Source:** `Descrizione_progetto_tesi.txt` (L19) — *"Il ruolo del modello linguistico è limitato alla generazione di una spiegazione chiara e comprensibile, basata esclusivamente sull'esito deterministico"*

### Core Safety Invariant
The Rule Engine decision is injected into the LLM prompt as `[DECISIONE DETERMINISTICA — NON CONTRADDIRE]` *before* any normative context. Post-generation validators detect contradictions. This ensures LLM cannot influence the clinical/regulatory outcome.

**Source:** `PROJECT_STATE_TRACKER.md` (§3, L275)

---

## 3. Notes in Scope

| Nota | Topic | Rules | Status |
|------|-------|-------|--------|
| 97 | Anticoagulanti orali in FANV | 18 | Complete |
| 01 | Gastroprotettori (PPIs) | 4 | Complete |
| 13 | Ipolipemizzanti (statine) | 7 | Complete |
| 66 | FANS/NSAIDs (routed from N01) | 9 | Complete |

**Rationale for selection** (`Descrizione_progetto_tesi.txt` L31): Nota 97 (anticoagulants, high complexity), Nota 1 (gastroprotectors, simpler), Nota 13 (lipid-lowering, intermediate) — three notes with different structural complexity to validate generalizability.

**Note 66** was added as an implicit dependency of Nota 01 (routing for diclofenac+misoprostolo).

---

## 4. Output Contract

The system outputs for each case:
1. **Reimbursement decision** — `RIMBORSABILE | NON_RIMBORSABILE | NON_DETERMINABILE`
2. **Explicit motivation** — Italian-language explanation citing retrieved normative text
3. **Citations** — PDF filename + page + section for each supporting statement
4. **Missing data signals** — `missing_fields_coverage` (decisive) vs `missing_fields_guidance` (non-blocking)
5. **Audit trail** — `coverage_trace` + `audit_trail` with per-rule Kleene results and phase numbers

**Source:** `Descrizione_progetto_tesi.txt` (L21-29)

---

## 5. Acceptance Criteria (Definition of "Perfect")

| Criterion | Threshold | Current Status |
|-----------|-----------|----------------|
| Rule engine correctness (gold standard) | 37/37 (100%) | **37/37 ✅** |
| Rule engine Macro F1 | 1.000 | **1.0000 ✅** |
| Pipeline faithfulness | ≥100% | **100% ✅** |
| Pipeline citation coverage | ≥90% | **94.6% ✅** |
| Pipeline hallucination rate | ≤10% | **0% ✅** |
| Pipeline section completeness | 100% | **100% ✅** |
| Unit test pass | 173/173 | **173/173 ✅** |

**Source:** `PROJECT_STATE_TRACKER.md` (CHANGELOG Session 6, L32-44)

---

## 6. Evaluation Strategy

Three evaluation tracks (`Descrizione_progetto_tesi.txt` L33-43):

### Track 1 — Decision Correctness
- Gold standard: 37 manually labeled cases per note (positive, negative, exception, borderline, missing-data)
- Metrics: accuracy, precision, recall, F1 per class (RIMBORSABILE, NON_RIMBORSABILE, NON_DETERMINABILE, ROUTED)
- **Current result:** Macro F1 = 1.0000 on 37/37 cases

### Track 2 — Retrieval Quality
- Annotated relevant sections per case
- Metrics: Recall@k (k=3,5,10), Precision@k, MRR
- **Current results:** Recall@5=0.70, MRR=0.76, Recall@10=0.76

### Track 3 — Explanation Quality
- Faithfulness: every claim in explanation supported by retrieved text
- Section completeness: required structured sections present
- Decision consistency: explanation agrees with deterministic decision
- **Current results:** faithfulness=100%, hallucination=0%, sections=100%

---

## 7. Architectural Decisions (Rationale)

| Decision | Why |
|----------|-----|
| Kleene 3VL | Patient data is always incomplete; avoid forcing binary assumptions |
| Short-circuit + missing-field pruning | Report only decisive missing fields, not all missing fields |
| Interval arithmetic for CHA2DS2-VASc | Partial data can still determine eligibility definitively |
| Age block max=2 (not 3) | A2 (age≥75, w=2) and A (65≤age<75, w=1) are mutually exclusive |
| `rule_evaluated_as` field in BlockingRule | Preserves raw Kleene result for correct explanation generation |
| Dual missing-field channels | `missing_fields_coverage` ≠ `missing_fields_guidance` (safety-critical) |
| Invariant I-1: Dose-on-Denial | NON_RIMBORSABILE → suppress all DOSE flags (patient safety) |
| temperature=0 for LLM | Reproducible outputs for evaluation |
| Section detection in ingestion | Enables Stage A intra-page precision via `{pdf_file, page, section}` |

**Source:** `PROJECT_STATE_TRACKER.md` §8 (L560-580)

---

## 8. Implementation Scope vs Original Intent

| Component | Intended | Implemented | Delta |
|-----------|----------|-------------|-------|
| Rule Engine (all 4 Note) | ✓ | ✓ 38 rules, 173 tests | None |
| RAG Ingestion | ✓ | ✓ 7 PDFs, 97 chunks | None |
| Orchestrator (POST /explain) | ✓ | ✓ Full pipeline | None |
| Evaluation framework | ✓ | ✓ 3 tracks, 3 notebooks | None |
| Perioperative rules (Nota 97) | Mentioned | TODO (nota-97-all-3.pdf) | Intentionally deferred |
| Thesis write-up | Phase C | Not started | Next phase |

**Note on perioperative rules:** `rules/nota_97/rules.yaml` (L695-701) explicitly marks perioperative management rules as TODO with anchor `nota-97-all-3.pdf`. These were intentionally excluded from scope in the project plan.

---

*Checkpoint:* All engineering phases complete. Next: PDF ground truth extraction and implementation audit.
