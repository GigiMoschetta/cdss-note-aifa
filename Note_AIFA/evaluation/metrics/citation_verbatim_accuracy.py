"""
M1 — Citation Verbatim Accuracy (CVA)
======================================

For each citation in the LLM explanation (PROVA NORMATIVA blocks), verifies
that the verbatim text claimed at (pdf, page) actually exists in the PDF
at that position.

This metric is NON-TAUTOLOGICAL: it confronts the LLM's output against the
PDF itself, not against an autohor-scripted gold. A failure means the
claimed verbatim does not match the PDF.

Output (per case):
    cva_score: float                    # n_match / n_citations (range [0,1])
    n_citations: int                    # number of PROVA NORMATIVA blocks
    n_match: int                        # citations whose verbatim was found in PDF
    citation_details: list[dict]        # per-citation { rule_id, pdf, page, verbatim, found, similarity }

Aggregate:
    mean, median, std, n_cases_evaluated, n_cases_skipped
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_OUTPUT = _ROOT / "evaluation" / "results" / "citation_verbatim_accuracy.json"
_PDF_DIR = _ROOT


# Reuse the PDF text extractor from derive_gold (same coordinate system)
sys.path.insert(0, str(_ROOT / "tools"))
from derive_gold_from_pdf import _extract_page_text_with_positions, _normalize_for_match  # noqa: E402


_PROVA_RE = re.compile(
    r"---\s*PROVA\s*NORMATIVA\s*---(.*?)---\s*FINE\s*---",
    re.DOTALL | re.IGNORECASE,
)
_RULE_ID_RE = re.compile(r"^\s*Regola:\s*(\S+)", re.MULTILINE)
_FONTE_RE = re.compile(
    r"^\s*Fonte:\s*([\S][^,\n]+?\.pdf)\s*,\s*p\.\s*(\d+)",
    re.MULTILINE | re.IGNORECASE,
)
_VERBATIM_RE = re.compile(r"Testo\s*verbatim:\s*[«\"](.+?)[»\"]", re.DOTALL | re.IGNORECASE)


def _parse_prova_blocks(explanation: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for m in _PROVA_RE.finditer(explanation):
        body = m.group(1)
        rule_id_m = _RULE_ID_RE.search(body)
        fonte_m = _FONTE_RE.search(body)
        verbatim_m = _VERBATIM_RE.search(body)
        if not (rule_id_m and fonte_m and verbatim_m):
            continue
        blocks.append({
            "rule_id": rule_id_m.group(1),
            "pdf_file": fonte_m.group(1).strip(),
            "page": int(fonte_m.group(2)),
            "verbatim": verbatim_m.group(1).strip(),
        })
    return blocks


_PDF_FS_NAME = {
    "Nota_01.pdf": "Nota_01.pdf",
    "Nota_66.pdf": "Nota_66 .pdf",
    "nota-13.pdf": "nota-13.pdf",
    "nota-97.pdf": "nota-97.pdf",
    "nota-97-all-1.pdf": "nota-97-all-1.pdf",
    "nota-97-all-2.pdf": "nota-97-all-2.pdf",
    "nota-97-all-3.pdf": "nota-97-all-3.pdf",
}


def _verify_verbatim_in_pdf(pdf_dir: Path, pdf_file: str, page: int, verbatim: str) -> tuple[bool, float]:
    """Return (found, similarity) for verbatim located in the PDF at given page."""
    fs_name = _PDF_FS_NAME.get(pdf_file, pdf_file)
    pdf_path = pdf_dir / fs_name
    if not pdf_path.exists():
        return (False, 0.0)
    try:
        text, _, _ = _extract_page_text_with_positions(pdf_path, page - 1)
    except Exception:
        return (False, 0.0)

    verb_norm = _normalize_for_match(verbatim)
    text_norm = _normalize_for_match(text)
    if not verb_norm:
        return (False, 0.0)
    if verb_norm in text_norm:
        return (True, 1.0)
    # Fallback: rapidfuzz
    try:
        from rapidfuzz import fuzz
        sim = fuzz.partial_ratio(verb_norm, text_norm) / 100.0
        return (sim >= 0.95, sim)
    except ImportError:
        return (False, 0.0)


def compute_cva(case_result: dict, pdf_dir: Path) -> dict:
    explanation = case_result.get("response_text", "") or case_result.get("explanation", "")
    if not explanation:
        return {"skipped": True, "reason": "no explanation"}

    blocks = _parse_prova_blocks(explanation)
    if not blocks:
        return {
            "skipped": False,
            "n_citations": 0,
            "n_match": 0,
            "cva_score": None,  # undefined when no citations
            "citation_details": [],
        }

    details = []
    n_match = 0
    for blk in blocks:
        found, sim = _verify_verbatim_in_pdf(
            pdf_dir, blk["pdf_file"], blk["page"], blk["verbatim"]
        )
        if found:
            n_match += 1
        details.append({
            "rule_id": blk["rule_id"],
            "pdf_file": blk["pdf_file"],
            "page": blk["page"],
            "verbatim_preview": blk["verbatim"][:120] + ("..." if len(blk["verbatim"]) > 120 else ""),
            "found_in_pdf": found,
            "similarity": round(sim, 4),
        })

    cva = n_match / len(blocks) if blocks else None
    return {
        "skipped": False,
        "n_citations": len(blocks),
        "n_match": n_match,
        "cva_score": round(cva, 4) if cva is not None else None,
        "citation_details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-report", type=Path, default=_PIPELINE_REPORT)
    parser.add_argument("--explanations-dir", type=Path,
                        default=_ROOT / "evaluation" / "results" / "pipeline_explanations")
    parser.add_argument("--pdf-dir", type=Path, default=_PDF_DIR)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    logger = logging.getLogger("cva")

    if not args.pipeline_report.exists():
        logger.error(f"Pipeline report missing: {args.pipeline_report}")
        return 1

    report = json.loads(args.pipeline_report.read_text())
    cases = report.get("case_results", [])
    logger.info(f"Loaded {len(cases)} cases from {args.pipeline_report}")

    per_case: list[dict] = []
    cva_scores: list[float] = []
    for c in cases:
        case_id = c.get("case_id")
        # Get explanation from file if not inline
        if "response_text" not in c and "explanation" not in c:
            ex_path = args.explanations_dir / f"{case_id}.txt"
            if ex_path.exists():
                c["response_text"] = ex_path.read_text()
        result = compute_cva(c, args.pdf_dir)
        result["case_id"] = case_id
        per_case.append(result)
        if not result.get("skipped") and result.get("cva_score") is not None:
            cva_scores.append(result["cva_score"])

    if cva_scores:
        agg = {
            "n_cases_evaluated": len(cva_scores),
            "n_cases_skipped": len(cases) - len(cva_scores),
            "mean": round(mean(cva_scores), 4),
            "median": round(median(cva_scores), 4),
            "std": round(stdev(cva_scores), 4) if len(cva_scores) > 1 else 0.0,
            "min": round(min(cva_scores), 4),
            "max": round(max(cva_scores), 4),
            "n_perfect": sum(1 for s in cva_scores if s == 1.0),
            "n_zero": sum(1 for s in cva_scores if s == 0.0),
        }
    else:
        agg = {"n_cases_evaluated": 0, "n_cases_skipped": len(cases)}

    out = {
        "metric": "M1_citation_verbatim_accuracy",
        "description": "% of LLM citations whose verbatim text exists in the PDF at the declared (page, char) position",
        "tautological": False,
        "n_cases_total": len(cases),
        "aggregate": agg,
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    logger.info(f"CVA mean={agg.get('mean','?')} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
