#!/bin/bash
# Re-run M2 (Citation Containment Score) on current explanations,
# then print pre/post comparison table.

set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m evaluation.metrics.citation_relevance \
    --explanations-dir evaluation/results/pipeline_explanations \
    --output evaluation/results/citation_relevance.json

python3 tools/compare_m2.py
