#!/bin/bash
# full_cleanroom_v2.sh — Full v2 cleanroom evaluation from zero
# Wipes state, re-ingests PDFs, runs unit tests, evaluates pipeline,
# computes all 7 non-tautological metrics, generates summary.
#
# Usage:
#   bash tools/full_cleanroom_v2.sh                # standard cleanroom
#   bash tools/full_cleanroom_v2.sh --fix-yaml     # also auto-fix WEAK_SIM excerpts
#   bash tools/full_cleanroom_v2.sh --skip-nli     # skip M3 (saves ~10 min)
#
# Output:
#   - evaluation/results/OVERNIGHT_SUMMARY_v2.md (final report)
#   - /tmp/cleanroom_v2.log (live log with phase progress)
#
# Audit clarification V3-H5 (2026-05-06): the strict-fail gate (`--strict-audit`,
# i.e. abort the whole run on the first failed stage) is implemented ONLY in
# tools/run_full_overnight.sh and is intentionally absent here. The cleanroom
# pipeline is meant to be a best-effort verification that always reaches the
# summary phase even when individual metrics fail; the strict gate belongs to
# the production-grade overnight runner. Earlier audit V2 wording suggested
# the two scripts shared a STRICT_AUDIT mode — that claim is corrected here.

set -e
set -u
set -o pipefail

# ── Reproducibility seeds (audit fix 2026-05-12 BLK-07) ───────────────────────
# Stabilise Python hash randomization and CUBLAS workspace to make bootstrap
# CIs, RAGAS, QAEval and any set-iterating metric reproducible across runs.
export PYTHONHASHSEED="${PYTHONHASHSEED:-42}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="/tmp/cleanroom_v2.log"
LOCK="/tmp/aifa_cleanroom.lock"
cd "$ROOT"

# Audit V4 2026-05-12: require HuggingFace pinned revisions to resolve.
# Without this, an offline run silently falls back to unpinned models and
# the run is no longer a true cleanroom.
export AIFA_STRICT_CLEANROOM=1

# ── Mutual exclusion — prevent concurrent cleanroom runs ─────────────────────
# Two parallel cleanroom would race-wipe ChromaDB and corrupt artifacts.
# flock holds an exclusive lock; if another instance is running, this aborts.
exec 200>"$LOCK"
if ! flock -n 200; then
  echo "ERROR: Another cleanroom run holds $LOCK. Abort." >&2
  exit 2
fi

# ── Cleanup trap (audit fix 2026-05-06 NF-2): release the flock and tear ─────
# down dev services on EXIT/ERR/INT/TERM. Prevents the "uvicorn orfani" bug
# (memory: feedback_overnight_bug.md) where Ctrl+C left :8000/:8001 occupied
# and cached stale ChromaDB UUIDs into the next run.
_cleanup() {
  local rc=$?
  echo "[cleanup] Releasing $LOCK and stopping dev services (rc=$rc)" | tee -a "$LOG" >&2 || true
  flock -u 200 2>/dev/null || true
  make down-local >/dev/null 2>&1 || true
  return "$rc"
}
trap _cleanup EXIT ERR INT TERM

FIX_YAML=0
SKIP_NLI=0
for arg in "$@"; do
  case "$arg" in
    --fix-yaml) FIX_YAML=1 ;;
    --skip-nli) SKIP_NLI=1 ;;
  esac
done

START_TS=$(date +%s)
echo "==== Cleanroom v2 START $(date -u +%Y-%m-%dT%H:%M:%SZ) ====" | tee "$LOG"
echo "FIX_YAML=$FIX_YAML  SKIP_NLI=$SKIP_NLI" | tee -a "$LOG"

phase() {
  echo "" | tee -a "$LOG"
  echo "==== [$(date +%H:%M:%S)] Phase $1: $2 ====" | tee -a "$LOG"
}

# Activate venv
source aifa_rule_engine/.venv/bin/activate
export CHROMA_COLLECTION_SUFFIX="_v2"

# ── Phase 0 — Stop services + wipe stale ─────────────────────────────────────
phase 0 "Stop services + kill stale uvicorn"
make down-local >>"$LOG" 2>&1 || true
sleep 2
lsof -ti:8000 -ti:8001 2>/dev/null | xargs -r kill 2>/dev/null || true

# ── Phase 1 — Wipe state ──────────────────────────────────────────────────────
phase 1 "Wipe ChromaDB v2 + results"
# v1 collections preserved for rollback (only v2 dir contents removed)
python3 - <<'EOF' >>"$LOG" 2>&1
import chromadb
client = chromadb.PersistentClient(path="rag_pipeline/chroma_db")
existing = [c.name for c in client.list_collections() if c.name.endswith("_v2")]
for n in existing:
    client.delete_collection(n)
    print(f"deleted {n}")
