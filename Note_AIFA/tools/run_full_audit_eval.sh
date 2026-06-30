#!/usr/bin/env bash
set -euo pipefail
# Day 7 audit fix: end-to-end evaluation pipeline post-V3.4 fixes.
#
# Runs the full evaluation suite in sequence and produces a summary report.
# Invoked AFTER `make verify-cleanroom` (which itself runs ingest + tests + eval-rule + eval-pipeline + eval-retrieval).
#
# This script ADDITIONALLY runs the V3.4 audit-introduced metrics:
# - Bootstrap CI on rule_engine_report
# - Majority class baseline
# - LLM-only baseline (requires Ollama)
# - Faithfulness verbatim (requires saved explanations)
# - Idempotency test
# - Boundary perturbation test
# - n=50 LLM audit (requires saved explanations)
#
# Usage:
#   bash tools/run_full_audit_eval.sh

set -e
cd "$(dirname "$0")/.."  # cd to Note_AIFA/

PYTHON="./aifa_rule_engine/.venv/bin/python"
RESULTS="evaluation/results"

echo "=== V3.4 audit full evaluation ==="

echo "--- 1. PDF integrity check ---"
$PYTHON tools/verify_pdf_integrity.py --strict

echo ""
echo "--- 2. Unit tests ---"
$PYTHON -m pytest aifa_rule_engine/tests/ -q 2>&1 | tail -3

echo ""
echo "--- 3. Rule engine evaluation (gold standard, 122 cases) ---"
$PYTHON -m evaluation.scripts.evaluate_rule_engine \
    --json-report $RESULTS/rule_engine_report.json 2>&1 | tail -3

echo ""
echo "--- 4. Bootstrap CI 95% on rule engine ---"
$PYTHON -m evaluation.metrics.bootstrap_ci \
    --input $RESULTS/rule_engine_report.json \
    --output $RESULTS/rule_engine_ci.json 2>&1 | tail -5

echo ""
echo "--- 5. Majority class baseline ---"
$PYTHON -m evaluation.baselines.majority_class 2>&1 | tail -10

echo ""
echo "--- 6. LLM-only baseline (skipped if Ollama not up) ---"
if curl -s --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
    $PYTHON -m evaluation.baselines.llm_only 2>&1 | tail -10
else
    echo "(Ollama not reachable, skipped)"
fi

echo ""
echo "--- 7. Robustness: idempotency ---"
$PYTHON -m evaluation.robustness.idempotency 2>&1 | tail -5

echo ""
echo "--- 8. Robustness: boundary perturbation ---"
$PYTHON -m evaluation.robustness.boundary_perturbation 2>&1 | tail -5

echo ""
echo "--- 9. Faithfulness verbatim (uses audit/llm_outputs/ if exists) ---"
if [ -d "../audit/llm_outputs" ]; then
    $PYTHON -m evaluation.metrics.faithfulness_verbatim \
        --llm-outputs-dir ../audit/llm_outputs \
        --output $RESULTS/faithfulness_verbatim.json 2>&1 | tail -10
else
    echo "(audit/llm_outputs/ not found, skipped)"
fi

echo ""
echo "--- 10. n=50 LLM audit (uses pipeline_explanations/ if exists) ---"
if [ -d "$RESULTS/pipeline_explanations" ] && [ -f "$RESULTS/pipeline_report.json" ]; then
    $PYTHON -m evaluation.scripts.day5_llm_audit_n50 \
        --explanations-dir $RESULTS/pipeline_explanations \
        --pipeline-report $RESULTS/pipeline_report.json \
        --output ../audit/llm_quality_audit_n50.md 2>&1 | tail -10
else
    echo "(pipeline_explanations or pipeline_report not found, skipped)"
    echo "Hint: run 'make eval-pipeline' first with --save-explanations"
fi

echo ""
echo "=== V3.4 audit eval complete ==="
echo "Reports in: $RESULTS/"
echo "  - rule_engine_report.json + rule_engine_ci.json"
echo "  - baseline_majority_class.json + baseline_llm_only.json"
echo "  - robustness_idempotency.json + robustness_boundary.json"
echo "  - faithfulness_verbatim.json"
echo "Audit reports in: ../audit/"
echo "  - 09_post_fix_report.md"
echo "  - llm_quality_audit_n50.md (if pipeline_explanations exists)"
