#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# OVERNIGHT EVALUATION ORCHESTRATOR — single LLM (Llama 3.1 8B)
#
# Runs the full from-scratch pipeline + every metric for thesis evaluation.
#
# Stages (with checkpoint/resume):
#   00 PDF integrity (sha256)
#   01 PDF→rule fidelity audit (HARD GATE: 0 BLOCCANTI required)
#   10 Wipe ChromaDB + results
#   11 Re-ingest PDFs
#   12 Unit tests (357+)
#   13 Rule engine eval (122 cases, must be 100%)
#   14 Services up (rule_engine + rag_pipeline)
#
#   20 Pipeline LLM with --save-explanations (~30 min)
#   21 Track 2 retrieval metrics
#
#   30 excerpt_match
#   31 faithfulness_verbatim
#   32 NLI faithfulness (mDeBERTa)
#   33 LLM output metrics bundle (claim_coverage, citation_set, decision_compliance,
#                                  rouge_paraphrase, sentence_support, decision_rationale_alignment)
#   34 RAGAS (italianized, gold_answer reference, ~12h)
#   35 QAEval (Malasi, Llama judge, ~3h)
#
#   40 Composite scores (Decision/Evidence/Utility/Quality/ALES)
#   41 Bootstrap CI 95%
#
#   50 Services down
#   51 Per-case verifiable reports (122 .md + .json)
#   52 Thesis tables/figures + summary
#
# Usage:
#   bash tools/run_full_overnight.sh                # full run, ~14-16h
#   bash tools/run_full_overnight.sh --resume       # skip stages already completed
#   bash tools/run_full_overnight.sh --skip-ragas   # skip the slow RAGAS stage (~3h instead of ~14h)
#   bash tools/run_full_overnight.sh --skip-qaeval  # skip QAEval too
#
# Logs:   evaluation/results/.checkpoints/<stage>.log
# Locks:  evaluation/results/.checkpoints/<stage>.done
# Final:  evaluation/results/OVERNIGHT_SUMMARY.md
# ─────────────────────────────────────────────────────────────────────────────
set -e
set -u
set -o pipefail

# ── Reproducibility seeds (audit fix 2026-05-12 BLK-07) ───────────────────────
# Stabilise Python hash randomization (set order, dict iteration tie-breaks in
# CPython 3.7+) and CUBLAS workspace allocation (deterministic conv kernels on
# CUDA 10.2+). Without these, RAGAS/QAEval bootstrap samples and any metric
# that iterates over a `set()` vary across runs, making ALES non-reproducible.
export PYTHONHASHSEED="${PYTHONHASHSEED:-42}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

# Working directory: Note_AIFA
cd "$(dirname "$0")/.." || { echo "[FATAL] cd to Note_AIFA failed" >&2; exit 1; }

# Cleanup trap (audit fix 2026-05-06 NF-2): on EXIT/ERR/INT/TERM, stop the
# dev services that this script may have started via `make up-local`. Prevents
# orphan uvicorn processes from holding :8000/:8001 across runs.
_cleanup_overnight() {
  local rc=$?
  echo "[cleanup] Stopping dev services (overnight rc=$rc)" >&2 || true
  make down-local >/dev/null 2>&1 || true
  return "$rc"
}
trap _cleanup_overnight EXIT ERR INT TERM

VENV=aifa_rule_engine/.venv/bin/python
RESULTS=evaluation/results
CHKPT=$RESULTS/.checkpoints
PIPELINE_REPORT=$RESULTS/pipeline_report.json
EXPL_DIR=$RESULTS/pipeline_explanations
RULE_REPORT=$RESULTS/rule_engine_report.json
RETR_REPORT=$RESULTS/retrieval_report.json

mkdir -p "$CHKPT"

# Parse flags
RESUME=0
SKIP_RAGAS=0
SKIP_QAEVAL=0
STRICT_AUDIT=0
for arg in "$@"; do
    case $arg in
        --resume)        RESUME=1 ;;
        --skip-ragas)    SKIP_RAGAS=1 ;;
        --skip-qaeval)   SKIP_QAEVAL=1 ;;
        --strict-audit)  STRICT_AUDIT=1 ;;
        *) echo "Unknown flag: $arg" >&2; exit 2 ;;
    esac
