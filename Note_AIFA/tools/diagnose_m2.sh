#!/bin/bash
# Diagnose why M2 didn't move: check pipeline freshness, env vars, and PROVA blocks.
set -euo pipefail

cd "$(dirname "$0")/.." || { echo "[FATAL] cd to Note_AIFA failed" >&2; exit 1; }

echo "=== 1. Pipeline explanations directory ==="
ls evaluation/results/pipeline_explanations/ | wc -l | xargs -I {} echo "  files: {}"
echo "  newest:"
ls -lt evaluation/results/pipeline_explanations/ | head -3 | awk '{print "    "$6, $7, $8, $9}'
echo "  oldest:"
ls -lt evaluation/results/pipeline_explanations/ | tail -2 | head -1 | awk '{print "    "$6, $7, $8, $9}'

echo
echo "=== 2. Orchestrator process env ==="
ORCH_PID=$(lsof -ti:8001 | head -1)
if [ -z "$ORCH_PID" ]; then
    echo "  Orchestrator NOT RUNNING on :8001"
else
    echo "  PID: $ORCH_PID"
    grep -aE "CHROMA_COLLECTION_SUFFIX|CHROMA_DB_DIR" /proc/$ORCH_PID/environ 2>/dev/null | tr '\0' '\n' | sed 's/^/    /'
fi

echo
echo "=== 3. Sample PROVA NORMATIVA blocks (post-fix should have 'char N-N' for v2 collections) ==="
for cid in N66-002 N01-001 N97-007 N13-005 N13-016; do
    f="evaluation/results/pipeline_explanations/${cid}.txt"
    if [ -f "$f" ]; then
        echo "--- $cid (modified $(stat -c %y "$f" | cut -d. -f1)) ---"
        grep -A 0 "Fonte:" "$f" | head -3 | sed 's/^/    /'
    fi
done

echo
echo "=== 4. Pipeline is still running? ==="
PYPID=$(pgrep -f "evaluate_pipeline" | head -1)
if [ -n "$PYPID" ]; then
    echo "  YES — evaluate_pipeline still running (PID $PYPID)"
    echo "  Tail of log:"
    tail -5 .pids/rag_pipeline.log 2>/dev/null | sed 's/^/    /'
else
    echo "  NO — evaluate_pipeline not active"
fi

echo
echo "=== 5. Last 5 lines of orchestrator log ==="
tail -5 .pids/rag_pipeline.log 2>/dev/null | sed 's/^/  /'
