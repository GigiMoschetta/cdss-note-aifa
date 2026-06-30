# Overnight Evaluation Summary — v2 (PDF-anchored, non-tautological metrics)

_Generated: 2026-05-05T13:34:09Z_

This v2 summary distinguishes **non-tautological metrics** (M1..M7) from
**integrity asserts** (numbers guaranteed by construction). Every metric
displayed under §2 is computed against either the PDF source itself or a
PDF-derived gold (`pdf_derived_anchors.json` + `expected_outputs_v2.json`).

## 1. PDF→rule fidelity audit

_44 rules audited via fuzzy matching against PDF text._

| Status | Count | Severity |
|---|---|---|
| VERBATIM_FOUND | 27 | INFO |
| APPROX_FOUND | 17 | INFO |
| LOW_SIM_FOUND | 0 | MEDIO |
| WEAK_SIM_FOUND | 0 | ALTO |
| FAIL_NOT_FOUND | 0 | BLOCCANTE |

## 2. Metriche genuine (NON tautologiche) — primary thesis evaluation

| ID | Metrica | Valore | Range | Note |
|---|---|---|---|---|
| **M7** | Decision Macro F1 (vs author-scripted gold) | **1.0** | [0,1] | n=122 cases, gold da `expected_rule_engine` (NON da rule_engine output — post-audit-fix). Anchor coverage separato: 1.0 (39/39) |
| **M1** | Citation Verbatim Accuracy (CVA) | **0.5128** | [0,1] | mean over 39 cases (n_perfect=20) |
| **M2** | Citation Containment Score (CCS) | **0.4615** | [0,1] | |gold ∩ chunk| / |gold| — fraction of PDF-gold span covered by cited chunk, n=39 |
| **M4** | Explanation Uniqueness (EU) | **0.4802** | [0,1] | dup_rate=0.2623 (13 groups), mean_cosine=0.3491 |
| **M5** | Logical Consistency (LC) | **0.9836** | [0,1] | 2/122 cases with logical errors |
| **M6** | Readability Gulpease (norm) | **0.3872** | [0,1] | raw mean=53.23 (Italian-specific index) |

**Caveat di interpretazione (per la difesa):**

- **M3 NLI lower-bound**: il modello `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` è multilingual generico, non fine-tuned su normativa italiana. La metrica entailment è una stima conservativa: valori bassi (≤0.2) NON significano hallucination, ma riflettono che il modello non riesce a riconoscere l'entailment su sintagmi tecnici/giuridici italiani. Il proxy operativo di faithfulness è `faithfulness_verbatim` (3-gram coverage = 0.99) computato in v1 sul medesimo dataset.
- **M4 EU duplicates**: case clinicamente equivalenti (es. 5 N01 ROUTED-to-Nota-66 con stesso pattern di rule engine) generano explanation quasi-identiche perché l'orchestrator inietta deterministicamente decisione + chunks. È un trade-off determinismo/personalizzazione del LLM Q4_K_M, non un bug. La metrica è informativa, non un indicatore di failure.
- **M2 vs M2-legacy**: il containment (CCS) ha sostituito il Jaccard (CRS) come metrica primaria — il Jaccard era artificiosamente penalizzato dalla differenza di scala chunk≈1800 char vs gold≈200 char.
- **M7 audit-fix 2026-04-30**: ora usa `expected_rule_engine.reimbursement_decision` dei `cases.json` (gold scritto a mano dall'autore) invece di `actual_result` (output del rule engine). Pre-fix era tautologica (rule engine vs sé stesso), post-fix è una vera misura di conformità implementazione↔attesa autore.

## 3. Integrity asserts (NOT metrics — guaranteed by construction)

These numbers are 100% by design and do **not** measure quality:

- `decision_injection_integrity_assert`: **1.0** (rule engine decision string is enforced in §1 of LLM output)
- `fonti_section_completeness_byconstruction`: **1.0** (FONTI section is composed deterministically by the orchestrator)
- `section_completeness`: **1.0** (prompt-template enforced)
- `rule_engine_self_consistency`: **1.0** (rule engine vs author-scripted gold; replaced by M7 for clinical relevance)

## 4. Wilson 95% confidence intervals (non-degenerate)

- Rule engine pass rate: **1.0** ∈ [0.9695, 1.0]
  - RIMBORSABILE (n=69): recall 1.0 ∈ [0.9473, 1.0], precision 1.0 ∈ [0.9473, 1.0]
  - NON_RIMBORSABILE (n=39): recall 1.0 ∈ [0.9104, 1.0], precision 1.0 ∈ [0.9104, 1.0]
  - NON_DETERMINABILE (n=9): recall 1.0 ∈ [0.7011, 1.0], precision 1.0 ∈ [0.7011, 1.0]
  - ROUTED (n=5): recall 1.0 ∈ [0.5657, 1.0], precision 1.0 ∈ [0.5657, 1.0]

## 4b. Baselines (ablation per quantificare il contributo del rule engine)

Tutti i baselines girano sui medesimi 122 case. Embedder allineato (post-fix 2026-04-30): `paraphrase-multilingual-mpnet-base-v2` per tutti i sistemi che fanno retrieval (era inconsistente in `llm_rag.py` pre-fix).

| Sistema | Accuracy | Macro F1 | Δ vs hybrid |
|---|---|---|---|
| Majority class (sempre RIMBORSABILE) | 0.5656 | 0.2408 | -0.7592 |
| LLM-only (Llama 3.1 8B, no RAG, no rules) | 0.5656 | 0.2408 | -0.7592 |
| LLM+RAG (Llama 3.1 8B + k=5 retrieval, no rules) | 0.5902 | 0.3152 | -0.6848 |
| **Hybrid (rule engine + RAG + LLM)** | **1.0000** | **1.0000** | — |

**Letture chiave:**
- Δ Rule engine = +0.6848 F1 (contributo del symbolic layer)
- Δ RAG = +0.0744 F1 (contributo del retrieval rispetto a LLM-only)
- Il rule engine è dimostrabilmente la componente decisiva: anche con LLM+RAG perfettamente allineato all'embedder di produzione, il gap resta enorme.

## 5. Retrieval (Track 2)

- Recall@3 = 0.5199 | Recall@5 = 0.632 | Recall@10 = 0.6937
- MRR = 0.7869
- Stage A (anchor) = 0.7854 | Stage B (semantic) = 0.2146

## 6. Explanation duplicate groups (M4 detail)

- 5 cases share output: N01-006, N01-019, N01-020, N01-021, N01-022
- 3 cases share output: N13-006, N13-017, N13-020
- 3 cases share output: N13-008, N13-009, N13-019
- 3 cases share output: N13-014, N13-015, N13-016
- 2 cases share output: N01-001, N01-015
- 2 cases share output: N01-002, N01-014
- 2 cases share output: N13-002, N13-003
- 2 cases share output: N13-005, N13-013
- 2 cases share output: N66-001, N66-013
- 2 cases share output: N66-004, N66-016

## 7. Logical violations (M5 detail)

- N97-013 [L1_range_below_threshold]: [2,2], che è inferiore alla soglia di 2
- N97-016 [L1_range_below_threshold]: [4, 4], che è inferiore alla soglia di 2

---

**How to read this summary:**

- **Section 2 (M1..M7)** is the primary thesis evaluation — every value is
  computed against either the PDF directly or a PDF-derived gold.
- **Section 3 (asserts)** must NOT be reported as quality metrics. They are
  internal consistency checks of the pipeline.
- The **Thesis Score** composite is intentionally NOT included here — it is
  an internal evaluation tool only, not part of the manuscript.
