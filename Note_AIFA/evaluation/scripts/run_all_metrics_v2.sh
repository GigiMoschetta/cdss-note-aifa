#!/bin/bash
# Run all v2 non-tautological metrics in sequence.
# Robust: continues on failure of any single metric, reports total time.
# Audit fix 2026-05-12 (HGH-05): venv activation is performed BEFORE `set +e`
# to ensure a missing/broken venv aborts the run instead of silently falling
# back to the system Python; only the metric loop runs in continue-on-error.
set -euo pipefail

cd "$(dirname "$0")/../.."
source aifa_rule_engine/.venv/bin/activate

# ── Reproducibility seeds (audit fix 2026-05-12 BLK-07) ───────────────────────
export PYTHONHASHSEED="${PYTHONHASHSEED:-42}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

set +e

START=$(date +%s)
FAILED=()

run_step() {
  local label="$1"
  echo ""
  echo "=== $label ==="
  shift
  if ! "$@"; then
    FAILED+=("$label")
  fi
}

run_step "M1: Citation Verbatim Accuracy" \
  python3 evaluation/metrics/citation_verbatim_accuracy.py

run_step "M2: Citation Relevance Score" \
  python3 evaluation/metrics/citation_relevance.py

run_step "M4: Explanation Uniqueness" \
  python3 evaluation/metrics/explanation_uniqueness.py

run_step "M5: Logical Consistency" \
  python3 evaluation/metrics/logical_consistency.py

run_step "M6: Readability Gulpease" \
  python3 evaluation/metrics/readability_gulpease.py

run_step "M7: PDF-gold Decision F1" \
  python3 evaluation/metrics/pdf_gold_decision_f1.py

run_step "Wilson 95% CI" \
  python3 -m evaluation.metrics.bootstrap_wilson

run_step "M3: Semantic Faithfulness (NLI italiano, GPU fp16)" \
  python3 evaluation/metrics/semantic_faithfulness_v2.py

run_step "Generate OVERNIGHT_SUMMARY_v2.md" \
  python3 evaluation/scripts/generate_overnight_summary_v2.py

END=$(date +%s)
ELAPSED=$((END - START))
echo ""
echo "============================================"
echo "Total time: ${ELAPSED}s"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All metrics succeeded."
else
  echo "Failed steps: ${FAILED[@]}"
fi
echo "Summary at: evaluation/results/OVERNIGHT_SUMMARY_v2.md"