done

START_TS=$(date -Iseconds)
GLOBAL_LOG=$CHKPT/_global.log
echo "==========================================" | tee -a "$GLOBAL_LOG"
echo "OVERNIGHT EVALUATION — Llama 3.1 8B Q4_K_M" | tee -a "$GLOBAL_LOG"
echo "Started: $START_TS"                          | tee -a "$GLOBAL_LOG"
echo "Resume:  $RESUME  Skip-RAGAS: $SKIP_RAGAS  Skip-QAEval: $SKIP_QAEVAL" | tee -a "$GLOBAL_LOG"
echo "==========================================" | tee -a "$GLOBAL_LOG"

# ─────────────────────────────────────────────────────────────────────────────
run_stage() {
    local stage_id="$1"; shift
    local stage_log="$CHKPT/$stage_id.log"
    local done_marker="$CHKPT/$stage_id.done"

    if [[ -f "$done_marker" ]] && [[ "$RESUME" == "1" ]]; then
        echo "[SKIP]  $stage_id (already done @ $(cat $done_marker))" | tee -a "$GLOBAL_LOG"
        return 0
    fi

    local start=$(date +%s)
    echo ""
    echo "[START] $stage_id @ $(date -Iseconds)" | tee -a "$GLOBAL_LOG"
    echo "        cmd: $*"                       | tee -a "$GLOBAL_LOG"
    # Audit fix 2026-05-07 (V3-W6 follow-up): wrap in if/else so set -e does
    # NOT abort the function on a non-zero rc. The plain `"$@" > log; rc=$?`
    # pattern under `set -e` was making the script exit before the rc check
    # below could read the value, defeating STRICT_AUDIT=0 (soft) mode.
    local rc=0
    if "$@" > "$stage_log" 2>&1; then
        rc=0
    else
        rc=$?
    fi
    local end=$(date +%s)
    local elapsed=$((end - start))

    if [[ $rc -eq 0 ]]; then
        date -Iseconds > "$done_marker"
        echo "[DONE]  $stage_id (${elapsed}s)" | tee -a "$GLOBAL_LOG"
    else
        echo "[FAIL]  $stage_id (rc=$rc, ${elapsed}s) — see $stage_log" | tee -a "$GLOBAL_LOG"
        echo "        last 5 lines:" | tee -a "$GLOBAL_LOG"
        tail -5 "$stage_log" | sed 's/^/        /' | tee -a "$GLOBAL_LOG"
        if [[ "${STRICT_AUDIT:-0}" == "1" ]]; then exit 1; fi
    fi
    # Audit fix 2026-05-07 (V3-W6 follow-up): in soft mode (STRICT_AUDIT=0,
    # default) we must always return 0 — the script runs under `set -e` so a
    # non-zero return here would abort the whole overnight at the first stage
    # that has a partial-failure, defeating the purpose of soft mode. The
    # truth source for completion is the .done marker in $CHKPT.
    return 0
}

# ────── STAGE 0: Foundation + maniacal PDF audit ──────
run_stage "00_pdf_integrity" $VENV tools/verify_pdf_integrity.py --strict
run_stage "01_pdf_audit"     $VENV tools/audit_rules_vs_pdf.py

# Hard gate: PDF audit must have 0 BLOCCANTI
AUDIT_JSON="../audit/PDF_AUDIT_REPORT.json"
if [[ ! -f "$AUDIT_JSON" ]]; then
    echo "[ABORT] PDF audit report missing at $AUDIT_JSON — stage 01_pdf_audit must run first" | tee -a "$GLOBAL_LOG"
    exit 1
fi
BLOCK_COUNT=$($VENV -c "import json; d=json.load(open('$AUDIT_JSON')); print(d['summary'].get('FABRICATED', 0))" 2>/dev/null || echo "READ_ERROR")
if [[ "$BLOCK_COUNT" == "READ_ERROR" ]]; then
    echo "[ABORT] Could not parse PDF audit JSON" | tee -a "$GLOBAL_LOG"
    exit 1
