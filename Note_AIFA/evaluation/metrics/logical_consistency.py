"""
M5 — Logical Consistency (LC)
==============================

Pattern-detects logical errors in LLM explanations that the existing
hallucination_rate metric (lexical-only) cannot catch:

  L1: Numeric range vs threshold contradictions
      e.g. "[4,4] inferiore alla soglia di 2"  (4 is NOT < 2)
      e.g. "punteggio 3, inferiore alla soglia 2"

  L2: Decision-vs-rationale internal contradiction
      e.g. §1 "RIMBORSABILE" but §2 "non sarà rimborsabile"
      e.g. §1 "NON_RIMBORSABILE" but §2 "il farmaco è rimborsabile"

  L3: Operator inversion in score block
      e.g. "supera la soglia ≥2" applied to a score of 1

  L4: Numeric inconsistency across sections
      e.g. §2 "score 4" but §3 "score 2"

LC = 1 - (n_violations / n_cases). A higher value means fewer logical errors.

Output (per case):
    violations: list[dict]      # {type: L1|L2|L3|L4, snippet, explanation}
    n_violations: int
    has_violations: bool

Aggregate:
    lc_score = 1 - (n_cases_with_violations / n_cases)
    violations_by_type: {L1: n, L2: n, L3: n, L4: n}
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_OUTPUT = _ROOT / "evaluation" / "results" / "logical_consistency.json"


# L1: range/threshold contradictions.
# Each pattern ends with a verb (inferiore|supera|raggiunge|sopra|sotto)
# and is paired with a numeric assertion that can be falsified.
_L1_PATTERNS = [
    # "[a,b]... inferiore... soglia... X"
    (re.compile(
        r"\[\s*(\d+)\s*,\s*(\d+)\s*\][^.]{0,80}inferiore[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "range_below_threshold"),
    # "punteggio Y... inferiore... soglia... X"
    (re.compile(
        r"(?:punteggio|score)[^.]{0,40}(?<!\d)(\d+)(?!\d)[^.]{0,40}inferiore[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "scalar_below_threshold"),
    # "punteggio Y... supera... soglia... X" (Y < X)
    (re.compile(
        r"(?:punteggio|score)[^.]{0,40}(?<!\d)(\d+)(?!\d)[^.]{0,40}supera[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "scalar_exceeds_threshold"),
    # "[a,b]... supera... soglia... X" with b < X (range max < threshold)
    (re.compile(
        r"\[\s*(\d+)\s*,\s*(\d+)\s*\][^.]{0,80}supera[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "range_exceeds_threshold"),
    # "Y è/non è/risulta sopra/sotto soglia X" — generic
    (re.compile(
        r"(?:punteggio|score)[^.]{0,40}(?<!\d)(\d+)(?!\d)[^.]{0,40}(?:sopra|al\s+di\s+sopra)[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "scalar_above_threshold"),
    (re.compile(
        r"(?:punteggio|score)[^.]{0,40}(?<!\d)(\d+)(?!\d)[^.]{0,40}(?:sotto|al\s+di\s+sotto)[^.]{0,40}soglia[^.]{0,15}(\d+)",
        re.IGNORECASE,
    ), "scalar_below_threshold_alt"),
]


def _check_l1_range_threshold(explanation: str) -> list[dict]:
    """Detect numeric range/threshold contradictions."""
    violations: list[dict] = []
    for regex, ptype in _L1_PATTERNS:
        for m in regex.finditer(explanation):
            try:
                if ptype == "range_below_threshold":
                    a, b, thr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if a >= thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Range [{a},{b}] is NOT below threshold {thr}",
                        })
                elif ptype == "scalar_below_threshold":
                    val, thr = int(m.group(1)), int(m.group(2))
                    if val >= thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Score {val} is NOT below threshold {thr}",
                        })
                elif ptype == "scalar_exceeds_threshold":
                    val, thr = int(m.group(1)), int(m.group(2))
                    if val < thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Score {val} does NOT exceed threshold {thr}",
                        })
                elif ptype == "range_exceeds_threshold":
                    a, b, thr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if b < thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Range max {b} does NOT exceed threshold {thr}",
                        })
                elif ptype == "scalar_above_threshold":
                    val, thr = int(m.group(1)), int(m.group(2))
                    if val < thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Score {val} is NOT above threshold {thr}",
                        })
                elif ptype == "scalar_below_threshold_alt":
                    val, thr = int(m.group(1)), int(m.group(2))
                    if val >= thr:
                        violations.append({
                            "type": "L1_" + ptype,
                            "snippet": m.group(0)[:200],
                            "explanation": f"Score {val} is NOT below threshold {thr}",
                        })
            except (ValueError, IndexError):
                continue
    return violations


def _check_l2_decision_internal_contradiction(explanation: str, decision: str) -> list[dict]:
    """Detect decision-vs-rationale contradictions inside the explanation."""
    violations: list[dict] = []
    if not decision:
        return violations
    decision_upper = decision.upper()

    if decision_upper == "RIMBORSABILE":
        # Look for "non rimborsabile" / "non sarà rimborsabile" / etc.
        bad_patterns = [
            r"non\s+(?:è|sarà|risulta|appare|verrà)\s+(?:più\s+)?rimborsabile",
            r"non\s+(?:lo|la)\s+rimborsa",
            r"non[\s_]rimborsabile",
        ]
        for pat in bad_patterns:
            for m in re.finditer(pat, explanation, flags=re.IGNORECASE):
                violations.append({
                    "type": "L2_decision_negation",
                    "snippet": m.group(0),
                    "explanation": f"Decision is RIMBORSABILE but text contains negation",
                })
    elif decision_upper == "NON_RIMBORSABILE":
        # Bare positive RIMBORSABILE without negation
        clean = re.sub(r"non[_\s]rimborsabile", "", explanation, flags=re.IGNORECASE)
        clean = re.sub(r"non\s+(?:è|sarà|risulta|appare|verrà)\s+(?:più\s+)?rimborsabile", "", clean, flags=re.IGNORECASE)
        if re.search(r"il\s+farmaco\s+(?:è|risulta|sarà)\s+rimborsabile", clean, flags=re.IGNORECASE):
            violations.append({
                "type": "L2_decision_positive_assertion",
                "snippet": "(in cleaned explanation)",
                "explanation": "Decision is NON_RIMBORSABILE but text asserts farmaco è rimborsabile",
            })
    return violations


def _check_l4_numeric_inconsistency(explanation: str) -> list[dict]:
    """Detect numeric inconsistency: same metric mentioned with different values."""
    violations: list[dict] = []
    # CHA2DS2-VASc score mentions
    pat = re.compile(
        r"(?:punteggio|score)?\s*CHA[\s_-]*2?DS2[\s_-]*VASc\s*"
        r"(?:totale)?\s*(?:è|=|di|risulta(?:nte)?)?\s*\[?\s*(\d+)",
        re.IGNORECASE,
    )
    values = [int(m.group(1)) for m in pat.finditer(explanation)]
    if len(set(values)) > 1:
        violations.append({
            "type": "L4_score_inconsistency",
            "snippet": f"CHA2DS2-VASc values: {values}",
            "explanation": f"Multiple distinct scores cited: {sorted(set(values))}",
        })
    return violations


# ── L5: semantic-clinical contradictions (Fase 5.2) ─────────────────────────
#
# Beyond pure numerical patterns we also catch clinically incoherent claims.
# Each pattern is a (regex, condition_on_decision, description) triple. The
# regex must match the SUSPICIOUS text in the explanation; the violation is
# only emitted when the rule's `condition_on_decision` predicate also holds
# on the deterministic decision string. This avoids false positives when the
# explanation merely paraphrases a contraindication that did NOT trigger.

_L5_RULES: list[tuple[re.Pattern[str], str, str]] = [
    # Hard contraindication declared but decision is RIMBORSABILE
    (re.compile(
        r"controindicazion[ei]\s+(?:assolut[ae]|hard)",
        re.IGNORECASE,
    ), "RIMBORSABILE",
     "absolute contraindication asserted while decision is RIMBORSABILE"),

    # "non eleggibile" or "non idoneo" but decision RIMBORSABILE
    (re.compile(
        r"(?:non\s+(?:è\s+)?eleggibile|non\s+(?:è\s+)?idone[oa])",
        re.IGNORECASE,
    ), "RIMBORSABILE",
     "non-eligibility asserted while decision is RIMBORSABILE"),

    # "criteri non (sono|risultano|appaiono|sembrano)? soddisfatti" but RIMBORSABILE
    (re.compile(
        r"criter[ei]\s+non\s+(?:sono\s+|risultano\s+|appaiono\s+|sembrano\s+)?soddisfatt[ie]",
        re.IGNORECASE,
    ), "RIMBORSABILE",
     "criteria not satisfied asserted while decision is RIMBORSABILE"),

    # "criteri soddisfatti" / "tutti i criteri sono soddisfatti" but NON_RIMBORSABILE
    (re.compile(
        r"(?:tutti\s+i\s+criter[ei]\s+(?:sono\s+)?soddisfatt[ie]|"
        r"criter[ei]\s+(?:risultano|sono)\s+soddisfatt[ie])",
        re.IGNORECASE,
    ), "NON_RIMBORSABILE",
     "criteria satisfied asserted while decision is NON_RIMBORSABILE"),

    # Mentions of routing to another Note in the body but decision FINAL
    # is harder to validate cheaply — left as future work.
]


def _check_l5_semantic_clinical(explanation: str, decision: str) -> list[dict]:
    """Pattern-detect semantic-clinical contradictions vs the decision."""
    violations: list[dict] = []
    if not decision:
        return violations
    decision_upper = decision.upper().replace("-", "_")
    for regex, dec_cond, desc in _L5_RULES:
        if dec_cond != decision_upper:
            continue
        for m in regex.finditer(explanation):
            violations.append({
                "type": "L5_semantic_clinical_contradiction",
                "snippet": m.group(0)[:200],
                "explanation": desc,
            })
    return violations


def compute_lc(case_result: dict) -> dict:
    explanation = case_result.get("response_text", "") or case_result.get("explanation", "")
    if not explanation:
        return {"skipped": True, "reason": "no explanation"}

    decision = case_result.get("decision_engine") or case_result.get("decision", "")

    violations: list[dict] = []
    violations.extend(_check_l1_range_threshold(explanation))
    violations.extend(_check_l2_decision_internal_contradiction(explanation, decision))
    violations.extend(_check_l4_numeric_inconsistency(explanation))
    violations.extend(_check_l5_semantic_clinical(explanation, decision))

    return {
        "skipped": False,
        "n_violations": len(violations),
        "has_violations": len(violations) > 0,
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-report", type=Path, default=_PIPELINE_REPORT)
    parser.add_argument("--explanations-dir", type=Path,
                        default=_ROOT / "evaluation" / "results" / "pipeline_explanations")
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    logger = logging.getLogger("lc")

    if not args.pipeline_report.exists():
        logger.error(f"Pipeline report missing: {args.pipeline_report}")
        return 1

    report = json.loads(args.pipeline_report.read_text())
    cases = report.get("case_results", [])
    logger.info(f"Loaded {len(cases)} cases")

    per_case: list[dict] = []
    n_with_violations = 0
    n_evaluated = 0
    by_type: dict[str, int] = {}

    for c in cases:
        case_id = c.get("case_id")
        # Always load explanation from file (the inline pipeline_report has metadata only)
        ex_path = args.explanations_dir / f"{case_id}.txt"
        if ex_path.exists():
            c["response_text"] = ex_path.read_text()
        # Decision is in details.engine_decision or similar
        details = c.get("details", {}) if isinstance(c.get("details"), dict) else {}
        c["decision"] = details.get("engine_decision") or c.get("decision_engine") or ""
        result = compute_lc(c)
        result["case_id"] = case_id
        per_case.append(result)
        if not result.get("skipped"):
            n_evaluated += 1
            if result.get("has_violations"):
                n_with_violations += 1
                for v in result.get("violations", []):
                    t = v.get("type", "unknown")
                    by_type[t] = by_type.get(t, 0) + 1

    lc_score = 1.0 - (n_with_violations / n_evaluated) if n_evaluated else None

    out = {
        "metric": "M5_logical_consistency",
        "description": "% of cases without pattern-detected logical errors (numeric, threshold, decision-rationale contradictions)",
        "tautological": False,
        "n_cases_total": len(cases),
        "aggregate": {
            "n_cases_evaluated": n_evaluated,
            "n_with_violations": n_with_violations,
            "lc_score": round(lc_score, 4) if lc_score is not None else None,
            "violations_by_type": dict(sorted(by_type.items())),
        },
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    logger.info(f"LC score={out['aggregate']['lc_score']} ({n_with_violations}/{n_evaluated} with violations) → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
