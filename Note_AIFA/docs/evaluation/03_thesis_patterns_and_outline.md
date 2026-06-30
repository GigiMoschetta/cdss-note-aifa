# 03 — Thesis Patterns and Outline

**Session:** 7 (2026-02-25)
**Source:** Analysis of 3 reference thesis PDFs (all pages read in full by agent af8f427060d3f6355)

---

## 1. Reference Theses Analyzed

| # | File | Author | Level | Institution | Year | Topic |
|---|------|--------|-------|-------------|------|-------|
| T1 | `Tesi_Rag_Malasi.pdf` | Denis Malasi | Laurea Magistrale | UniTS, Ingegneria e Architettura | 2024/2025 | RAG chunking strategies for enterprise (ChromaDB, DeepEval, Pareto front) |
| T2 | `Moro_Tommaso_thesis.pdf` | Tommaso Moro | Laurea Triennale | UniTS, MIGE, AI & Data Analytics | 2024-2025 | Influence of chunking on RAG (custom RDSG/NDCG metric, 12 strategies) |
| T3 | `Tesi_Retrival_Augmented_Generation_for_C_unit_tests.pdf` | (anonymous) | Master's / final-year | European inst. (EN thesis) | 2024/2025 | RAG for C# unit test generation (AST-based chunking, Qdrant, multi-level eval) |

---

## 2. Common Chapter Structure (All Three Theses)

All three follow the same macro-sequence:

```
Abstract / Introduction
  → Background / Theory (RAG, LLMs, embeddings)
  → Related Work or Motivation
  → System Design + Implementation
  → Evaluation Framework Design (its own chapter — treated as a contribution)
  → Results and Discussion
  → Conclusions and Future Work
  → Appendices (data, code, screenshots)
```

### Key structural observation
The **Evaluation Framework Design** is always its own full chapter, **separate from the Results chapter**. The metric design is treated as a methodological contribution, not boilerplate.

---

## 3. Per-Thesis Chapter Breakdown

### T1 — Malasi (Laurea Magistrale, ~103 pp)

| # | Title | Pages |
|---|-------|-------|
| — | Abstract | p. I |
| — | Introduction | p. V–IX (~5 pp) |
| 1 | RAG Concepts and Foundations | ~13 pp |
| 2 | Practical Implementation | ~7 pp |
| 3 | Document Chunking: Segmentation Methods | ~10 pp |
| 4 | Automated Evaluation of RAG Outputs | ~24 pp |
| 5 | Results of the Automated Evaluation | ~22 pp |
| 6 | Human Evaluation of RAG: BPMN Quiz Study | ~10 pp |
| 7 | Conclusions and Future Work | ~3 pp |
| A | Appendix A: UI Screenshots | ~3 pp |
| B | Appendix B: Algorithm Implementations | ~5 pp |

**Evaluation metrics:** Six DeepEval library metrics (AnswerRelevancy, QAEval, ContextualRelevancy, ContextualPrecision, Faithfulness, FaithfulnessStrict) grouped into three composite scores. Multi-objective comparison via epsilon-dominance Pareto front (ε=0.05). Human validation: 12 participants, 83.3% LLM–human agreement rate.

**Central result anchor:** Tables 5.5–5.8 (global chunking strategy comparison across four documents).

---

### T2 — Moro (Laurea Triennale, ~48 pp)

| # | Title | Pages |
|---|-------|-------|
| — | Abstract | ~3 pp |
| 1 | What is RAG and why it's not dead | ~8 pp |
| 2 | Goal and methodology | ~12 pp |
| 3 | Code Implementation | ~12 pp |
| 4 | Experimental Evaluation | ~11 pp |
| — | Bibliography | ~2 pp |

**Evaluation metrics:** Custom RDSG/NDCG metric (human-annotated):
- `RDSG_k = Σ [w'(c_i) × s(c_i)] / log₂(i+1)`
- `w'(c) = w(c) × √Density(c)` (relevance weight × density discount)
- Normalized to [0,1] via NDCG = RDSG / IdealRDSG
- Statistical significance: Wilcoxon Signed-Rank Test

