"""
Phase 4 — CDSS Evaluation Framework
=====================================

Directory structure:
  gold_standard/     — JSON test cases with expected Rule Engine outputs and explanation criteria
  scripts/           — Evaluation scripts (regression + pipeline)
  results/           — Output reports (gitignored)

Scripts:
  scripts/generate_expected_outputs.py   — Run Rule Engine on all cases, save full EvaluationResult
  scripts/evaluate_rule_engine.py        — Regression: compare Rule Engine output vs gold standard
  scripts/evaluate_pipeline.py           — Full pipeline: call /explain, score explanations

Usage:
  # Step 1: generate expected outputs (required once before regression tests)
  python -m evaluation.scripts.generate_expected_outputs

  # Step 2: regression test Rule Engine (fast, ~1s, no services needed)
  python -m evaluation.scripts.evaluate_rule_engine

  # Step 3: pipeline evaluation (requires make up, ~2-5 min)
  python -m evaluation.scripts.evaluate_pipeline --verbose
"""