fi
if [[ "$BLOCK_COUNT" -gt 0 ]]; then
    echo "[ABORT] PDF audit has $BLOCK_COUNT FABRICATED rules. Fix before proceeding." | tee -a "$GLOBAL_LOG"
    exit 1
fi
echo "[GATE]  PDF audit: 0 BLOCCANTI ✓ (verified $AUDIT_JSON)" | tee -a "$GLOBAL_LOG"

# Stage 09: kill stale uvicorn services on ports 8000/8001 BEFORE wiping chroma_db.
# Without this, an orchestrator started before the overnight (and thus not tracked
# by .pids/) keeps cached ChromaDB collection UUIDs that get invalidated by the
# wipe → every subsequent /explain call hits "Collection [UUID] does not exist"
# and returns 0 retrieved chunks, silently corrupting all downstream metrics.
run_stage "09_kill_stale" bash -c '
    for port in 8000 8001; do
        pids=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "Stale process(es) on port $port: $pids — killing"
            kill $pids 2>/dev/null || true
            sleep 2
            kill -9 $pids 2>/dev/null || true
        fi
    done
    rm -f "$1/14_services_up.done"
    true
' _ "$CHKPT"

# ────── STAGE 1: Wipe + ingest + tests + rule engine ──────
run_stage "10_wipe" bash -c "rm -rf rag_pipeline/chroma_db $RESULTS/pipeline_*.json $RESULTS/retrieval_report.json $RESULTS/rule_engine_report.json $RESULTS/excerpt_match.json $RESULTS/faithfulness_verbatim.json $RESULTS/nli_faithfulness.json $RESULTS/llm_output_metrics.json $RESULTS/qaeval.json $RESULTS/ragas_report.json $RESULTS/composite_scores.json $RESULTS/bootstrap_ci_*.json $RESULTS/pipeline_explanations $RESULTS/per_case_reports || true"
# Audit fix 2026-05-07: ingest-v2 (NOT ingest-local). The retriever reads
# CHROMA_COLLECTION_SUFFIX=_v2 from .env and looks up `nota_X_v2` collections;
# v1 ingest creates `nota_X` (no suffix) and the retriever silently returns
# 0 chunks for every query — the LLM then runs without RAG grounding.
run_stage "11_ingest"        make ingest-v2
run_stage "12_unit_tests"    $VENV -m pytest aifa_rule_engine/tests/ rag_pipeline/orchestrator/tests/ -q --tb=no
run_stage "13_rule_engine"   make eval-rule-engine
run_stage "14_services_up"   make up-local

# Wait for orchestrator
echo "Waiting for orchestrator readiness..." | tee -a "$GLOBAL_LOG"
ORCH_READY=0
for i in $(seq 1 60); do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "Orchestrator ready after ${i}s" | tee -a "$GLOBAL_LOG"
        ORCH_READY=1
        break
    fi
    sleep 1
done
if [[ "$ORCH_READY" != "1" ]]; then
    echo "[ABORT] Orchestrator did NOT become ready within 60s — refusing to run STAGE 2 against dead service" | tee -a "$GLOBAL_LOG"
    echo "        (continuing would corrupt all .done checkpoints with HTTP failures)" | tee -a "$GLOBAL_LOG"
    exit 1
fi

# ────── STAGE 2: Pipeline LLM + retrieval ──────
run_stage "20_pipeline_save" $VENV -m evaluation.scripts.evaluate_pipeline \
    --verbose --timeout 200 --save-explanations \
    --json-report $PIPELINE_REPORT
run_stage "21_retrieval"     $VENV -m evaluation.scripts.evaluate_retrieval \
    --json-report $RETR_REPORT

# ────── STAGE 3: Deterministic + RAGAS metrics ──────
run_stage "30_excerpt_match" $VENV -m evaluation.metrics.excerpt_match \
    --pipeline-report $PIPELINE_REPORT \
    --explanations-dir $EXPL_DIR \
    --gold-dir evaluation/gold_standard \
    --output $RESULTS/excerpt_match.json

run_stage "31_faithfulness_verbatim" $VENV -m evaluation.metrics.faithfulness_verbatim \
    --pipeline-report $PIPELINE_REPORT \
    --explanations-dir $EXPL_DIR \
    --output $RESULTS/faithfulness_verbatim.json

