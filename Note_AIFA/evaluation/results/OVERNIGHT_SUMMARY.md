# Overnight Evaluation Summary

_Generated: 2026-05-15T15:46:54_

## 1. Maniacal PDF→rule fidelity audit

_44 rules audited._

| Status | Count | Severity |
|---|---|---|
| VERBATIM_FOUND | 33 | INFO |
| APPROX_FOUND | 8 | INFO |
| PARAPHRASE_DOCUMENTED | 2 | MEDIO |
| WRONG_PAGE | 1 | ALTO |
| FABRICATED | 0 | BLOCCANTE |

**✅ 0 BLOCCANTI** — pipeline procede con regole verificate.

## 2. Track 1 — Rule Engine

- Total cases: **122**
- Pass rate: **1.0000**
- Macro F1: **1.0000**

| Classe | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| RIMBORSABILE | 1.0000 | 1.0000 | 1.0000 | 69 |
| NON_RIMBORSABILE | 1.0000 | 1.0000 | 1.0000 | 39 |
| NON_DETERMINABILE | 1.0000 | 1.0000 | 1.0000 | 9 |
| ROUTED | 1.0000 | 1.0000 | 1.0000 | 5 |

## 3. Track 2 — Retrieval

- Recall@3 = **0.6347** Recall@5 = **0.7467** Recall@10 = **0.9068**
- Precision@3 = **0.9891** Precision@5 = **0.9705**
- MRR = **1.0000**
- Stage A (anchor) = 78.54% Stage B (semantic) = 21.46%
- Total cases: 122

## 4. Track 3 — Pipeline LLM

- Total cases: **122**
- Overall pass rate: **1.0000**
- Decision consistency: **1.0000**
- Citation coverage: **1.0000**
- Hallucination rate: **0.0000**
- Section completeness: **1.0000**
- Mean total tokens/case: 8506 (median 9033, max 10916)

## 5. LLM-Output deterministic metrics

| Metric | Mean | Median | n |
|---|---|---|---|
| claim_coverage_score | 0.8525 | 1.0000 | 122 |
| citation_precision | 0.9978 | 1.0000 | 122 |
| citation_recall | 1.0000 | 1.0000 | 122 |
| citation_f1 | 0.9988 | 1.0000 | 122 |
| gold_citation_recall | 0.9918 | 1.0000 | 122 |
| decision_compliance_score | 1.0000 | 1.0000 | 122 |
| rouge_l_f1 | 0.0571 | 0.0530 | 122 |
| sentence_support_rate_strict | 0.3704 | 0.3333 | 122 |
| sentence_support_rate_loose | 0.8847 | 1.0000 | 122 |
| sentence_support_mean_max_sim | 0.6566 | 0.6631 | 122 |
| decision_rationale_alignment | 0.4000 | 0.0000 | 65 |

_Nota: `decision_rationale_alignment` è definito solo sui casi con `blocking_rules` non vuoto (65/122); i restanti 57 casi sono RIMBORSABILE_standard senza regole bloccanti per definizione._

## 6. NLI Faithfulness (mDeBERTa, deterministic)

- Mean entailment rate: **0.1325**
- Mean contradiction rate: **0.4391**
- Cases evaluated: 122

## 7. Faithfulness Verbatim (3-gram, deterministic)

- Mean verbatim quote rate: **1.0000**
- Mean 3-gram coverage: **0.9934**
- Cases evaluated: 39

## 8. Excerpt Match (gold PDF excerpt → LLM output)

- (soglia stretta 0.8) excerpt_match_rate_llm = **0.0574** · retrieval = **0.1803**
- gold_anchor_recall@3 / @5 / @10 = **0.7787** / **0.7951** / **0.9426**
- (soglia lasca 0.5) excerpt_match_rate_llm = **0.1721** · retrieval = **0.3361**

## 8b. BLEU / chrF — MOTIVAZIONE vs source (deterministic)

_n_cases: 122 (skipped 0)._

