#!/usr/bin/env python3
"""Verifica la consistenza fra i numeri citati nella tesi e i JSON canonici.

Confronta i valori aggregati della run overnight 2026-05-13 (corretta il
2026-05-29 con la QAEval completa) presenti in evaluation/results/ con i
numeri riportati nel testo della tesi. Ogni voce stampa PASS o FAIL;
exit code 0 solo se tutte le voci passano.

Uso:
    python tools/verify_thesis_numbers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "evaluation" / "results"

# (descrizione, file, percorso nel JSON, valore citato in tesi, tolleranza)
CHECKS = [
    # Rule engine — RQ1
    ("Casi totali", "rule_engine_report.json", ("total_cases",), 122, 0),
    ("Pass rate rule engine", "rule_engine_report.json", ("pass_rate",), 1.0, 0),
    ("Support RIMBORSABILE", "rule_engine_report.json",
     ("confusion_matrix", "RIMBORSABILE", "RIMBORSABILE"), 69, 0),
    ("Support NON_RIMBORSABILE", "rule_engine_report.json",
     ("confusion_matrix", "NON_RIMBORSABILE", "NON_RIMBORSABILE"), 39, 0),
    ("Support NON_DETERMINABILE", "rule_engine_report.json",
     ("confusion_matrix", "NON_DETERMINABILE", "NON_DETERMINABILE"), 9, 0),
    ("Support ROUTED", "rule_engine_report.json",
     ("confusion_matrix", "ROUTED", "ROUTED"), 5, 0),
    # Retrieval — RQ2
    ("Recall@10", "retrieval_report.json", ("aggregate", "recall_at_k", "10"), 0.9068, 1e-4),
    ("MRR", "retrieval_report.json", ("aggregate", "mrr"), 1.0, 0),
    ("Precision@3", "retrieval_report.json", ("aggregate", "precision_at_k", "3"), 0.989, 1e-3),
    ("Precision@5", "retrieval_report.json", ("aggregate", "precision_at_k", "5"), 0.970, 1e-3),
    # Citazioni e fedeltà — RQ3/RQ6
    ("Citation F1", "llm_output_metrics.json", ("aggregate", "citation_f1", "mean"), 0.9988, 1e-4),
    ("Hallucination rate", "pipeline_report.json",
     ("aggregate_metrics", "hallucination_rate"), 0.0, 0),
    ("QAEval F1 medio", "qaeval.json", ("aggregate", "mean_f1"), 0.1715, 1e-4),
    ("QAEval F1 mediana", "qaeval.json", ("aggregate", "median_f1"), 0.1667, 1e-4),
    ("QAEval n casi", "qaeval.json", ("aggregate", "n_cases_evaluated"), 121, 0),
    # Composito ALES — RQ7
    ("ALES medio", "composite_scores.json", ("aggregate", "ALES", "mean"), 0.6810, 1e-4),
    ("ALES mediana", "composite_scores.json", ("aggregate", "ALES", "median"), 0.6874, 1e-4),
    ("ALES std", "composite_scores.json", ("aggregate", "ALES", "std"), 0.1083, 1e-4),
    ("ALES complete (mean)", "composite_scores.json",
     ("aggregate", "ALES_breakdown", "complete", "mean"), 0.7008, 1e-4),
    ("ALES complete (n)", "composite_scores.json",
     ("aggregate", "ALES_breakdown", "complete", "n"), 81, 0),
    ("ALES partial (mean)", "composite_scores.json",
     ("aggregate", "ALES_breakdown", "partial", "mean"), 0.6419, 1e-4),
    ("ALES partial (n)", "composite_scores.json",
     ("aggregate", "ALES_breakdown", "partial", "n"), 41, 0),
    ("DecisionScore", "composite_scores.json",
     ("aggregate", "DecisionScore", "mean"), 1.0, 0),
    ("EvidenceSupport", "composite_scores.json",
     ("aggregate", "EvidenceSupport", "mean"), 0.4075, 1e-4),
    ("ContextualUtility", "composite_scores.json",
     ("aggregate", "ContextualUtility", "mean"), 0.6442, 1e-4),
    ("ContextualUtility n", "composite_scores.json",
     ("aggregate", "ContextualUtility", "n"), 81, 0),
    ("AnswerQuality", "composite_scores.json",
     ("aggregate", "AnswerQuality", "mean"), 0.3008, 1e-4),
    ("Peso ALES decisione", "composite_scores.json", ("weights", "alpha_decision"), 0.40, 0),
    ("Peso ALES evidenza", "composite_scores.json", ("weights", "beta_evidence"), 0.30, 0),
    ("Peso ALES utilità", "composite_scores.json", ("weights", "gamma_utility"), 0.20, 0),
    ("Peso ALES qualità", "composite_scores.json", ("weights", "delta_quality"), 0.10, 0),
    # Baseline — RQ5
    ("Baseline LLM-only Macro F1", "baseline_llm_only.json", None, 0.2408, 1e-4),
    ("Baseline LLM+RAG Macro F1", "baseline_llm_rag.json", None, 0.3152, 1e-4),
    ("Baseline LLM+RAG+rerank Macro F1", "baseline_llm_rag_rerank.json", None, 0.2759, 1e-4),
    ("Baseline maggioritaria Macro F1", "baseline_majority_class.json", None, 0.2408, 1e-4),
]


def dig(data, path):
    """Naviga il JSON lungo path; le chiavi numeriche vengono provate anche come int."""
    cur = data
    for key in path:
        if isinstance(cur, dict):
            cur = cur[key] if key in cur else cur[int(key)]
        else:
            cur = cur[int(key)]
    return cur


def find_macro_f1(data):
    """Cerca ricorsivamente una chiave macro_f1/macro_avg_f1 nel report baseline."""
    if isinstance(data, dict):
        for key in ("macro_f1", "macro_avg_f1", "macro_f1_score"):
            if key in data and isinstance(data[key], (int, float)):
                return data[key]
        for value in data.values():
            found = find_macro_f1(value)
            if found is not None:
                return found
    return None


def main() -> int:
    failures = 0
    for desc, fname, path, expected, tol in CHECKS:
        fpath = RESULTS / fname
        try:
            data = json.loads(fpath.read_text())
            actual = find_macro_f1(data) if path is None else dig(data, path)
            ok = abs(float(actual) - float(expected)) <= tol
        except Exception as exc:  # file mancante o struttura diversa
            print(f"FAIL  {desc:34s} errore: {exc}")
            failures += 1
            continue
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{status}  {desc:34s} tesi={expected}  json={actual}")
    total = len(CHECKS)
    print(f"\n{total - failures}/{total} verifiche superate.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
