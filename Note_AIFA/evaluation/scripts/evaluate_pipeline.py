"""
Phase 4 — Full Pipeline Evaluation (RAG + LLM)
================================================

Calls POST /explain on the running Orchestrator service for every gold
standard case and evaluates the generated explanation against quality criteria.

Metrics computed (all deterministic — no LLM calls):
  1. decision_consistency_rate — ratio of explanations where decision_consistent=True
                                 AND decision_contradicted=False
  2. citation_coverage_rate   — ratio where citation_complete=True
  3. hallucination_rate       — ratio where len(suspected_hallucinations) > 0
  4. section_completeness     — ratio where all 5 required sections are present
  5. token_stats              — mean/median/max prompt + completion tokens

Note: NLI/RAGAS entailment-based faithfulness is not implemented; optional future work.

Usage:
    # Services must be running (make up)
    python -m evaluation.scripts.evaluate_pipeline

    python -m evaluation.scripts.evaluate_pipeline \\
        --orchestrator http://localhost:8001 \\
        --nota 97 \\
        --json-report evaluation/results/pipeline_report.json \\
        --timeout 120
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RESULTS_DIR = _ROOT / "evaluation" / "results"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _call_explain(
    orchestrator_url: str,
    case: dict,
    timeout: float,
) -> dict:
    """POST /explain and return the parsed CDSSResponse dict."""
    try:
        import httpx
    except ImportError:
        print("httpx not installed. Run: pip install httpx", file=sys.stderr)
        sys.exit(1)

    inp = case["input"]
    payload = {
        "schema_version": "3.3",
        "note_id": inp["nota_id"],
        "drug_id": inp["drug_id"],
        "patient_data": inp.get("patient_data", {}),
        "clinician_asserted": inp.get("clinician_asserted", {}),
    }
    resp = httpx.post(
        f"{orchestrator_url}/explain",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ── Deterministic explanation checkers ───────────────────────────────────────

_SECTION_PATTERN = re.compile(
    # Primary format: "1. SECTION" (as instructed in prompt)
    # Fallback formats: "**SECTION**", "## SECTION" (common LLM markdown deviations)
    r"^\s*(?:\d+\.\s+|#{1,3}\s+|\*{1,2})?"
    r"(DECISIONE|MOTIVAZIONE|RACCOMANDAZIONI|DATI MANCANTI|FONTI)"
    r"(?:\*{1,2})?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_REQUIRED_SECTIONS = {
    "DECISIONE", "MOTIVAZIONE", "RACCOMANDAZIONI", "DATI MANCANTI", "FONTI"
}


def _check_section_completeness(explanation: str) -> tuple[bool, list[str]]:
    """Return (all_present, list_of_missing_sections)."""
    found = {m.group(1).upper() for m in _SECTION_PATTERN.finditer(explanation)}
    missing = sorted(_REQUIRED_SECTIONS - found)
    return len(missing) == 0, missing


def _check_string_criteria(explanation: str, criteria: dict) -> dict:
    """Check must_contain_strings and must_not_contain_strings."""
    results = {}
    exp_lower = explanation.lower()

    for s in criteria.get("must_contain_strings", []):
        results[f"contains:{s!r}"] = s.lower() in exp_lower

    for s in criteria.get("must_not_contain_strings", []):
        # Special case: "RIMBORSABILE" is a substring of "NON_RIMBORSABILE" and also
        # appears naturally in Italian negations like "non è rimborsabile".
        # Strip all negated forms before checking, so a correct NON_RIMBORSABILE
        # response doesn't trigger a false positive.
        check_text = re.sub(r"non[_\s]rimborsabile", "", exp_lower)
        check_text = re.sub(r"non\s+(?:è|e|risulta|appare|viene|sarà)\s+rimborsabile",
                            "", check_text)
        results[f"not_contains:{s!r}"] = s.lower() not in check_text

    return results


def _evaluate_case(cdss_response: dict, case: dict) -> dict:
    """
    Compute per-case quality metrics from the CDSSResponse dict.
    Returns a dict with all metric values.
    """
    explanation = cdss_response.get("generated_explanation", "")
    validation = cdss_response.get("validation") or {}
    criteria = case.get("explanation_criteria", {})

    # From validators (already computed by orchestrator)
    decision_consistent_ok = (
        validation.get("decision_consistent", False)
        and not validation.get("decision_contradicted", False)
    )
    citation_complete = validation.get("citation_complete", False)
    missing_citations = validation.get("missing_citations", [])
    hallucinations = validation.get("suspected_hallucinations", [])

    # Section completeness (deterministic regex)
    sections_ok, missing_sections = _check_section_completeness(explanation)

    # String criteria from gold standard
    string_checks = _check_string_criteria(explanation, criteria)
    strings_ok = all(string_checks.values())

    # Token counts
    prompt_tokens = cdss_response.get("prompt_tokens", 0)
    completion_tokens = cdss_response.get("completion_tokens", 0)

    # Justification check
    justification_complete = validation.get("justification_complete", True)

    return {
        "case_id": case["id"],
        "description": case["description"],
        "category": case.get("category", ""),
        "decision_consistent": decision_consistent_ok,
        "citation_complete": citation_complete,
        "has_hallucination": len(hallucinations) > 0,
        "sections_complete": sections_ok,
        "strings_ok": strings_ok,
        "justification_complete": justification_complete,
        "overall_pass": decision_consistent_ok and citation_complete and sections_ok and strings_ok,
        "details": {
            "decision_consistent": validation.get("decision_consistent"),
            "decision_contradicted": validation.get("decision_contradicted"),
            "missing_citations": missing_citations,
            "suspected_hallucinations": hallucinations,
            "missing_sections": missing_sections,
            "string_checks": string_checks,
            "missing_justification_rules": validation.get("missing_justification_rules", []),
        },
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "llm_model": cdss_response.get("llm_model", "unknown"),
        "retrieved_chunks_metadata": [
            {
                "chunk_id": c.get("chunk_id", ""),
                "pdf_file": c.get("pdf_file", ""),
                "page": c.get("page", 0),
                "section": c.get("section", ""),
                "retrieval_stage": c.get("retrieval_stage", ""),
                "score": c.get("score", 0.0),
            }
            for c in cdss_response.get("retrieved_chunks", [])
        ],
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate_metrics(case_results: list[dict]) -> dict:
    """Compute aggregate metrics across all cases."""
    if not case_results:
        return {}

    n = len(case_results)
    faithful_count = sum(1 for r in case_results if r["decision_consistent"])
    citation_count = sum(1 for r in case_results if r["citation_complete"])
    hallucination_count = sum(1 for r in case_results if r["has_hallucination"])
    sections_count = sum(1 for r in case_results if r["sections_complete"])
    justified_count = sum(1 for r in case_results if r.get("justification_complete", True))
    pass_count = sum(1 for r in case_results if r["overall_pass"])

    all_prompt_tokens = [r["token_usage"]["prompt_tokens"] for r in case_results if "token_usage" in r]
    all_completion_tokens = [r["token_usage"]["completion_tokens"] for r in case_results if "token_usage" in r]
    all_total_tokens = [r["token_usage"]["total_tokens"] for r in case_results if "token_usage" in r]

    return {
        "total_cases": n,
        "overall_pass_rate": round(pass_count / n, 4),
        "decision_consistency_rate": round(faithful_count / n, 4),
        "citation_coverage_rate": round(citation_count / n, 4),
        "hallucination_rate": round(hallucination_count / n, 4),
        "section_completeness_rate": round(sections_count / n, 4),
        "justification_snippet_coverage_rate": round(justified_count / n, 4),
        "counts": {
            "pass": pass_count,
            "decision_consistent": faithful_count,
            "citation_complete": citation_count,
            "with_hallucinations": hallucination_count,
            "sections_complete": sections_count,
        },
        "token_stats": {
            "prompt_tokens": {
                "mean": round(mean(all_prompt_tokens), 1) if all_prompt_tokens else 0,
                "median": median(all_prompt_tokens) if all_prompt_tokens else 0,
                "max": max(all_prompt_tokens) if all_prompt_tokens else 0,
            },
            "completion_tokens": {
                "mean": round(mean(all_completion_tokens), 1) if all_completion_tokens else 0,
                "median": median(all_completion_tokens) if all_completion_tokens else 0,
                "max": max(all_completion_tokens) if all_completion_tokens else 0,
            },
            "total_tokens": {
                "mean": round(mean(all_total_tokens), 1) if all_total_tokens else 0,
                "median": median(all_total_tokens) if all_total_tokens else 0,
                "max": max(all_total_tokens) if all_total_tokens else 0,
            },
        },
    }


# ── Per-category breakdown ─────────────────────────────────────────────────────

def _category_breakdown(case_results: list[dict]) -> dict[str, dict]:
    by_category: dict[str, list] = {}
    for r in case_results:
        cat = r.get("category", "unknown")
        by_category.setdefault(cat, []).append(r)

    breakdown = {}
    for cat, cases in sorted(by_category.items()):
        n = len(cases)
        breakdown[cat] = {
            "total": n,
            "pass": sum(1 for c in cases if c["overall_pass"]),
            "decision_consistent": sum(1 for c in cases if c["decision_consistent"]),
            "citation_complete": sum(1 for c in cases if c["citation_complete"]),
        }
    return breakdown


# ── Main ──────────────────────────────────────────────────────────────────────

def run_pipeline_evaluation(
    orchestrator_url: str,
    nota_ids: list[str],
    timeout: float,
    fail_fast: bool,
    verbose: bool,
    save_explanations: bool = False,
) -> dict:
    all_case_results: list[dict] = []
    total_errors = 0

    for nota_id in nota_ids:
        gold_path = _GOLD_DIR / f"nota_{nota_id}_cases.json"
        if not gold_path.exists():
            print(f"[SKIP] nota_{nota_id}_cases.json not found")
            continue

        with open(gold_path, encoding="utf-8") as f:
            gold = json.load(f)

        cases = gold["cases"]
        print(f"\nNota {nota_id} ({len(cases)} cases):")

        for case in cases:
            case_id = case["id"]
            print(f"  [{case_id}] calling /explain ...", end=" ", flush=True)
            t0 = time.monotonic()
            try:
                cdss_response = _call_explain(orchestrator_url, case, timeout)
                elapsed = time.monotonic() - t0
                metrics = _evaluate_case(cdss_response, case)
                metrics["latency_s"] = round(elapsed, 2)
                all_case_results.append(metrics)

                if save_explanations:
                    exp_dir = _ROOT / "evaluation" / "results" / "pipeline_explanations"
                    exp_dir.mkdir(parents=True, exist_ok=True)
                    (exp_dir / f"{case_id}.txt").write_text(
                        cdss_response.get("generated_explanation", ""),
                        encoding="utf-8",
                    )

                status = "✓" if metrics["overall_pass"] else "✗"
                print(
                    f"{status} ({elapsed:.1f}s) "
                    f"consistent={metrics['decision_consistent']} "
                    f"citation={metrics['citation_complete']} "
                    f"halluc={metrics['has_hallucination']} "
                    f"sections={metrics['sections_complete']}"
                )
                if verbose and not metrics["overall_pass"]:
                    details = metrics["details"]
                    if not metrics["decision_consistent"]:
                        print(f"    DECISION: consistent={details['decision_consistent']} "
                              f"contradicted={details['decision_contradicted']}")
                    if details["missing_citations"]:
                        print(f"    MISSING CITATIONS: {details['missing_citations']}")
                    if details["suspected_hallucinations"]:
                        print(f"    HALLUCINATIONS: {details['suspected_hallucinations']}")
                    if details["missing_sections"]:
                        print(f"    MISSING SECTIONS: {details['missing_sections']}")
                    if not all(details["string_checks"].values()):
                        failed = [k for k, v in details["string_checks"].items() if not v]
                        print(f"    STRING CHECKS FAILED: {failed}")

                if fail_fast and not metrics["overall_pass"]:
                    print("\n[--fail-fast] Stopping after first failure.")
                    goto_summary = True
                    break

            except Exception as exc:
                elapsed = time.monotonic() - t0
                print(f"ERROR ({elapsed:.1f}s): {exc}", file=sys.stderr)
                all_case_results.append({
                    "case_id": case_id,
                    "description": case["description"],
                    "category": case.get("category", ""),
                    "error": str(exc),
                    "overall_pass": False,
                    "decision_consistent": False,
                    "citation_complete": False,
                    "has_hallucination": False,
                    "sections_complete": False,
                    "strings_ok": False,
                })
                total_errors += 1
                if fail_fast:
                    break
        else:
            continue
        break  # fail_fast break propagation

    aggregate = _aggregate_metrics(all_case_results)
    breakdown = _category_breakdown(all_case_results)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orchestrator_url": orchestrator_url,
        "nota_ids_evaluated": nota_ids,
        "errors": total_errors,
        "aggregate_metrics": aggregate,
        "category_breakdown": breakdown,
        "case_results": all_case_results,
    }

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PIPELINE EVALUATION SUMMARY")
    print("=" * 70)
    if aggregate:
        print(f"Total cases:           {aggregate['total_cases']}")
        print(f"Overall pass rate:     {aggregate['overall_pass_rate'] * 100:.1f}%  "
              f"({aggregate['counts']['pass']}/{aggregate['total_cases']})")
        print(f"Decision consistency:  {aggregate['decision_consistency_rate'] * 100:.1f}%  "
              f"({aggregate['counts']['decision_consistent']}/{aggregate['total_cases']})")
        print(f"Citation coverage:     {aggregate['citation_coverage_rate'] * 100:.1f}%  "
              f"({aggregate['counts']['citation_complete']}/{aggregate['total_cases']})")
        print(f"Hallucination rate:    {aggregate['hallucination_rate'] * 100:.1f}%  "
              f"({aggregate['counts']['with_hallucinations']}/{aggregate['total_cases']})")
        print(f"Section completeness:  {aggregate['section_completeness_rate'] * 100:.1f}%  "
              f"({aggregate['counts']['sections_complete']}/{aggregate['total_cases']})")
        tok = aggregate["token_stats"]
        print(f"\nToken usage (mean):    "
              f"prompt={tok['prompt_tokens']['mean']:.0f}  "
              f"completion={tok['completion_tokens']['mean']:.0f}  "
              f"total={tok['total_tokens']['mean']:.0f}")
    print("=" * 70)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the full CDSS pipeline (RAG + LLM) against gold standard cases"
    )
    parser.add_argument(
        "--orchestrator", default="http://localhost:8001",
        help="Orchestrator service URL (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--nota", nargs="+", default=["97", "01", "13", "66"],
        help="Which nota(e) to evaluate (default: all)"
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="HTTP request timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help="Stop after first failed case"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print failure details for each case"
    )
    parser.add_argument(
        "--json-report", metavar="PATH",
        default=str(_RESULTS_DIR / "pipeline_report.json"),
        help="Write JSON report to this path"
    )
    parser.add_argument(
        "--save-explanations", action="store_true",
        help="Save raw LLM explanations to evaluation/results/pipeline_explanations/"
    )
    args = parser.parse_args()

    # Check orchestrator health first
    try:
        import httpx
        health = httpx.get(f"{args.orchestrator}/health", timeout=10.0)
        health_data = health.json()
        print(f"Orchestrator: {args.orchestrator}")
        print(f"Status: {health_data.get('status')}")
        print(f"LLM: {health_data.get('llm_backend')}/{health_data.get('llm_model')}\n")
    except Exception as exc:
        print(f"ERROR: Cannot reach orchestrator at {args.orchestrator}: {exc}", file=sys.stderr)
        print("Make sure the services are running: make up", file=sys.stderr)
        return 2

    report = run_pipeline_evaluation(
        orchestrator_url=args.orchestrator,
        nota_ids=args.nota,
        timeout=args.timeout,
        fail_fast=args.fail_fast,
        verbose=args.verbose,
        save_explanations=args.save_explanations,
    )

    out_path = Path(args.json_report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport written to: {out_path}")

    failed = sum(1 for r in report["case_results"] if not r.get("overall_pass"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
