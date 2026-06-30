"""
Expand each gold case with three new fields:
    gold_answer            ~150-200 word ideal explanation, derived from rule
                            engine output + rule structured_motivation +
                            relevant chunk excerpts.
    gold_relevant_chunks   ranked list of (rule_id, pdf_file, page, decision_role)
                            taken from blocking_rules + passed_rules.
    gold_claims            3-5 atomic claims that the model answer SHOULD
                            cover, with `must_appear` and optional `preferred`.

The output is written *next to* the existing gold files as
`nota_*_cases_extended.json` so the user can diff & review before promoting
them to the canonical `nota_*_cases.json`.

Usage:
    python -m evaluation.scripts.expand_gold_standard
    python -m evaluation.scripts.expand_gold_standard --in-place    # overwrite
    python -m evaluation.scripts.expand_gold_standard --only N97-001,N66-024
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


_PROJECT = Path(__file__).resolve().parent.parent.parent
_GOLD_DIR = _PROJECT / "evaluation" / "gold_standard"
_RULES_DIR = _PROJECT / "aifa_rule_engine" / "rules"


def _load_rules_index() -> dict[str, dict]:
    """Return {rule_id: rule_dict} across all 4 nota."""
    idx: dict[str, dict] = {}
    for nota in ("01", "13", "66", "97"):
        with open(_RULES_DIR / f"nota_{nota}" / "rules.yaml", encoding="utf-8") as f:
            for r in yaml.safe_load(f):
                idx[r["rule_id"]] = r
    return idx


def _decision_role(rule: dict, expected_blocking: list[str]) -> str:
    rt = rule.get("rule_type", "?")
    if rule["rule_id"] in expected_blocking:
        return "blocking"
    if rt == "SCOPE":
        return "scope"
    if rt in ("EXCL_HARD", "EXCEPTION"):
        return "exclusion_check"
    if rt in ("INCLUSION", "PATHWAY"):
        return "inclusion_check"
    if rt.startswith("GUIDANCE"):
        return "guidance"
    return "other"


def _extract_atomic_claims(rule: dict) -> list[str]:
    """Extract 1-2 atomic claims from a rule (rule_type-aware)."""
    claims: list[str] = []
    desc = (rule.get("description_it") or "").strip()
    rationale = (rule.get("structured_motivation", {}) or {}).get("rationale_it", "").strip()
    impact = (rule.get("structured_motivation", {}) or {}).get("clinical_impact", "").strip()

    # Heuristic: take the first sentence of description and impact
    for txt in (impact, rationale, desc):
        if not txt:
            continue
        sentences = re.split(r"(?<=[\.\!\?])\s+", txt.replace("\n", " "))
        for s in sentences:
            s = s.strip().rstrip(".")
            if 20 <= len(s) <= 150:
                claims.append(s)
                if len(claims) >= 2:
                    break
        if len(claims) >= 2:
            break

    return claims[:2]


def _build_gold_answer(case: dict, rules_idx: dict[str, dict]) -> str:
    """Compose a ~150-200 word ideal explanation."""
    expected = case.get("expected_rule_engine", {}) or {}
    decision = expected.get("reimbursement_decision", "?")
    nota_id = case["input"]["nota_id"]
    drug = case["input"]["drug_id"]

    blocking_ids = expected.get("expected_blocking_rule_ids", []) or []
    flag_ids = expected.get("expected_clinical_flag_rule_ids", []) or []
    missing_fields = expected.get("missing_fields_coverage", []) or []
    pdf_ref = case.get("pdf_reference", {}) or {}

    parts: list[str] = []

    # Opening
    if decision == "RIMBORSABILE":
        parts.append(f"Il farmaco {drug} è RIMBORSABILE secondo la Nota AIFA {nota_id}.")
    elif decision == "NON_RIMBORSABILE":
        parts.append(
            f"Il farmaco {drug} NON È RIMBORSABILE secondo la Nota AIFA {nota_id}."
        )
    elif decision == "NON_DETERMINABILE":
        parts.append(
            f"La rimborsabilità del farmaco {drug} secondo la Nota AIFA {nota_id} "
            f"è NON DETERMINABILE per dati clinici insufficienti."
        )
    elif decision == "ROUTED":
        route = expected.get("route_to") or "altra Nota"
        parts.append(
            f"Il farmaco {drug} è regolato dalla Nota {route} (e non dalla Nota {nota_id})."
        )
    else:
        parts.append(f"Decisione: {decision}.")

    # Rationale: blocking rules
    if blocking_ids:
        parts.append("Motivazione:")
        for rid in blocking_ids[:3]:
            rule = rules_idx.get(rid)
            if not rule:
                continue
            mot = (rule.get("structured_motivation", {}) or {}).get("rationale_it", "")
            mot_short = re.sub(r"\s+", " ", mot).strip().rstrip(".")
            anchor = rule.get("normative_anchor", {}) or {}
            citation = f"{anchor.get('pdf_file','?')} p.{anchor.get('page','?')}"
            if mot_short:
                parts.append(f"{mot_short} (Fonte: {citation}).")

    # Clinical flags
    if flag_ids:
        parts.append("Considerazioni cliniche:")
        for fid in flag_ids[:2]:
            rule = rules_idx.get(fid)
            if rule:
                impact = (rule.get("structured_motivation", {}) or {}).get(
                    "clinical_impact", ""
                )
                impact = re.sub(r"\s+", " ", impact).strip().rstrip(".")
                if impact:
                    parts.append(f"{impact}.")

    # Missing data
    if missing_fields:
        parts.append(
            "Dati mancanti rilevanti per la decisione: "
            + ", ".join(missing_fields[:5])
            + "."
        )

    # Closing citation
    if pdf_ref:
        parts.append(
            f"Riferimento normativo principale: {pdf_ref.get('pdf_file','?')} "
            f"p.{pdf_ref.get('page','?')}."
        )

    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_gold_relevant_chunks(case: dict, rules_idx: dict[str, dict]) -> list[dict]:
    expected = case.get("expected_rule_engine", {}) or {}
    blocking = expected.get("expected_blocking_rule_ids", []) or []
    flags = expected.get("expected_clinical_flag_rule_ids", []) or []

    items: list[dict] = []
    rank = 1

    # blocking rules first
    for rid in blocking:
        rule = rules_idx.get(rid)
        if not rule:
            continue
        anchor = rule.get("normative_anchor", {}) or {}
        items.append({
            "rank": rank,
            "rule_id": rid,
            "pdf_file": anchor.get("pdf_file"),
            "page": anchor.get("page"),
            "section": anchor.get("section"),
            "decision_role": "blocking",
        })
        rank += 1

    # then SCOPE rules of the same nota (if not already in blocking)
    nota_id = case["input"]["nota_id"]
    for rid, rule in rules_idx.items():
        if rule.get("nota") != nota_id:
            continue
        if rid in blocking:
            continue
        if rule.get("rule_type") == "SCOPE":
            anchor = rule.get("normative_anchor", {}) or {}
            items.append({
                "rank": rank,
                "rule_id": rid,
                "pdf_file": anchor.get("pdf_file"),
                "page": anchor.get("page"),
                "section": anchor.get("section"),
                "decision_role": "scope",
            })
            rank += 1
            break

    # finally clinical flags
    for rid in flags:
        if rid in [it["rule_id"] for it in items]:
            continue
        rule = rules_idx.get(rid)
        if not rule:
            continue
        anchor = rule.get("normative_anchor", {}) or {}
        items.append({
            "rank": rank,
            "rule_id": rid,
            "pdf_file": anchor.get("pdf_file"),
            "page": anchor.get("page"),
            "section": anchor.get("section"),
            "decision_role": "guidance",
        })
        rank += 1

    return items


def _build_gold_claims(case: dict, rules_idx: dict[str, dict]) -> list[dict]:
    expected = case.get("expected_rule_engine", {}) or {}
    blocking = expected.get("expected_blocking_rule_ids", []) or []
    flags = expected.get("expected_clinical_flag_rule_ids", []) or []

    claims: list[dict] = []
    cid = 1

    # Top: the decision itself
    decision = expected.get("reimbursement_decision", "?")
    claims.append({
        "id": f"c{cid}",
        "text": f"La decisione di rimborsabilità è {decision}.",
        "must_appear": True,
    })
    cid += 1

    # Claims from blocking rules
    for rid in blocking[:2]:
        rule = rules_idx.get(rid)
        if not rule:
            continue
        for atomic in _extract_atomic_claims(rule)[:1]:
            claims.append({
                "id": f"c{cid}",
                "text": atomic,
                "must_appear": True,
            })
            cid += 1

    # Claims from clinical flags (preferred but not required)
    for rid in flags[:1]:
        rule = rules_idx.get(rid)
        if not rule:
            continue
        for atomic in _extract_atomic_claims(rule)[:1]:
            claims.append({
                "id": f"c{cid}",
                "text": atomic,
                "must_appear": False,
                "preferred": True,
            })
            cid += 1

    return claims[:5]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in-place", action="store_true", help="overwrite gold files")
    p.add_argument("--only", default=None, help="comma-separated case_ids")
    args = p.parse_args()

    only = {x.strip() for x in (args.only or "").split(",") if x.strip()}
    rules_idx = _load_rules_index()

    n_processed = 0
    for nota in ("01", "13", "66", "97"):
        gold_path = _GOLD_DIR / f"nota_{nota}_cases.json"
        with open(gold_path, encoding="utf-8") as f:
            data = json.load(f)

        for case in data["cases"]:
            if only and case["id"] not in only:
                continue
            case["gold_answer"] = _build_gold_answer(case, rules_idx)
            case["gold_relevant_chunks"] = _build_gold_relevant_chunks(case, rules_idx)
            case["gold_claims"] = _build_gold_claims(case, rules_idx)
            n_processed += 1

        out_path = gold_path if args.in_place else gold_path.with_name(
            f"nota_{nota}_cases_extended.json"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  wrote {out_path}")

    print(f"\nProcessed {n_processed} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