| Metric | Mean | Median | std | n |
|---|---|---|---|---|
| bleu_vs_chunks | 0.0000 | 0.0000 | 0.0000 | 122 |
| chrf_vs_chunks | 3.1807 | 2.8938 | 1.4062 | 122 |
| chrfpp_vs_chunks | 3.0149 | 2.7849 | 1.3497 | 122 |
| bleu_vs_excerpt | 2.5586 | 0.8145 | 4.4773 | 122 |
| chrf_vs_excerpt | 23.1887 | 18.7522 | 12.9858 | 122 |
| chrfpp_vs_excerpt | 20.6737 | 15.9665 | 12.7395 | 122 |

## 9. RAGAS Metrics (LLM judge: Llama 3.1 8B, italianized prompts)

_n_cases: 122, judge: llama3.1:8b, wall-time: 81174s_

| Metric | Mean | Median | n |
|---|---|---|---|
| faithfulness | 0.6137 | 0.5714 | 51 |
| answer_relevancy | 0.6274 | 0.6557 | 113 |
| context_precision | 0.5716 | 0.5657 | 73 |
| context_recall | 0.8375 | 1.0000 | 67 |
| answer_similarity | 0.7374 | 0.7384 | 122 |
| answer_correctness | 0.4651 | 0.4483 | 120 |

## 10. QAEval (Malasi-style F1 on micro-questions)

- Mean Recall: **0.3461**
- Mean Precision: **0.1519**
- Mean F1: **0.1715**
- Median F1: **0.1667**
- Cases evaluated: 121

## 11. Composite Scores (Malasi-inspired)

_Weights: α(Decision)=0.4, β(Evidence)=0.3, γ(Utility)=0.2, δ(Quality)=0.1_

| Composite | Mean | Median | Trimmed Mean | Std | n |
|---|---|---|---|---|---|
| **DecisionScore** | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 122 |
| **EvidenceSupport** | 0.4075 | 0.4905 | 0.4050 | 0.3079 | 122 |
| **ContextualUtility** | 0.6442 | 0.6068 | 0.6424 | 0.1616 | 81 |
| **AnswerQuality** | 0.4683 | 0.4656 | 0.4705 | 0.2363 | 122 |
| **ALES** | 0.6988 | 0.7135 | 0.6978 | 0.1176 | 122 |

## 12. Robustness + Baselines

- Idempotency: **100.00%** (20/20×3 runs)
- Boundary perturbation: **100.00%** (9/9)

**Tabella ablation baseline:**

| Baseline | Accuracy | Macro F1 | Note |
|---|---|---|---|
| Majority class (sempre RIMBORSABILE) | 0.5656 | 0.2408 | trivial — baseline rate |
| LLM-only (llama3.1:8b, no RAG, no rules) | 0.5656 | 0.2408 | degenera a majority class |
| LLM+RAG (llama3.1:8b, k=5, no rules) | 0.5902 | 0.3152 | retrieval ablation |
| **Hybrid (full system)** | **1.0000** | **1.0000** | rule engine deterministico + RAG + LLM |

**Δ ablation (Macro F1):**
- Δ LLM+RAG vs LLM-only = **+0.0744** (contributo del retrieval)
- Δ Hybrid vs LLM+RAG = **+0.6848** (contributo del rule engine)
- Δ Hybrid vs LLM-only = **+0.7592** (RAG + rule engine combinati)

## 13. Per-case verifiable reports

- Generated: **123** markdown + **122** JSON files
- Index: `evaluation/results/per_case_reports/INDEX.md`

---

## How to read this summary

- **Track 1 (Rule Engine)** is the safety-critical layer — must be 100% pass.
- **Track 3 + LLM-Output metrics** evaluate explanation quality on multiple dimensions.
- **NLI faithfulness** is the deterministic counterpart to RAGAS faithfulness — if both are high, evidence is trustworthy.
- **ALES** is the composite score for thesis-grade comparison; see `composite_scores.json` for per-case breakdown.
- For verifying a single case, open `evaluation/results/per_case_reports/N{NN}/{case_id}.md` — it shows input, gold, engine output, retrieved chunks (with verbatim text), LLM explanation, and all per-case metric scores side-by-side.
