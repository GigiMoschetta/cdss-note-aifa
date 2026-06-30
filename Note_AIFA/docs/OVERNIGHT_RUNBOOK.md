# Overnight Evaluation — Runbook

How to launch the full thesis-grade evaluation tonight and what to verify
in the morning.

## Pre-flight checklist (do this NOW, before launching)

1. **Verify Ollama is running with llama3.1:8b**
   ```bash
   curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep llama3.1
   ```
   Expected: a record for `llama3.1:8b`.

2. **Verify GPU available** (optional but recommended)
   ```bash
   nvidia-smi | head -10
   ```

3. **Verify disk space** ≥ 10 GB free in
   `/home/gigimoschetta/Desktop/Tesi_update/`.

4. **Run the PDF audit gate ALONE first** (1 minute) to catch any blocker
   ```bash
   cd /home/gigimoschetta/Desktop/Tesi_update/Tesi\ Triennale/Note_AIFA
   make eval-pdf-audit
   ```
   Expected: `🟢 No blocking findings.`

## Launch

Open a terminal you can leave running unattended. Use `screen` or `tmux` so
that if you close the terminal the process keeps running.

```bash
cd "/home/gigimoschetta/Desktop/Tesi_update/Tesi Triennale/Note_AIFA"
screen -S overnight                     # detach later with Ctrl-A, D
make eval-full-overnight 2>&1 | tee /tmp/overnight.log
```

After launch you can press `Ctrl-A, D` to detach. Reattach later with
`screen -r overnight`.

Estimated wall time: **~14-16 hours** (PDF + ingest + rule engine + pipeline
LLM + all metrics + RAGAS on 116 cases).

If you only have ~4 hours and want to skip RAGAS/QAEval (the slow parts):

```bash
make eval-fast-overnight
```

## Resume after crash/interrupt

The orchestrator writes a `.done` checkpoint after every stage. To resume
from where it stopped:

```bash
make eval-resume
```

Stages already done are skipped. The script is idempotent — you can
restart it as many times as needed.

## Stage map (what runs in what order)

| Stage | Wall time | Stage purpose |
|---|---|---|
| 00 PDF integrity | <1 min | SHA256 check of 7 PDFs |
| 01 PDF→rule audit | <1 min | Maniacal verbatim audit, gate on BLOCCANTI |
| 10 Wipe | <1 min | Clean ChromaDB + previous results |
| 11 Ingest | ~5 min | Re-ingest 7 PDFs to ChromaDB |
| 12 Unit tests | <1 min | 942+ pytest cases must pass |
| 13 Rule engine eval | <1 min | 116 cases, must be 100% Macro F1 |
| 14 Services up | <1 min | Start rule_engine + rag_pipeline servers |
| 20 Pipeline LLM (saving explanations) | ~30 min | 116 cases × ~16s, all .txt saved |
| 21 Track 2 retrieval | <1 min | Recall@k, MRR offline from pipeline_report |
| 30 Excerpt match | <1 min | Gold PDF excerpt → LLM body verbatim |
| 31 Faithfulness verbatim | <1 min | 3-gram coverage of LLM quotes |
| 32 NLI Faithfulness | ~10 min | mDeBERTa per-sentence entailment |
| 33 LLM output metrics bundle | ~5 min | claim_coverage, citation P/R, ROUGE-L, sentence support |
| 34 RAGAS (italianized, 6 metrics × 116) | **~12 hours** | LLM judge with Llama 3.1 (the slow one) |
| 35 QAEval (Malasi-style F1) | ~2 hours | Llama judge, 6 calls/case |
| 40 Composite scores | <1 min | DecisionScore, Evidence, Utility, Quality, ALES |
| 41 Bootstrap CI | <1 min | 95% CI on rule engine metrics |
| 50-52 Services down + baselines + robustness | ~5 min | majority/LLM-only baselines + idempotency + boundary |
| 60 Per-case reports | ~1 min | 116 markdown + 116 JSON files |
| 61 Summary generation | <1 min | OVERNIGHT_SUMMARY.md |

## In the morning — checklist

1. Open the summary:
   ```bash
   less evaluation/results/OVERNIGHT_SUMMARY.md
   ```

2. Verify all green:
   ```bash
   ls evaluation/results/.checkpoints/*.done | wc -l
   ```
   Expected: ~25-28 stages done. If less, check `_global.log` for failures.

3. Spot-check a few per-case reports:
   ```bash
   open evaluation/results/per_case_reports/N97/N97-001.md
   open evaluation/results/per_case_reports/N66/N66-024.md  # known fail
   ```

4. Check anomalies in summary's "Anomalies" section if present.

5. Update the thesis with the new numbers (cap6_risultati.tex):
   - Track 1 Macro F1 + 95% CI
   - Track 2 Recall@5, MRR
   - Track 3 + LLM-output composite scores
   - RAGAS table
   - QAEval F1
   - Composite ALES distribution

## Known limitations to declare in cap 6 of tesi

1. **RAGAS uses Llama 3.1 8B as judge** — same family as the model under test.
   Mitigation: italianized prompts, also we report deterministic metrics
   (NLI faithfulness via mDeBERTa) for cross-validation.

2. **Single LLM tested in this run** (Llama 3.1 8B Q4_K_M). Multi-model
   comparison (LLaMAntino-3, Maestrale, Qwen2.5) is documented as future work
   pending hardware availability.

3. **QAEval and RAGAS are LLM-judge metrics** — not deterministic. We report
   their scores alongside the deterministic NLI/excerpt-match for triangulation.

4. **22 of 44 rule excerpts are documented paraphrases** (not verbatim from PDF):
   audit shows token containment ≥ 0.6 in target page, semantic equivalence
   verified via 116/116 gold standard pass. Rule behavior (the safety-critical
   property) is verified at the deterministic-rule-engine level.

## Files of interest after the run

| File | Purpose |
|---|---|
| `evaluation/results/OVERNIGHT_SUMMARY.md` | One-page summary of all metrics |
| `evaluation/results/composite_scores.json` | ALES + 4 composites per case |
| `evaluation/results/per_case_reports/INDEX.md` | Filterable table of all 116 cases |
| `evaluation/results/per_case_reports/N{NN}/{case_id}.md` | Single-case detailed report |
| `audit/PDF_AUDIT_REPORT.md` | Maniacal PDF→rule fidelity audit |
| `evaluation/results/.checkpoints/_global.log` | Stage-by-stage timing log |
