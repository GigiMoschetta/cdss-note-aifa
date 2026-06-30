"""Compare M2 (Citation Containment Score) before and after the orchestrator fix.

Usage:
    python3 tools/compare_m2.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"

PRE_PATH = RESULTS / "citation_relevance_pre_fix_2026-04-30.json"
POST_PATH = RESULTS / "citation_relevance.json"

pre = json.load(open(PRE_PATH))["aggregate"]
post = json.load(open(POST_PATH))["aggregate"]

print(f"PRE  CCS mean={pre['mean']:.4f} | evaluated={pre['n_cases_evaluated']} | zeros={pre['n_zero']} | perfect={pre['n_perfect']}")
print(f"POST CCS mean={post['mean']:.4f} | evaluated={post['n_cases_evaluated']} | zeros={post['n_zero']} | perfect={post['n_perfect']}")

delta = post["mean"] - pre["mean"]
rel = (delta / pre["mean"] * 100) if pre["mean"] else float("inf")
print(f"\nDelta M2 mean = {delta:+.4f}  ({rel:+.0f}% relativo)")