EOF
rm -rf evaluation/results/pipeline_explanations
rm -rf evaluation/results/per_case_reports
rm -f evaluation/results/pipeline_report.json
rm -f evaluation/results/retrieval_report.json
rm -f evaluation/results/citation_*.json
rm -f evaluation/results/explanation_uniqueness.json
rm -f evaluation/results/logical_consistency.json
rm -f evaluation/results/readability_gulpease.json
rm -f evaluation/results/pdf_gold_decision_f1.json
rm -f evaluation/results/semantic_faithfulness_v2.json
rm -f evaluation/results/wilson_ci_rule_engine.json
rm -f evaluation/results/OVERNIGHT_SUMMARY_v2.md

# ── Phase 2 — Optional: auto-fix WEAK_SIM YAML excerpts ──────────────────────
if [ "$FIX_YAML" = "1" ]; then
  phase 2 "Auto-fix WEAK_SIM YAML excerpts"
  python3 tools/derive_gold_from_pdf.py >>"$LOG" 2>&1
  python3 tools/auto_fix_excerpts.py --apply >>"$LOG" 2>&1
fi

# ── Phase 3 — Derive PDF gold ─────────────────────────────────────────────────
phase 3 "Derive PDF gold from rules.yaml"
python3 tools/derive_gold_from_pdf.py 2>&1 | tee -a "$LOG" | grep -E "Total rules|FOUND|Wrote"

# ── Phase 4 — Re-ingest v2 ────────────────────────────────────────────────────
phase 4 "Re-ingest PDFs (v2 schema with char-offset + tables)"
python3 rag_pipeline/ingest_v2.py --reset 2>&1 | tee -a "$LOG" | grep -E "INFO.*chunks|Done"

# ── Phase 5 — Regenerate expected_outputs_v2 ─────────────────────────────────
phase 5 "Regenerate expected_outputs_v2 with PDF anchors"
python3 evaluation/scripts/regenerate_expected_outputs_v2.py 2>&1 | tee -a "$LOG" | grep -E "INFO.*cases|Done"

# ── Phase 6 — Unit tests ──────────────────────────────────────────────────────
# Tests use mocked collection names without suffix (e.g. "nota_97"). To avoid
# KeyError("nota_97") when env CHROMA_COLLECTION_SUFFIX="_v2" causes _get_collection
# to look up "nota_97_v2", we temporarily unset the var for unit tests.
phase 6 "Unit tests (rule engine + orchestrator)"
unset CHROMA_COLLECTION_SUFFIX
python3 -m pytest aifa_rule_engine/tests/ rag_pipeline/orchestrator/tests/ -q 2>&1 | tee -a "$LOG" | tail -3
# Re-enable v2 routing for the rest of the cleanroom (services + pipeline + metrics)
export CHROMA_COLLECTION_SUFFIX="_v2"

# ── Phase 7 — Rule engine eval ────────────────────────────────────────────────
phase 7 "Rule engine evaluation (122 cases)"
make eval-rule-engine 2>&1 | tee -a "$LOG" | tail -3

# ── Phase 8 — Start services ──────────────────────────────────────────────────
phase 8 "Start services with v2 collection"
make up-local 2>&1 | tee -a "$LOG" | tail -3
sleep 8
curl -sf http://localhost:8000/health > /dev/null || { echo "RULE ENGINE DOWN"; exit 1; }
curl -sf http://localhost:8001/health > /dev/null || { echo "ORCHESTRATOR DOWN"; exit 1; }
echo "Both services healthy" | tee -a "$LOG"

# ── Phase 9 — Pipeline eval (122 cases, ~25 min) ─────────────────────────────
phase 9 "Pipeline evaluation (122 cases — slowest phase)"
python3 -m evaluation.scripts.evaluate_pipeline \
  --verbose --timeout 200 --save-explanations \
  --json-report evaluation/results/pipeline_report.json 2>&1 | tee -a "$LOG" | grep -E "PIPELINE|pass rate|consistency|Hallucination|Token"

# ── Phase 10 — Retrieval eval ─────────────────────────────────────────────────
phase 10 "Retrieval evaluation (Track 2)"
make eval-retrieval 2>&1 | tee -a "$LOG" | tail -5

