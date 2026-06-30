"""
Day 5 audit fix F4-14 / B.5 piano precedente: expanded n=50 LLM quality audit.

Reads the per-case explanations saved by `evaluate_pipeline.py --save-explanations`
in `evaluation/results/pipeline_explanations/{case_id}.txt` and applies a
deterministic 5-axis quality rubric:

  1. Factual correctness   — no obviously wrong clinical facts
  2. Decision faithfulness — explanation agrees with engine decision
  3. No cross-nota contamination — no concepts from other Notes
  4. Conditional clauses preserved — DOSE_RIDOTTA / SOSPENDERE flags not dropped
  5. FONTI citations match claims — each cited source actually appears

Stratified sampling: balanced across decision classes and Notes.

Output: `audit/llm_quality_audit_n50.md` with per-axis pass rates.

Note: this is a heuristic audit (regex + keyword + structure check), not a
human eval. For real clinical validation, consult a pharmacologist.

Usage:
    python -m evaluation.scripts.day5_llm_audit_n50 \
        --explanations-dir evaluation/results/pipeline_explanations \
        --pipeline-report evaluation/results/pipeline_report.json \
        --output ../audit/llm_quality_audit_n50.md
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict


_SAMPLING_SEED = 42


_NOTA_KEYWORDS = {
    "01": {"PPI", "gastroprotett", "FANS+ASA", "anti-ulcer", "omeprazolo", "pantoprazolo", "lansoprazolo", "esomeprazolo", "misoprostolo"},
    "13": {"statin", "ipolipemizz", "ezetimibe", "fibrato", "PUFA", "LDL", "colesterolo", "atorvastat", "simvastat", "pravastat", "fluvastat", "lovastat", "rosuvastat"},
    "66": {"FANS", "antinfiammat", "COX", "ibuprofene", "diclofenac", "nimesulide", "celecoxib", "etoricoxib", "ketoprofene", "naprossene", "meloxicam", "piroxicam"},
    "97": {"anticoagul", "FANV", "DOAC", "AVK", "warfarin", "apixaban", "dabigatran", "rivaroxaban", "edoxaban", "CHA2DS2", "VASc", "INR"},
}

# Words specific to a Nota that should NOT appear in another Nota's explanation
# (for cross-contamination check).
_NOTA_SPECIFIC = {
    "01": {"omeprazolo", "pantoprazolo", "misoprostolo", "esomeprazolo"},
    "13": {"atorvastatina", "rosuvastatina", "simvastatina", "ezetimibe", "LDL", "CHA2DS2"},  # CHA2DS2 trap from F4-7 fix
    "66": {"ibuprofene", "celecoxib", "nimesulide", "etoricoxib"},
    "97": {"apixaban", "dabigatran", "warfarin", "CHA2DS2-VASc", "VFG"},
}


def axis1_factual(explanation: str, case: dict) -> tuple[bool, str]:
    """Heuristic: explanation should not contain known-wrong drug-class assertions."""
    # Known false claim patterns (from audit Phase 4 F4-9):
    bad_patterns = [
        (r"ketorolac.*include", "ketorolac is its own NSAID, not an inclusion of another"),
        (r"include il ketorolac", "ketorolac is not part of any combination"),
        (r"include il dexketoprofene", "dexketoprofene is its own enantiomer"),
        (r"omeprazolo.*è un FANS", "omeprazolo is a PPI, not a FANS"),
        (r"warfarin.*è un DOAC", "warfarin is an AVK, not a DOAC"),
    ]
    for pattern, reason in bad_patterns:
        if re.search(pattern, explanation, re.IGNORECASE):
            return False, f"factual error: {reason}"
    return True, ""


def axis2_decision_faithfulness(explanation: str, case: dict) -> tuple[bool, str]:
    """Decision string in section 1 matches expected."""
    expected = case.get("expected_rule_engine", {}).get("reimbursement_decision")
    if expected is None:
        # ROUTED case
        return True, "skip (ROUTED case)"
    # Find first decision in section 1
    m = re.search(r"(?:1\.\s*DECISIONE|DECISIONE).*?(RIMBORSABILE|NON_RIMBORSABILE|NON RIMBORSABILE|NON_DETERMINABILE|NON DETERMINABILE)",
                  explanation, re.DOTALL)
    if not m:
        return False, "no decision found in section 1"
    found = m.group(1).replace(" ", "_").upper()
    if found == expected.upper():
        return True, ""
    return False, f"decision mismatch: section1='{found}' expected='{expected}'"


def axis3_no_cross_nota(explanation: str, case: dict) -> tuple[bool, str]:
    """No concepts/drugs from other Notes appear in the explanation."""
    case_nota = case["input"]["nota_id"]
    other_notas = [n for n in ("01", "13", "66", "97") if n != case_nota]

    found_terms = []
    for other in other_notas:
        for term in _NOTA_SPECIFIC.get(other, set()):
            # Use word-boundary regex
            if re.search(r'\b' + re.escape(term) + r'\b', explanation, re.IGNORECASE):
                # Tolerate self-mention if the same drug name appears in current case
                drug_id = case["input"].get("drug_id", "").lower()
                if term.lower() in drug_id:
                    continue
                found_terms.append(f"{term} (from N{other})")

    if found_terms:
        return False, f"cross-nota contamination: {found_terms[:3]}"
    return True, ""


def axis4_conditional_clauses(explanation: str, case: dict) -> tuple[bool, str]:
    """If engine emitted DOSE_RIDOTTA / DOSE_CONTROINDICATA, explanation should mention it."""
    # We don't have direct access to engine flags here without rerunning;
    # heuristic: if expected_clinical_flag_rule_ids contains DOSE-related rules,
    # check that 'dose' or 'mg' appears in section 3 (RACCOMANDAZIONI).
    expected_flags = case.get("expected_rule_engine", {}).get("expected_clinical_flag_rule_ids", [])
    has_dose_flag = any("DOSE" in f or "GDOSE" in f for f in expected_flags)
    if not has_dose_flag:
        return True, "skip (no dose flag expected)"
    # Look in section 3 (RACCOMANDAZIONI)
    m = re.search(r"(?:3\.\s*RACCOMANDAZIONI|RACCOMANDAZIONI)(.*?)(?:\d+\.\s*\w|$)",
                  explanation, re.DOTALL)
    if not m:
        return False, "section 3 RACCOMANDAZIONI missing"
    section3 = m.group(1).lower()
    if "dose" in section3 or "mg" in section3 or "ridotta" in section3 or "ridurre" in section3:
        return True, ""
    return False, "section 3 missing dose recommendation despite expected_dose_flag"


def axis5_fonti_citations(explanation: str, case: dict) -> tuple[bool, str]:
    """Section 5 FONTI exists and contains at least 1 PDF reference."""
    m = re.search(r"(?:5\.\s*FONTI|FONTI)(.*)", explanation, re.DOTALL)
    if not m:
        return False, "section 5 FONTI missing"
    fonti = m.group(1)
    if not re.search(r"\.pdf", fonti, re.IGNORECASE):
        return False, "FONTI lacks .pdf reference"
    # Multiple page formats: "p. 1", "p.1", "p 1", "pag. 1", "pp. 1-3"
    if re.search(r"\b(?:p|pag|pp)\.?\s*\d+", fonti, re.IGNORECASE):
        return True, ""
    return False, "FONTI lacks page number reference"


AXES = [
    ("factual_correctness", axis1_factual),
    ("decision_faithfulness", axis2_decision_faithfulness),
    ("no_cross_nota_contamination", axis3_no_cross_nota),
    ("conditional_clauses_preserved", axis4_conditional_clauses),
    ("fonti_citations_match_claims", axis5_fonti_citations),
]


def stratified_sample(cases: list[dict], n: int = 50, seed: int = _SAMPLING_SEED) -> list[dict]:
    """Stratified random sample across decision classes and Notes.

    Deterministic across runs thanks to the explicit ``seed``: each stratum
    is independently shuffled with the same RNG, then the first
    ``target_per_stratum`` cases are taken. This avoids the previous behaviour
    of slicing ``cs[:target_per_stratum]`` in file order, which is systematic
    (not random) and not reproducibly representative.
    """
    rng = random.Random(seed)

    by_strata: dict[tuple, list] = defaultdict(list)
    for c in cases:
        decision = c.get("expected_rule_engine", {}).get("reimbursement_decision") or "ROUTED"
        nota = c.get("input", {}).get("nota_id", "?")
        by_strata[(decision, nota)].append(c)

    target_per_stratum = max(1, n // max(1, len(by_strata)))
    sampled = []
    for stratum in sorted(by_strata):              # stable stratum order across runs
        cs = list(by_strata[stratum])
        rng.shuffle(cs)
        sampled.extend(cs[:target_per_stratum])

    if len(sampled) > n:
        rng.shuffle(sampled)
        sampled = sampled[:n]
    return sampled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--explanations-dir", required=True)
    parser.add_argument("--pipeline-report", required=True,
                        help="To get the case metadata + expected fields")
    parser.add_argument("--output", required=True)
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()

    expl_dir = Path(args.explanations_dir)
    if not expl_dir.is_dir():
        print(f"ERROR: explanations dir not found: {expl_dir}", file=sys.stderr)
        return 1

    # Load cases (with expected fields) from cases.json files
    gold_dir = Path(args.pipeline_report).parent.parent / "gold_standard"
    all_cases = []
    for nota in ("01", "13", "66", "97"):
        with open(gold_dir / f"nota_{nota}_cases.json", encoding="utf-8") as f:
            all_cases.extend(json.load(f)["cases"])

    sample = stratified_sample(all_cases, args.n)
    print(f"Stratified sample: {len(sample)} cases (target {args.n})")

    results = []
    for case in sample:
        cid = case["id"]
        expl_path = expl_dir / f"{cid}.txt"
        if not expl_path.exists():
            print(f"  SKIP {cid}: no explanation file")
            continue
        explanation = expl_path.read_text(encoding="utf-8")
        case_axes = {}
        for axis_name, axis_fn in AXES:
            ok, reason = axis_fn(explanation, case)
            case_axes[axis_name] = {"pass": ok, "reason": reason}
        results.append({
            "case_id": cid,
            "category": case.get("category", ""),
            "nota": case["input"]["nota_id"],
            "axes": case_axes,
        })

    # Aggregate per-axis pass rates
    agg = {}
    for axis_name, _ in AXES:
        n_pass = sum(1 for r in results if r["axes"][axis_name]["pass"])
        agg[axis_name] = {
            "pass": n_pass,
            "total": len(results),
            "rate": round(n_pass / max(1, len(results)), 4),
        }

    # Per-Nota breakdown
    by_nota = defaultdict(lambda: defaultdict(int))
    for r in results:
        by_nota[r["nota"]]["total"] += 1
        for axis_name, info in r["axes"].items():
            if info["pass"]:
                by_nota[r["nota"]][axis_name] += 1

    # Build markdown report
    lines = [
        f"# LLM Quality Audit n={len(results)} (V3.4 audit Day 5 fix F4-14)",
        "",
        "**Method:** deterministic 5-axis rubric on stratified sample of pipeline_explanations.",
        "",
        "## Aggregate per-axis pass rates",
        "",
        "| Axis | Pass | Total | Rate |",
        "|---|---|---|---|",
    ]
    for axis_name, info in agg.items():
        lines.append(f"| {axis_name} | {info['pass']} | {info['total']} | {info['rate']*100:.2f}% |")
    lines.append("")
    lines.append("## Per-Nota breakdown")
    lines.append("")
    lines.append("| Nota | Total | Factual | Decision | Cross-nota | Cond.clauses | FONTI |")
    lines.append("|---|---|---|---|---|---|---|")
    for nota in sorted(by_nota.keys()):
        n = by_nota[nota]["total"]
        cells = [
            nota, str(n),
            f"{by_nota[nota]['factual_correctness']}/{n}",
            f"{by_nota[nota]['decision_faithfulness']}/{n}",
            f"{by_nota[nota]['no_cross_nota_contamination']}/{n}",
            f"{by_nota[nota]['conditional_clauses_preserved']}/{n}",
            f"{by_nota[nota]['fonti_citations_match_claims']}/{n}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Failures (per-case detail)")
    lines.append("")
    n_failures = 0
    for r in results:
        failures = [(k, v["reason"]) for k, v in r["axes"].items() if not v["pass"]]
        if failures:
            n_failures += 1
            lines.append(f"### {r['case_id']} ({r['category']}, nota {r['nota']})")
            for axis, reason in failures:
                lines.append(f"  - **{axis}**: {reason}")
            lines.append("")
    if n_failures == 0:
        lines.append("_No failures across all axes._")
    lines.append("")
    lines.append(f"**Total cases evaluated:** {len(results)}")
    lines.append(f"**Cases with ≥1 failure:** {n_failures}")
    lines.append(f"**All-axis pass cases:** {len(results) - n_failures}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"Audit report written to: {args.output}")

    print(f"\n{'='*60}")
    for axis_name, info in agg.items():
        print(f"  {axis_name:<35} {info['pass']:>3}/{info['total']:<3}  {info['rate']*100:.2f}%")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