**Central result anchor:** Fig 13 (12 strategies × 6 columns: Mean NDCG, Median, Trimmed Mean, Std Dev, Ranking Points, Wins).

---

### T3 — C# Unit Tests (Master's, ~76 pp + appendices)

| # | Title | Pages |
|---|-------|-------|
| 1 | Background | ~13 pp |
| 2 | Related Work | ~3 pp |
| 3 | RAG for Code Synthesis | ~3 pp |
| 4 | RAG Implementation | ~16 pp |
| 5 | Evaluation Set Synthesis | ~4 pp |
| 6 | RAG Evaluation | ~5 pp |
| 7 | Results and Discussion | ~17 pp |
| A–C | Appendices (personas, embedding comparison, errors) | ~13 pp |

**Evaluation metrics:** Non-LLM retrieval metrics (Context Precision@K, Context Recall) to avoid circularity; three-level generation metrics (compilation errors → pass/fail → coverage delta). RAGAS was rejected due to LLM hallucination artifacts in query generation.

**Central result anchor:** Figs 7.1–7.13 (box-and-whiskers: Precision@K and Recall by repository/query type/language/persona).

---

## 4. Evaluation Methodology Comparison

| Aspect | Malasi (T1) | Moro (T2) | C# Thesis (T3) |
|--------|-------------|-----------|----------------|
| Retrieval metric | Composite (ContextualRelevancy + ContextualPrecision) | Custom RDSG/NDCG (human-annotated) | Context Precision@K, Context Recall (non-LLM) |
| Answer quality | Composite (AnswerRelevancy + QAEval + Faithfulness) | N/A (retrieval focus) | Level 1–3 (compilation, pass/fail, coverage) |
| Multi-objective | Pareto front (ε=0.05) | Ranking points + wins | Three separate levels (not aggregated) |
| Human validation | 12 participants, 83.3% agreement | Human annotation as primary signal | 6 personas drive query diversity |
| Statistical test | None | Wilcoxon Signed-Rank Test | None formal |
| LLM-as-judge | Yes (GPT-4o-mini) | Explicitly avoided ("black box") | Partially (RAGAS rejected) |

**Pattern:** All three acknowledge the LLM-as-judge tension and justify their choice explicitly. The evaluation section establishes credibility — not boilerplate.

---

## 5. Contribution Narrative Structure (Common Arc)

All three follow this argumentative arc:

1. **Gap statement:** "Existing approaches suffer from X (knowledge cutoff / LLM opacity / no code context)."
2. **Design choice:** "We address X by Y (chunking variation / custom metric / AST parsing)."
3. **Empirical validation:** "We ran experiments over N configurations."
4. **Key quantitative result:** One central table or figure anchors all claims.
5. **Limitation acknowledgment:** Explicitly scoped — NOT minimized.
6. **Future work:** 1–2 pages of extensions.

**Master's distinction:** T1 adds a second validation layer (human study), expected at Magistrale level for real-world applicability claims.

---

## 6. Writing Style Conventions

| Convention | Evidence |
|------------|---------|
| Passive voice for methods | "Experiments were conducted..." |
| Active voice for claims | "The results show that..." |
| Italian formality markers | Dedica, ringraziamenti, frontespizio (T1, T2) |
| Citation density | 20–40 total references; dense in background, sparse in results |
| Every figure referenced in text | No orphan figures — all referenced before appearance |
| Hedged conclusions | "suggests," "tends to," "in the context of this study" |
| Negative results included | C# thesis: "cannot realistically increase productivity"; Moro: SemanticChunker underperforms |
| Background as tutorial | Ch1 assumes ML knowledge but not RAG — self-contained primer |
| Implementation chapters concrete | Code snippets, DB schemas, prompt templates, architecture diagrams |
| Results = narrative + table | Every quantitative result has a prose interpretation paragraph |

---

## 7. Recommended Chapter Structure for This Thesis

Based on the T1+T2 patterns (Italian CS thesis on RAG + deterministic rule engine for pharmaceutical eligibility):