# ── Phase 11 — All 7 v2 metrics ──────────────────────────────────────────────
# Use `grep ... || true` so a missing match doesn't abort under `set -e -o pipefail`.
# The metric scripts always exit 0 on success — the grep is purely cosmetic.
phase 11 "Run all v2 metrics (M1..M7 + Wilson CI)"
python3 evaluation/metrics/citation_verbatim_accuracy.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     CVA" || true; }
python3 evaluation/metrics/citation_relevance.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     (CRS|CCS)" || true; }
python3 evaluation/metrics/explanation_uniqueness.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     EU" || true; }
python3 evaluation/metrics/logical_consistency.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     LC" || true; }
python3 evaluation/metrics/readability_gulpease.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     Gulpease" || true; }
python3 evaluation/metrics/pdf_gold_decision_f1.py 2>&1 | tee -a "$LOG" | { grep -E "INFO     M7" || true; }
python3 -m evaluation.metrics.bootstrap_wilson 2>&1 | tee -a "$LOG" | { grep -E "INFO     pass_rate" || true; }

if [ "$SKIP_NLI" = "0" ]; then
  phase 11.5 "M3 NLI italiano (mDeBERTa-XNLI on GPU fp16)"
  python3 evaluation/metrics/semantic_faithfulness_v2.py 2>&1 | tee -a "$LOG" | grep -E "INFO     SF|processed"
fi

# ── Phase 12 — Stop services + summary ────────────────────────────────────────
phase 12 "Stop services + generate summary"
make down-local 2>&1 | tee -a "$LOG" | tail -3
python3 evaluation/scripts/generate_overnight_summary_v2.py 2>&1 | tee -a "$LOG" | tail -3

# ── Phase 12.5 — Snapshot results (versioned, with `latest/` symlink) ───────
phase 12.5 "Snapshot results to runs/<timestamp>/ + update latest/ symlink"
RUN_TS=$(date -u +%Y%m%dT%H%M%SZ)
RUN_DIR="evaluation/results/runs/${RUN_TS}"
mkdir -p "$RUN_DIR"
# Copy every JSON + the markdown summary; explanations dir is large, copy only if exists
find evaluation/results/ -maxdepth 1 -type f \( -name '*.json' -o -name 'OVERNIGHT_SUMMARY_v2.md' \) -print0 \
  | xargs -0 -I{} cp -p "{}" "$RUN_DIR"/ 2>>"$LOG" || true
# Refresh `latest` symlink (relative for portability inside repo)
ln -sfn "${RUN_TS}" evaluation/results/runs/latest
echo "Snapshot: $RUN_DIR  (latest -> $RUN_TS)" | tee -a "$LOG"

# ── Phase 13 — LaTeX V2 appendix (Tier 4.1) ──────────────────────────────────
phase 13 "Update LaTeX manuscript with V2 numbers"
python3 tools/update_latex_v2_numbers.py --apply 2>&1 | tee -a "$LOG" | tail -5

# ── Phase 14 — Re-build LaTeX PDF (if pdflatex available) ────────────────────
phase 14 "Rebuild thesis PDF (if pdflatex installed)"
if command -v pdflatex >/dev/null 2>&1; then
  _orig_cwd="$(pwd)"
  if cd "$ROOT/../tesi_latex" 2>/dev/null; then
    pdflatex -interaction=nonstopmode tesi.tex >>"$LOG" 2>&1 || echo "pdflatex pass 1 had warnings" | tee -a "$LOG"
    pdflatex -interaction=nonstopmode tesi.tex >>"$LOG" 2>&1 || echo "pdflatex pass 2 had warnings" | tee -a "$LOG"
    cd "$_orig_cwd"
    echo "Thesis PDF rebuilt: $ROOT/../tesi_latex/tesi.pdf" | tee -a "$LOG"
  else
    echo "tesi_latex/ directory not found — skipping PDF rebuild" | tee -a "$LOG"
  fi
else
  echo "pdflatex not installed — skipping PDF rebuild" | tee -a "$LOG"
fi

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
ELAPSED_MIN=$((ELAPSED / 60))

echo "" | tee -a "$LOG"
echo "==== Cleanroom v2 DONE in ${ELAPSED_MIN} min ====" | tee -a "$LOG"
echo "Output: evaluation/results/OVERNIGHT_SUMMARY_v2.md" | tee -a "$LOG"
echo "Live log: $LOG" | tee -a "$LOG"

# Display final summary (use absolute path — robust to cwd changes from Phase 14)
cat "$ROOT/evaluation/results/OVERNIGHT_SUMMARY_v2.md" | head -50 | tee -a "$LOG"
