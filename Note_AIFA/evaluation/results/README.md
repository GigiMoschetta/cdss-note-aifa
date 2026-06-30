# evaluation/results/ — Guida ai file di risultato

Questa directory contiene gli output canonici delle metriche di valutazione. **Aggiornata 2026-05-12.**

## Canonico (cleanroom 2026-05-08)

I numeri di **abstract.tex** e **cap5_valutazione_risultati.tex** della tesi vengono da questi file. Sono il riferimento ufficiale (la macro LaTeX `\cleanroomrun` punta a `cleanroom~2026-05-08`).

### Decisione + intervalli di confidenza (rule engine)

| File | Contenuto | Valore canonico |
|---|---|---|
| `pdf_gold_decision_f1.json` | Macro F1 rule engine vs gold PDF-grounded | F1 = 1.0000 (n=122) |
| `bootstrap_ci_rule_engine.json` | Wilson 95% CI sull'accuratezza | [0.9695, 1.0] |
| `rule_engine_report.json` | Per-case pass/fail + confusion matrix 4×4 | 122/122 pass |
| `wilson_ci_rule_engine.json` | Wilson score interval per proporzione | n=122 |

### Retrieval

| File | Contenuto |
|---|---|
| `retrieval_report.json` | Recall@k, Precision@k, MRR, stage coverage |
| `pipeline_report.json` | Output completo della pipeline LLM+RAG (per-case, 122 casi) |

### Citazioni e fedeltà (Track 3)

| File | Metrica |
|---|---|
| `citation_relevance.json` | M2 — Citation Relevance Score |
| `citation_verbatim_accuracy.json` | M1 — Citation Verbatim Accuracy |
| `faithfulness_verbatim.json` | Fedeltà verbatim chunk → output LLM |
| `excerpt_match.json` | Excerpt match strict |
| `excerpt_match_loose.json` | Excerpt match con soglia rilassata |
| `nli_faithfulness.json` | M3 — NLI italiano (mDeBERTa) |

### Composite + ALES

| File | Contenuto |
|---|---|
| `composite_scores.json` | ALES + 4 componenti canonici (Decision, Evidence, ContextualUtility, AnswerQuality) post-cleanroom 2026-05-08 |
| `OVERNIGHT_SUMMARY.md` | Riepilogo human-readable del cleanroom 2026-05-08 |
| `OVERNIGHT_SUMMARY_v2.md` | Versione v2 del summary (cleanroom precedente, 2026-05-05) |

### Robustezza

| File | Metrica |
|---|---|
| `robustness_idempotency.json` | Stessi input → stessi output (100%) |
| `robustness_boundary.json` | Perturbazioni ±soglia |
| `boundary_report.json` + `.md` | Dettaglio per boundary |

### Baseline (ablazione)

| File | Sistema confrontato |
|---|---|
| `baseline_llm_only.json` | Solo Llama 3.1 8B (no rule engine, no RAG) |
| `baseline_llm_rag.json` | Llama 3.1 8B + RAG semplice (no rule engine) |
| `baseline_majority_class.json` | Predittore banale (classe maggioritaria) |

### Altri

| File | Contenuto |
|---|---|
| `bleu_chrf.json` | Metriche traduzione (sanity check) |
| `qaeval.json` | QA-based eval (Malasi, Llama judge) |
| `ragas_report.json` | RAGAS framework |
| `logical_consistency.json` | M5 — Logical Consistency |
| `explanation_uniqueness.json` | M4 — Explanation Uniqueness |
| `readability_gulpease.json` | M6 — Gulpease index (italiano) |
| `llm_output_metrics.json` | Bundle metrico aggregato output LLM |
| `non_determinable_analysis.json` | Analisi casi `NON_DETERMINABILE` |
| `e2e_smoke_test_2026-05-07.json` | Smoke test end-to-end |
| `ales_sensitivity.json` | ALES sensitivity analysis |
| `nli_comparison_summary.json` + `.md` | Confronto modelli NLI |
| `boundary_report.md` | Riepilogo human-readable boundary |

## File storici (suffisso `_pre_fix_DATE` o `_pre_F0.1_DATE`)

Sono snapshot pre-fix conservati per audit trail. **Non sono il canonico** per la tesi.

| File | Significato |
|---|---|
| `composite_scores_pre_F0.1_2026-05-06.json` | Composite scores prima del fix F0.1 (decircularization) |
| `excerpt_match_pre_fix_2026-04-30.json` | Excerpt match prima del fix excerpt verbatim |

## Sotto-cartelle

| Directory | Contenuto |
|---|---|
| `baseline_v3.4/` | Risultati storici della baseline 3.4 (snapshot intermedio) |
| `runs/` | Run datate (es. `20260505T133409Z/`) per audit trail |
| `per_case_reports/` | 122 report `.md` + `.json` per caso del cleanroom 2026-05-08 |
| `pipeline_explanations/` | Spiegazioni LLM per caso (testo) |

## Effetto dei fix 2026-05-12 sui numeri

I fix verificati nel commit `fcd59e6` cambiano il comportamento di alcuni script di valutazione (vedi `STATE.md` §4 a livello root). Specificamente:

- `evaluate_rule_engine.py`: ora usa `==` invece di `issubset` su blocking_rule_ids → rule_engine_report.json futuro potrebbe avere F1 ≤ 1.0.
- `evaluate_retrieval.py`: ROUTED esclusi dall'aggregato → retrieval_report.json futuro potrebbe avere Recall/MRR diversi dal canonico 0.9068/1.0.
- `PYTHONHASHSEED=42`: bootstrap futuri sono deterministici **con questo specifico seed** → CI puntuali diversi dai canonici.

I file in questa cartella **rispecchiano il cleanroom 2026-05-08 pre-fix**: sono il riferimento ufficiale citato in tesi. Un eventuale ri-run produrrebbe valori aggiornati ma all'interno della stessa classe di magnitudine.