```
Abstract (Italian + English)
Introduzione
  - Problema: le Note AIFA sono complesse e multi-condizionali
  - Contributo: motore a regole deterministico + RAG con decisioni tracciabili e citate

Cap. 1: Background
  1.1 Il sistema delle Note AIFA (contesto normativo)
  1.2 Large Language Models e i loro limiti (allucinazioni, knowledge cutoff)
  1.3 Retrieval-Augmented Generation (pipeline, embedding, vector store)
  1.4 Logica a tre valori di Kleene (motivazione per dati clinici incompleti)
  1.5 Sistemi esperti e motori a regole (confronto con approcci probabilistici)

Cap. 2: Lavori Correlati
  2.1 RAG per documenti normativi e legali
  2.2 Clinical Decision Support Systems (CDSS)
  2.3 Sistemi ibridi neuro-simbolici

Cap. 3: Progettazione del Sistema
  3.1 Architettura complessiva (due livelli: simbolico + neurale)
  3.2 Modello dei dati (paziente, farmaco, variabili cliniche)
  3.3 Rappresentazione delle regole (YAML, tipi di regola, ancoraggi normativi)
  3.4 Pipeline di ingestion dei PDF (chunking, sezioni, ancoraggi)

Cap. 4: Implementazione
  4.1 Motore a regole (valutazione Kleene, corti-circuiti, variabili derivate)
  4.2 Componente RAG (Stage A anchor-guided + Stage B semantic + reranking)
  4.3 Orchestratore e API (POST /evaluate, POST /explain)
  4.4 Meccanismo di audit trail e citazioni

Cap. 5: Framework di Valutazione
  5.1 Dataset gold standard (37 scenari: positivi, negativi, eccezioni, borderline, missing-data)
  5.2 Track 1 — Correttezza decisionale (accuracy, F1 per classe)
  5.3 Track 2 — Qualità del retrieval (Recall@k, Precision@k, MRR)
  5.4 Track 3 — Qualità della spiegazione (faithfulness, citation coverage, hallucination)
  5.5 Invarianti di sicurezza (dose-on-denial, routed=null, guidance not in trace)

Cap. 6: Risultati
  6.1 Correttezza del motore a regole (37/37, Macro F1=1.0000)
  6.2 Qualità del retrieval (Recall@5=0.70, MRR=0.76)
  6.3 Qualità della spiegazione (faithfulness=100%, hallucination=0%)
  6.4 Analisi dei casi falliti (N97-005/006, N13-007)
  6.5 Limiti e casi fuori scope (perioperatorio, regole generali)

Cap. 7: Conclusioni e Lavori Futuri
  7.1 Contributi principali
  7.2 Limitazioni
  7.3 Estensioni future (Nota 36, interfaccia clinica, modello LLM locale più grande)

Appendici
  A. Schema API (POST /evaluate, POST /explain)
  B. Esempi di scenari golden patient (YAML/JSON)
  C. Estratti del ground truth normativo
  D. Tabella completa delle regole (rule_id → PDF → implementazione → test)
```

**Key recommendation:** Make Cap. 5 (Evaluation Framework) its own full chapter — following all three reference patterns — and anchor the quantitative discussion around one central summary table (the equivalent of Moro's Fig 13 = the Track 1 classification report + Track 3 pipeline metrics table).

---

## 8. Target Page Count (Laurea Triennale Calibration)

Based on T2 (Moro, 48 pp) as the closest reference (same level, same institution, same supervisor):

| Chapter | Target pages |
|---------|-------------|
| Abstract + Introduzione | 3–4 |
| Cap. 1 Background | 8–10 |
| Cap. 2 Lavori Correlati | 4–5 |
| Cap. 3 Progettazione | 8–10 |
| Cap. 4 Implementazione | 10–12 |
| Cap. 5 Framework di Valutazione | 8–10 |
| Cap. 6 Risultati | 8–10 |
| Cap. 7 Conclusioni | 3–4 |
| Appendici | 4–6 |
| **Totale** | **~56–71 pp** |

---

*All three theses read in full (af8f427060d3f6355). Page counts from PDF pagination as rendered.*
