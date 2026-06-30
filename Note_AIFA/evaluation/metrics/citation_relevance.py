"""
M2 — Citation Containment Score (CCS, formerly CRS)
====================================================

For each case, the gold (from pdf_derived_anchors.json + expected_outputs_v2.json)
specifies which (pdf, char_start, char_end) ranges should be cited.

The LLM citations (from PROVA NORMATIVA blocks) are parsed and compared:

  CCS = mean over blocking_rules of containment(gold_range, llm_range)
        = |gold ∩ llm_range| / |gold|

Where char-ranges are integer half-open intervals on the same (pdf, page).

Why containment instead of Jaccard (audit fix 2026-04-30):
- Chunks v2 span ~1800 chars (TARGET_CHARS); gold spans ~50-300 chars.
- Jaccard penalises large chunks even when they fully cover the gold span,
  because |chunk ∪ gold| ≈ |chunk| ≫ |gold ∩ chunk|.
- Containment answers the relevant question: "does the cited chunk window
  cover the verbatim text the rule is anchored to?" — 1.0 = fully covered.

The Jaccard is still computed and reported for backward compatibility.

Outputs:
  per-case: list of (rule_id, gold_range, llm_range, containment, jaccard)
  aggregate: mean, median, n_cases
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from statistics import mean, median, stdev

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_EXPLANATIONS_DIR = _ROOT / "evaluation" / "results" / "pipeline_explanations"
_OUTPUT = _ROOT / "evaluation" / "results" / "citation_relevance.json"


# Parse PROVA NORMATIVA "Fonte: <pdf>, p. <N>, righe <a>-<b> (char <cs>-<ce>)"
_FONTE_GRANULAR_RE = re.compile(
    r"Fonte:\s*([\S][^,\n]+?\.pdf)\s*,\s*p\.\s*(\d+)"
    r"(?:\s*,\s*(?:righe|riga)\s*(\d+)(?:-(\d+))?)?"
    r"(?:\s*\(\s*char\s*(\d+)-(\d+)\s*\))?",
    re.IGNORECASE,
)
_RULE_ID_RE = re.compile(r"^\s*Regola:\s*(\S+)", re.MULTILINE)
_PROVA_BLOCK_RE = re.compile(
    r"---\s*PROVA\s*NORMATIVA\s*---(.*?)---\s*FINE\s*---",
    re.DOTALL | re.IGNORECASE,
)


def _parse_llm_citations(explanation: str) -> dict[str, dict]:
    """Map rule_id → {pdf, page, char_start, char_end}."""
    out: dict[str, dict] = {}
    for m in _PROVA_BLOCK_RE.finditer(explanation):
        body = m.group(1)
        rid_m = _RULE_ID_RE.search(body)
        fonte_m = _FONTE_GRANULAR_RE.search(body)
        if not (rid_m and fonte_m):
            continue
        rule_id = rid_m.group(1)
        pdf = fonte_m.group(1).strip()
        page = int(fonte_m.group(2))
        cs = int(fonte_m.group(5)) if fonte_m.group(5) else None
        ce = int(fonte_m.group(6)) if fonte_m.group(6) else None
        out[rule_id] = {
            "pdf_file": pdf,
            "page": page,
            "char_start": cs,
            "char_end": ce,
        }
    return out


def _load_gold(gold_dir: Path) -> dict[str, list]:
    """Map case_id → list of (rule_id, gold_pdf, gold_page, gold_cs, gold_ce, status)"""
    out: dict[str, list] = {}
    for nota in ["01", "13", "66", "97"]:
        path = gold_dir / f"nota_{nota}_expected_outputs_v2.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        for o in d.get("outputs", []):
            cid = o.get("case_id")
            blocking = o.get("pdf_gold", {}).get("blocking_rules_with_pdf_anchor", [])
            entries = []
            for br in blocking:
                if not br.get("excerpt_pdf_verbatim"):
                    continue
                entries.append({
                    "rule_id": br.get("rule_id"),
                    "pdf_file": br.get("pdf_file"),
                    "page": br.get("page"),
                    "char_start": br.get("char_start"),
                    "char_end": br.get("char_end"),
                    "anchor_status": br.get("anchor_status"),
                })
            if entries:
                out[cid] = entries
    return out


def _range_jaccard(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Jaccard of two integer half-open ranges [a0,a1) and [b0,b1)."""
    if a[0] >= a[1] or b[0] >= b[1]:
        return 0.0
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def _range_containment(gold: tuple[int, int], chunk: tuple[int, int]) -> float:
    """Containment of `gold` inside `chunk`: |gold ∩ chunk| / |gold|.

    Returns 1.0 when the chunk fully covers the gold span — the relevant
    quantity for a citation that points to a (pdf, page, char_range) anchor.
    """
    if gold[0] >= gold[1] or chunk[0] >= chunk[1]:
        return 0.0
    inter = max(0, min(gold[1], chunk[1]) - max(gold[0], chunk[0]))
    gold_len = gold[1] - gold[0]
    return inter / gold_len if gold_len > 0 else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-dir", type=Path, default=_GOLD_DIR)
    parser.add_argument("--explanations-dir", type=Path, default=_EXPLANATIONS_DIR)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("crs")

    gold = _load_gold(args.gold_dir)
    log.info(f"Loaded gold for {len(gold)} cases (with blocking anchors)")

    files = sorted(args.explanations_dir.glob("*.txt"))
    log.info(f"Loaded {len(files)} explanation files")

    per_case: list[dict] = []
    crs_values: list[float] = []
    for f in files:
        cid = f.stem
        gold_entries = gold.get(cid)
        if not gold_entries:
            per_case.append({"case_id": cid, "skipped": True, "reason": "no gold blocking"})
            continue
        explanation = f.read_text()
        llm_cites = _parse_llm_citations(explanation)

        per_rule = []
        rule_containments = []
        rule_jaccards = []
        for ge in gold_entries:
            rid = ge["rule_id"]
            llm_c = llm_cites.get(rid)
            if not llm_c or llm_c.get("char_start") is None:
                per_rule.append({
                    "rule_id": rid,
                    "gold_range": [ge["char_start"], ge["char_end"]],
                    "llm_range": None,
                    "containment": 0.0,
                    "jaccard": 0.0,
                })
                rule_containments.append(0.0)
                rule_jaccards.append(0.0)
                continue
            # Same pdf+page check
            if llm_c["pdf_file"].strip() != (ge["pdf_file"] or "").strip() or llm_c["page"] != ge["page"]:
                per_rule.append({
                    "rule_id": rid,
                    "gold_range": [ge["char_start"], ge["char_end"]],
                    "llm_range": [llm_c["char_start"], llm_c["char_end"]],
                    "containment": 0.0,
                    "jaccard": 0.0,
                    "reason": "pdf/page mismatch",
                })
                rule_containments.append(0.0)
                rule_jaccards.append(0.0)
                continue
            gold_range = (ge["char_start"], ge["char_end"])
            llm_range = (llm_c["char_start"], llm_c["char_end"])
            cont = _range_containment(gold_range, llm_range)
            j = _range_jaccard(gold_range, llm_range)
            per_rule.append({
                "rule_id": rid,
                "gold_range": list(gold_range),
                "llm_range": list(llm_range),
                "containment": round(cont, 4),
                "jaccard": round(j, 4),
            })
            rule_containments.append(cont)
            rule_jaccards.append(j)

        ccs = mean(rule_containments) if rule_containments else 0.0
        crs = mean(rule_jaccards) if rule_jaccards else 0.0
        crs_values.append(ccs)  # primary: containment (renamed metric)
        per_case.append({
            "case_id": cid,
            "n_blocking_rules": len(gold_entries),
            "n_cited": sum(1 for r in per_rule if r["llm_range"] is not None),
            "ccs": round(ccs, 4),
            "crs_jaccard_legacy": round(crs, 4),
            "per_rule": per_rule,
        })

    if crs_values:
        agg = {
            "n_cases_evaluated": len(crs_values),
            "mean": round(mean(crs_values), 4),
            "median": round(median(crs_values), 4),
            "std": round(stdev(crs_values), 4) if len(crs_values) > 1 else 0.0,
            "min": round(min(crs_values), 4),
            "max": round(max(crs_values), 4),
            "n_perfect": sum(1 for v in crs_values if v == 1.0),
            "n_zero": sum(1 for v in crs_values if v == 0.0),
        }
    else:
        agg = {"n_cases_evaluated": 0}

    out = {
        "metric": "M2_citation_containment_score",
        "description": "Containment |gold ∩ llm_chunk| / |gold|: fraction of the PDF-gold char span covered by the LLM-cited chunk window",
        "primary_metric": "containment (CCS)",
        "secondary_metric": "jaccard (legacy CRS, biased by chunk size mismatch)",
        "tautological": False,
        "n_cases_total": len(files),
        "aggregate": agg,
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(f"CCS containment mean={agg.get('mean','?')} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
