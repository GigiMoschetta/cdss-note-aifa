#!/bin/bash
# Restart orchestrator (loads patched cdss_orchestrator.py),
# re-run pipeline + M2 metric, print pre/post comparison.
# ETA: ~20-25 minutes.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [1/5] Stopping services..."
make down-local

echo
echo "==> [1b/5] Killing any orphan uvicorn..."
lsof -ti:8000 -ti:8001 2>/dev/null | xargs -r kill 2>/dev/null || true
sleep 2

echo
echo "==> [2/5] Starting services with patched code..."
make up-local
sleep 8
curl -sf http://localhost:8001/health >/dev/null && echo "  orchestrator OK"
curl -sf http://localhost:8000/health >/dev/null && echo "  rule engine  OK"

echo
echo "==> [3/5] Re-running pipeline (this is the slow step, ~20 min)..."
make eval-pipeline-save

echo
echo "==> [4/5] Re-computing M2..."
python3 -m evaluation.metrics.citation_relevance \
    --explanations-dir evaluation/results/pipeline_explanations \
    --output evaluation/results/citation_relevance.json

echo
echo "==> [5/5] Pre/post comparison:"
python3 tools/compare_m2.py
