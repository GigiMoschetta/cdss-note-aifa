"""
Composite scores Malasi-style + Decision Score (CDSS-specific).

Reads:
  - evaluation/results/llm_output_metrics.json   (claim coverage, citation, decision_compliance, ...)
  - evaluation/results/nli_faithfulness.json     (NLI entailment)
  - evaluation/results/faithfulness_verbatim.json (3-gram verbatim)
  - evaluation/results/excerpt_match.json        (gold excerpt verbatim)
  - evaluation/results/qaeval.json               (Malasi QAEval F1)
  - evaluation/results/ragas_report.json         (RAGAS metrics)
  - evaluation/results/retrieval_report.json     (Track 2 metrics — for context)

Produces 4 composite scores per case (CDSS-specific extension of Malasi 4.5).
Effective weights as actually implemented (all components NORMALIZED to sum=1
when they are simultaneously available):

  AnswerQuality      base weights [pre-norm]: relevancy 0.30, qaeval_f1 0.70
                     → if both present: 0.30/0.70  (matches Malasi 4.5).
                     → if only one present: that one is rescaled to weight=1.

  ContextualUtility  base weights [pre-norm]:
                       contextual_relevancy 0.45,
                       contextual_precision 0.30,
                       contextual_recall    0.25.
                     → if all three present: 0.45/0.30/0.25 (this is the CDSS
                       extension; Malasi 4.5 originally had only 0.70/0.30 over
                       relevancy+precision — recall is added here because the
                       AIFA gold standard provides it).
                     → otherwise rescaled over available components.

  EvidenceSupport    base weights [pre-norm]:
                       verbatim   0.50,
                       nli        0.20,
                       ragas_faith 0.30,
                       ragas_faith_strict 0.15  (only when ≠ ragas_faith).
                     → if all four present: real normalized weights become
                       0.435 / 0.174 / 0.261 / 0.130 (sums to 1 by division
                       through tot_w=1.15). The thesis must report these
                       *effective* weights, not the pre-norm ones.

  DecisionScore      mean of validator flag pass/fail (no weights).

Overall ALES = α·D + β·E + γ·U + δ·Q with α=0.40, β=0.30, γ=0.20, δ=0.10
(safety-priorized). Cases with missing components produce a "partial" ALES
with rescaled weights and `is_partial: true` — partial and complete cases
are tracked separately in the aggregate to avoid mixing.

Output:
  evaluation/results/composite_scores.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median, stdev


_PROJECT = Path(__file__).resolve().parent.parent.parent


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _index_per_case(d: dict, key: str = "case_id") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in d.get("per_case", []):
        cid = r.get(key)
        if cid:
            out[cid] = r
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--llm-metrics", default="evaluation/results/llm_output_metrics.json")
    p.add_argument("--nli", default="evaluation/results/nli_faithfulness.json")
    p.add_argument("--verbatim", default="evaluation/results/faithfulness_verbatim.json")
    p.add_argument("--excerpt", default="evaluation/results/excerpt_match.json")
    p.add_argument("--qaeval", default="evaluation/results/qaeval.json")
    p.add_argument("--ragas", default="evaluation/results/ragas_report.json")
    p.add_argument(
        "--ragas-fallback",
        default="evaluation/results/ragas_report_subset.json",
        help="Path used when --ragas does not exist (audit fix 2026-05-04 P0.3): "
             "the full RAGAS run is expensive (~10h) and is often skipped in favor of "
             "ragas_report_subset.json (n=20 stratified). When --ragas is absent this "
             "fallback lets composite_scores still produce ContextualUtility / "
             "AnswerQuality on the 20 cases with RAGAS data, marking the rest as partial.",
    )
    p.add_argument("--retrieval", default="evaluation/results/retrieval_report.json")
    p.add_argument("--output", default="evaluation/results/composite_scores.json")
    p.add_argument(
        "--weights",
        default="0.40,0.30,0.20,0.10",
        help="ALES weights: alpha,beta,gamma,delta (Decision,Evidence,Utility,Quality)",
    )
    args = p.parse_args()

    alpha, beta, gamma, delta = (float(x) for x in args.weights.split(","))

    # P0.3 fallback: prefer full RAGAS report; fall back to subset if absent.
    ragas_path = args.ragas
    if not Path(ragas_path).exists() and Path(args.ragas_fallback).exists():
        print(f"  [info] {ragas_path} not found, falling back to {args.ragas_fallback}",
              file=sys.stderr)
        ragas_path = args.ragas_fallback

    llm_idx = _index_per_case(_load_json(args.llm_metrics))
    nli_idx = _index_per_case(_load_json(args.nli))
    verbatim_idx = _index_per_case(_load_json(args.verbatim))
    excerpt_idx = _index_per_case(_load_json(args.excerpt))
    qaeval_idx = _index_per_case(_load_json(args.qaeval))
    ragas_idx = _index_per_case(_load_json(ragas_path))
    retrieval_idx = _index_per_case(_load_json(args.retrieval))

    case_ids = set()
    for d in (llm_idx, nli_idx, verbatim_idx, qaeval_idx, ragas_idx):
        case_ids.update(d.keys())
    case_ids = sorted(case_ids)

    per_case: list[dict] = []
    for cid in case_ids:
        llm = llm_idx.get(cid, {})
        nli = nli_idx.get(cid, {})
        verb = verbatim_idx.get(cid, {})
        exc = excerpt_idx.get(cid, {})
        qae = qaeval_idx.get(cid, {})
        rag = ragas_idx.get(cid, {})
        retr = retrieval_idx.get(cid, {})

        # Decision Score — from existing validators
        decision_compl = (llm.get("decision_compliance") or {}).get("score")

        # Evidence Support — refactor 5.3 (Excellence Plan):
        # The mDeBERTa-XNLI head is multilingual but NOT fine-tuned on Italian
        # regulatory text, so its entailment scores systematically under-estimate
        # faithfulness on AIFA prose. We now treat the deterministic verbatim
        # 3-gram signal as PRIMARY and NLI as SECONDARY (lower-bound). The
        # OVERNIGHT_SUMMARY_v2 already documents this caveat; the composite
        # weights now reflect it numerically.
        #
        # Weight rationale:
        #   verbatim   0.50  — primary, deterministic, language-agnostic
        #   nli        0.20  — secondary, multilingual lower-bound (XNLI floor)
        #   ragas_faith 0.30  — LLM-judge faithfulness, when available
        nli_entail = nli.get("entailment_rate")
        verb_rate = verb.get("verbatim_rate") if verb else None
        ragas_faith = rag.get("faithfulness")
        # audit fix V3-H1 (2026-05-06): use `is not None` instead of `or` so a
        # legitimate faithfulness_strict=0.0 is not silently replaced by ragas_faith.
        # Same pattern as context_relevancy below (audit fix V1-H5).
        _rfs = rag.get("faithfulness_strict")
        ragas_faith_strict = _rfs if _rfs is not None else ragas_faith
        evidence_components = []
        if verb_rate is not None:
            evidence_components.append(("verbatim", verb_rate, 0.50))
        if nli_entail is not None:
            evidence_components.append(("nli", nli_entail, 0.20))
        if ragas_faith is not None:
            evidence_components.append(("ragas_faith", ragas_faith, 0.30))
        if ragas_faith_strict is not None and ragas_faith_strict != ragas_faith:
            evidence_components.append(("ragas_faith_strict", ragas_faith_strict, 0.15))
        # Normalize weights to sum to 1
        evidence = None
        if evidence_components:
            tot_w = sum(w for _, _, w in evidence_components)
            evidence = sum(v * w / tot_w for _, v, w in evidence_components)

        # Answer Quality (Malasi composite)
        answer_relevancy = rag.get("answer_relevancy")
        qaeval_f1 = qae.get("f1")
        components = []
        if answer_relevancy is not None:
            components.append(answer_relevancy * 0.30)
        if qaeval_f1 is not None:
            components.append(qaeval_f1 * 0.70)
        # If only one is available, use it solo
        answer_quality = sum(components) if components else None
        if components and len([c for c in components if c is not None]) < 2:
            # rescale by available weight
            total_w = (0.30 if answer_relevancy is not None else 0) + (0.70 if qaeval_f1 is not None else 0)
            if total_w > 0 and answer_quality is not None:
                answer_quality = answer_quality / total_w

        # Contextual Utility (Malasi composite)
        # Avoid `or` short-circuit: a legitimate context_relevancy=0.0 must NOT
        # be silently replaced with context_precision (audit H5-bis bug).
        _rel = rag.get("context_relevancy")
        ctx_relevancy = _rel if _rel is not None else rag.get("context_precision")
        ctx_precision = rag.get("context_precision")
        ctx_recall = rag.get("context_recall")
        utility_components = []
        if ctx_relevancy is not None:
            utility_components.append(ctx_relevancy * 0.45)
        if ctx_precision is not None:
            utility_components.append(ctx_precision * 0.30)
        if ctx_recall is not None:
            utility_components.append(ctx_recall * 0.25)
        contextual_utility = sum(utility_components) if utility_components else None
        if utility_components:
            total_w = (
                (0.45 if ctx_relevancy is not None else 0)
                + (0.30 if ctx_precision is not None else 0)
                + (0.25 if ctx_recall is not None else 0)
            )
            if total_w > 0 and contextual_utility is not None:
                contextual_utility = contextual_utility / total_w

        # Final ALES — declare partial state explicitly when components are missing
        ales_pieces = []
        components_used = []
        if decision_compl is not None:
            ales_pieces.append((decision_compl, alpha))
            components_used.append("Decision")
        if evidence is not None:
            ales_pieces.append((evidence, beta))
            components_used.append("Evidence")
        if contextual_utility is not None:
            ales_pieces.append((contextual_utility, gamma))
            components_used.append("ContextualUtility")
        if answer_quality is not None:
            ales_pieces.append((answer_quality, delta))
            components_used.append("AnswerQuality")
        if ales_pieces:
            tot_w = sum(w for _, w in ales_pieces)
            ales = sum(v * w / tot_w for v, w in ales_pieces)
        else:
            ales = None

        n_components = len(components_used)
        is_partial = n_components < 4

        per_case.append({
            "case_id": cid,
            "DecisionScore": round(decision_compl, 4) if decision_compl is not None else None,
            "EvidenceSupport": round(evidence, 4) if evidence is not None else None,
            "ContextualUtility": round(contextual_utility, 4) if contextual_utility is not None else None,
            "AnswerQuality": round(answer_quality, 4) if answer_quality is not None else None,
            "ALES": round(ales, 4) if ales is not None else None,
            "ALES_partial": is_partial,
            "n_components_used": n_components,
            "components_used": components_used,
            "components": {
                "nli_entailment_rate": nli_entail,
                "verbatim_quote_rate": verb_rate,
                "ragas_faithfulness": ragas_faith,
                "ragas_answer_relevancy": answer_relevancy,
                "qaeval_f1": qaeval_f1,
                "ragas_context_recall": ctx_recall,
                "claim_coverage": (llm.get("claim_coverage") or {}).get("score"),
                "citation_f1": (llm.get("citation_set") or {}).get("citation_f1"),
            },
        })

    # Aggregate
    valid = lambda key: [r[key] for r in per_case if r.get(key) is not None]
    aggregate = {}
    for k in ("DecisionScore", "EvidenceSupport", "ContextualUtility", "AnswerQuality", "ALES"):
        vals = valid(k)
        if vals:
            # Use statistics.median (interpolated for even n) and statistics.stdev
            # (sample standard deviation, n-1 in denominator) for consistency with
            # other modules and standard reporting conventions.
            aggregate[k] = {
                "mean": round(mean(vals), 4),
                "median": round(median(vals), 4),
                "trimmed_mean": round(mean(sorted(vals)[3:-3] or vals), 4),
                "std": round(stdev(vals), 4) if len(vals) >= 2 else 0.0,
                "n": len(vals),
            }
    # Also report ALES separately for "complete" cases (all 4 components) vs partial,
    # so the thesis can document if there is a population mismatch.
    complete_ales = [r["ALES"] for r in per_case if r.get("ALES") is not None and not r.get("ALES_partial")]
    partial_ales = [r["ALES"] for r in per_case if r.get("ALES") is not None and r.get("ALES_partial")]
    aggregate["ALES_breakdown"] = {
        "complete": {
            "mean": round(mean(complete_ales), 4) if complete_ales else None,
            "n": len(complete_ales),
        },
        "partial": {
            "mean": round(mean(partial_ales), 4) if partial_ales else None,
            "n": len(partial_ales),
        },
    }

    out = {
        "metric": "composite_scores",
        "weights": {"alpha_decision": alpha, "beta_evidence": beta,
                    "gamma_utility": gamma, "delta_quality": delta},
        "n_cases": len(per_case),
        "aggregate": aggregate,
        "per_case": per_case,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Composite Scores — n={len(per_case)} cases")
    print("=" * 60)
    for k in ("DecisionScore", "EvidenceSupport", "ContextualUtility", "AnswerQuality", "ALES"):
        agg = aggregate.get(k)
        if agg:
            print(f"  {k:20s} mean={agg['mean']:.4f}  median={agg['median']:.4f}  "
                  f"trimmed={agg['trimmed_mean']:.4f}  std={agg['std']:.4f}  n={agg['n']}")
    print(f"\nReport: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