# Audit fix 2026-05-07: NLI on CUDA. mDeBERTa-v3-base (~280M params, ~600MB VRAM)
# fits easily on RTX 3060 (~8GB free when Ollama unloaded between LLM-judge waves).
# CPU mode took ~75 min for 30/122 cases (extrapolated 4-5h total) due to longer
# explanations post-RAG fix + sliding window for >512 token sequences. CUDA brings
# stage to ~10 min. Ollama is unloaded during stage 32 anyway (idle TTL elapsed).
run_stage "32_nli_faithfulness" $VENV -m evaluation.metrics.nli_faithfulness \
    --pipeline-report $PIPELINE_REPORT \
    --explanations-dir $EXPL_DIR \
    --output $RESULTS/nli_faithfulness.json \
    --device cuda

run_stage "33_llm_output_metrics" $VENV -m evaluation.metrics.llm_output_metrics \
    --pipeline-report $PIPELINE_REPORT \
    --explanations-dir $EXPL_DIR \
    --gold-dir evaluation/gold_standard \
    --output $RESULTS/llm_output_metrics.json

if [[ "$SKIP_RAGAS" == "0" ]]; then
    # HGH-02 (audit 2026-05-12): hard cap RAGAS.
    # 2026-05-13 run: post-RAG-fix pipeline produces longer explanations + the
    # Llama 3.1 8B judge hits the RagasOutputParser more often, pushing each
    # job from historical 55s to ~120s (Ollama single-instance, GPU 2% utilized).
    # Cap bumped 14h→30h (50400→108000) — observed rate 110-130s/it × 732 jobs
    # projects 22-26h; 30h gives ~4-8h safety margin against retry-storm spikes.
    run_stage "34_ragas" timeout --signal=TERM 108000 \
        $VENV -m evaluation.metrics.ragas_eval \
            --pipeline-report $PIPELINE_REPORT \
            --explanations-dir $EXPL_DIR \
            --gold-dir evaluation/gold_standard \
            --output $RESULTS/ragas_report.json
fi

if [[ "$SKIP_QAEVAL" == "0" ]]; then
    run_stage "35_qaeval" $VENV -m evaluation.metrics.qaeval \
        --pipeline-report $PIPELINE_REPORT \
        --explanations-dir $EXPL_DIR \
        --gold-dir evaluation/gold_standard \
        --output $RESULTS/qaeval.json \
        --resume
fi

# ────── STAGE 4: Composites + bootstrap CI ──────
run_stage "40_composite_scores" $VENV -m evaluation.metrics.composite_scores \
    --output $RESULTS/composite_scores.json

run_stage "41_bootstrap_rule" $VENV -m evaluation.metrics.bootstrap_ci \
    --input $RULE_REPORT \
    --output $RESULTS/bootstrap_ci_rule_engine.json

# ────── STAGE 5: Services down + per-case reports + thesis artifacts ──────
run_stage "50_services_down" make down-local
run_stage "51_baselines"     make eval-baselines
run_stage "52_robustness"    make eval-robustness

run_stage "60_per_case_reports" make eval-per-case-reports

# Generate the OVERNIGHT_SUMMARY.md
run_stage "61_summary" bash -c "$VENV -m evaluation.scripts.generate_overnight_summary > $RESULTS/OVERNIGHT_SUMMARY.md 2>&1 || echo '(summary generator missing — todo)' > $RESULTS/OVERNIGHT_SUMMARY.md"

END_TS=$(date -Iseconds)
echo ""                                                                 | tee -a "$GLOBAL_LOG"
echo "==========================================" | tee -a "$GLOBAL_LOG"
echo "OVERNIGHT EVALUATION COMPLETE"             | tee -a "$GLOBAL_LOG"
echo "Started:  $START_TS"                       | tee -a "$GLOBAL_LOG"
echo "Finished: $END_TS"                         | tee -a "$GLOBAL_LOG"
echo "Summary:  $RESULTS/OVERNIGHT_SUMMARY.md"   | tee -a "$GLOBAL_LOG"
echo "Per-case: $RESULTS/per_case_reports/"      | tee -a "$GLOBAL_LOG"
echo "==========================================" | tee -a "$GLOBAL_LOG"
