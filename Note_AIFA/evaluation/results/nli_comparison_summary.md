# NLI / Italian-similarity model comparison

## NLI (entailment vs contradiction over MOTIVAZIONE sentences)

| Modello | n | mean_entailment | median_entailment | mean_contradiction | n_high_contr |
|---|---|---|---|---|---|
| `mDeBERTa-v3-base-mnli-xnli` | 122 | 0.0799 | 0.0042 | 0.2522 | 100 |
| `mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | 122 | 0.2953 | 0.2869 | 0.3047 | 110 |
| `mDeBERTa-v3-base-mnli-xnli` | 122 | 0.0806 | 0.0042 | 0.2582 | 104 |

**Higher entailment = better.  Lower contradiction = better.**

## Italian semantic similarity (STSB cross-encoder)

| Modello | n | mean (norm [0,1]) | median | n_low_support (<0.5) |
|---|---|---|---|---|
| `cross-encoder-italian-bert-stsb` | 122 | 0.1063 | 0.1104 | 396 |

**M3-bis NOT a replacement for NLI** — it answers a similarity question, 
not an entailment question. Both signals are reported for triangulation.