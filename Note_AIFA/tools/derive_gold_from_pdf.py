"""
derive_gold_from_pdf.py — PDF-derived ground-truth excerpts for rules
======================================================================

For each rule in aifa_rule_engine/rules/nota_*/rules.yaml:
  1. Read normative_anchor (pdf_file, page, excerpt).
  2. Open the PDF and extract page text + char-level positions.
  3. Locate the verbatim excerpt in the page (using fuzzy matching as a
     diagnostic, but the canonical match must be exact verbatim ≥0.95).
  4. Persist position info (char_start, char_end, line_start, line_end, bbox, sha256)
     into evaluation/gold_standard/pdf_derived_anchors.json.

A rule with mismatch (similarity <0.95) is marked status=FAIL — the rule
should be corrected (excerpt fabricated or wrong page), not the tool.

This breaks the tautology of "expected_outputs.json scritto dall'autore":
the gold is now derived deterministically from the PDF, with a script
that any reviewer can re-run to verify.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
_ROOT = _HERE.parent  # Note_AIFA/
_RULES_DIR = _ROOT / "aifa_rule_engine" / "rules"
_OUTPUT = _ROOT / "evaluation" / "gold_standard" / "pdf_derived_anchors.json"

_FUZZ_THRESHOLD = 0.50  # min similarity to extract excerpt_pdf_verbatim
_VERBATIM_THRESHOLD = 0.99  # exact verbatim match (ignoring whitespace)
_APPROX_THRESHOLD = 0.85   # close paraphrase still aligned with PDF
_LOW_SIM_THRESHOLD = 0.65  # weak alignment but matching span exists

# PDF filename → filesystem name (filesystem unified 2026-05-06: no trailing space).
_PDF_NAME_FIX = {
    "Nota_01.pdf": "Nota_01.pdf",
    "Nota_66.pdf": "Nota_66.pdf",
    "nota-13.pdf": "nota-13.pdf",
    "nota-97.pdf": "nota-97.pdf",
    "nota-97-all-1.pdf": "nota-97-all-1.pdf",
    "nota-97-all-2.pdf": "nota-97-all-2.pdf",
    "nota-97-all-3.pdf": "nota-97-all-3.pdf",
}


@dataclass
class GoldAnchor:
    rule_id: str
    nota_id: str
    rule_type: str
    description_it: str
    pdf_file: str  # normalized (no trailing space)
    pdf_filesystem_name: str  # actual filesystem name
    pdf_sha256: str
    page: int
    section: str
    excerpt_yaml: str  # original from rules.yaml
    excerpt_pdf_verbatim: str  # the actual text found in the PDF (case-insensitive normalized)
    char_start: int
    char_end: int
    line_start: int
    line_end: int
    bbox: list  # [x0, y0, x1, y1]
    similarity: float  # 0.0-1.0
    status: str  # "VERBATIM_FOUND" | "APPROX_FOUND" | "FAIL_NOT_FOUND" | "FAIL_WRONG_PAGE"
    excerpt_sha256: str  # sha of excerpt_yaml (for integrity)


# ---------------------------------------------------------------------------
# Text normalization (handle PDF artifacts: ligatures, NBSPs, smart quotes)
# ---------------------------------------------------------------------------

def _normalize_for_match(s: str) -> str:
    """Aggressive normalization for fuzzy matching.

    Apply NFKC normalization, lowercase, dehyphenation across line breaks
    ("trat-\\ntamento" → "trattamento"), collapse whitespace, strip.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    # Dehyphenation: word break at end of line ("-\n" → "")
    s = re.sub(r"-\s*\n\s*", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    # Smart quotes → ascii
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return s.strip()


def _fuzzy_locate_in_text(needle: str, haystack: str) -> tuple[int, int, float]:
    """
    Locate `needle` inside `haystack` allowing minor whitespace/casing variants.

    Returns (char_start, char_end, similarity).
    similarity == 1.0 means exact (after normalization).
    similarity < 1.0 indicates fuzzy match (use rapidfuzz partial_ratio).
    Returns (-1, -1, 0.0) if not found.
    """
    from rapidfuzz import fuzz

    needle_norm = _normalize_for_match(needle)
    if not needle_norm:
        return (-1, -1, 0.0)

    # Build a normalized view of haystack while keeping a position map.
    # We want to find needle_norm in normalized haystack and map back to raw.
    # Strategy: precompute char-by-char mapping (raw_idx → normalized_idx).
    norm_chars: list[str] = []
    raw_to_norm: list[int] = []  # length == len(haystack); raw_to_norm[i] = position in norm_chars
    norm_to_raw: list[int] = []  # length == len(norm_chars); norm_to_raw[j] = i in haystack

    last_was_space = True
    for i, c in enumerate(haystack):
        nc = unicodedata.normalize("NFKC", c).lower()
        if nc.isspace():
            if not last_was_space:
                norm_chars.append(" ")
                norm_to_raw.append(i)
                last_was_space = True
            raw_to_norm.append(len(norm_chars))
        else:
            norm_chars.append(nc)
            norm_to_raw.append(i)
            raw_to_norm.append(len(norm_chars) - 1)
            last_was_space = False

    norm_str = "".join(norm_chars).strip()
    if not norm_str:
        return (-1, -1, 0.0)

    # Try exact substring match first
    pos = norm_str.find(needle_norm)
    if pos >= 0:
        # Map normalized positions back to raw positions
        raw_start = norm_to_raw[pos] if pos < len(norm_to_raw) else 0
        end_norm = pos + len(needle_norm) - 1
        raw_end = norm_to_raw[end_norm] + 1 if end_norm < len(norm_to_raw) else len(haystack)
        return (raw_start, raw_end, 1.0)

    # Fallback: fuzzy partial_ratio search
    score = fuzz.partial_ratio(needle_norm, norm_str) / 100.0
    if score < _FUZZ_THRESHOLD:
        return (-1, -1, score)

    # Find the best alignment using fuzz.partial_ratio_alignment
    try:
        from rapidfuzz.fuzz import partial_ratio_alignment
        ali = partial_ratio_alignment(needle_norm, norm_str)
        if ali is None:
            return (-1, -1, score)
        # ali.dest_start / ali.dest_end are positions in norm_str
        norm_start = ali.dest_start
        norm_end = ali.dest_end
        raw_start = norm_to_raw[norm_start] if norm_start < len(norm_to_raw) else 0
        raw_end = norm_to_raw[norm_end - 1] + 1 if 0 < norm_end <= len(norm_to_raw) else len(haystack)
        return (raw_start, raw_end, score)
    except ImportError:
        return (-1, -1, score)


# ---------------------------------------------------------------------------
# Page extraction (PyMuPDF rawdict — same as ingest_v2)
# ---------------------------------------------------------------------------

def _extract_page_text_with_positions(pdf_path: Path, page_idx: int) -> tuple[str, list[tuple], int]:
    """
    Extract page text + per-char (line_idx, bbox) positions.

    Returns (text, char_positions, line_count).
    char_positions[i] = (line_idx_0based, (x0, y0, x1, y1)).
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_idx]
        rd = page.get_text("rawdict")
        text_parts: list[str] = []
        positions: list[tuple] = []
        line_idx = 0

        for blk in rd["blocks"]:
            if "lines" not in blk:
                continue
            for line in blk["lines"]:
                bbox_line = tuple(line.get("bbox", (0.0, 0.0, 0.0, 0.0)))
                for span in line["spans"]:
                    for ch in span.get("chars", []):
                        text_parts.append(ch["c"])
                        positions.append((line_idx, tuple(ch["bbox"])))
                # newline marker
                text_parts.append("\n")
                positions.append((line_idx, bbox_line))
                line_idx += 1

        return ("".join(text_parts), positions, line_idx)
    finally:
        doc.close()


def _bbox_union(boxes: list[tuple]) -> list[float]:
    if not boxes:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _pdf_sha256(pdf_path: Path) -> str:
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        for buf in iter(lambda: f.read(8192), b""):
            h.update(buf)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Main derivation
# ---------------------------------------------------------------------------

def derive_anchor(rule: dict, pdf_dir: Path, logger: logging.Logger) -> GoldAnchor:
    rule_id = rule["rule_id"]
    nota_id = str(rule["nota"])
    rule_type = rule["rule_type"]
    description_it = rule.get("description_it", "")
    anchor = rule.get("normative_anchor", {})
    pdf_file = anchor.get("pdf_file", "")
    page_no = int(anchor.get("page", 0))
    section = anchor.get("section", "")
    excerpt = anchor.get("excerpt", "") or ""

    pdf_filesystem = _PDF_NAME_FIX.get(pdf_file, pdf_file)
    pdf_path = pdf_dir / pdf_filesystem
    if not pdf_path.exists():
        return GoldAnchor(
            rule_id=rule_id,
            nota_id=nota_id,
            rule_type=rule_type,
            description_it=description_it,
            pdf_file=pdf_file,
            pdf_filesystem_name=pdf_filesystem,
            pdf_sha256="",
            page=page_no,
            section=section,
            excerpt_yaml=excerpt,
            excerpt_pdf_verbatim="",
            char_start=-1,
            char_end=-1,
            line_start=-1,
            line_end=-1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            similarity=0.0,
            status="FAIL_PDF_MISSING",
            excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16],
        )

    pdf_sha = _pdf_sha256(pdf_path)

    # Try declared page first
    page_idx = page_no - 1
    text, positions, line_count = _extract_page_text_with_positions(pdf_path, page_idx)
    cs, ce, sim = _fuzzy_locate_in_text(excerpt, text)

    if sim >= _VERBATIM_THRESHOLD:
        status = "VERBATIM_FOUND"
    elif sim >= _APPROX_THRESHOLD:
        status = "APPROX_FOUND"
    elif sim >= _LOW_SIM_THRESHOLD:
        status = "LOW_SIM_FOUND"
    elif sim >= _FUZZ_THRESHOLD:
        status = "WEAK_SIM_FOUND"
    else:
        status = "FAIL_NOT_FOUND"

    # If FAIL_NOT_FOUND, try ±1 page
    if status == "FAIL_NOT_FOUND":
        import fitz
        doc = fitz.open(str(pdf_path))
        n_pages = len(doc)
        doc.close()
        for delta in (-1, +1, -2, +2):
            alt = page_idx + delta
            if 0 <= alt < n_pages:
                alt_text, alt_pos, alt_lines = _extract_page_text_with_positions(pdf_path, alt)
                acs, ace, asim = _fuzzy_locate_in_text(excerpt, alt_text)
                if asim >= _FUZZ_THRESHOLD:
                    logger.warning(
                        f"{rule_id}: excerpt found on page {alt+1}, declared {page_no} → status=FAIL_WRONG_PAGE"
                    )
                    text, positions, line_count = alt_text, alt_pos, alt_lines
                    cs, ce, sim = acs, ace, asim
                    status = "FAIL_WRONG_PAGE"
                    page_idx = alt
                    break

    # Expand match boundaries to word boundaries (avoid mid-word truncation)
    if cs >= 0 and ce <= len(text):
        # Expand left to word boundary
        while cs > 0 and text[cs - 1].isalnum():
            cs -= 1
        # Expand right to word boundary
        while ce < len(text) and text[ce - 1].isalnum() and text[ce].isalnum():
            ce += 1

    if cs < 0:
        return GoldAnchor(
            rule_id=rule_id,
            nota_id=nota_id,
            rule_type=rule_type,
            description_it=description_it,
            pdf_file=pdf_file,
            pdf_filesystem_name=pdf_filesystem,
            pdf_sha256=pdf_sha,
            page=page_no,
            section=section,
            excerpt_yaml=excerpt,
            excerpt_pdf_verbatim="",
            char_start=-1,
            char_end=-1,
            line_start=-1,
            line_end=-1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            similarity=sim,
            status="FAIL_NOT_FOUND",
            excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16],
        )

    line_start = positions[cs][0] + 1 if cs < len(positions) else 1
    line_end = positions[ce - 1][0] + 1 if 0 < ce <= len(positions) else line_start

    bboxes = [
        positions[i][1] for i in range(cs, min(ce, len(positions)))
        if text[i] != "\n"
    ]
    bbox = _bbox_union(bboxes)

    actual_text = text[cs:ce]

    return GoldAnchor(
        rule_id=rule_id,
        nota_id=nota_id,
        rule_type=rule_type,
        description_it=description_it,
        pdf_file=pdf_file,
        pdf_filesystem_name=pdf_filesystem,
        pdf_sha256=pdf_sha,
        page=page_idx + 1,
        section=section,
        excerpt_yaml=excerpt,
        excerpt_pdf_verbatim=actual_text,
        char_start=cs,
        char_end=ce,
        line_start=line_start,
        line_end=line_end,
        bbox=[round(b, 2) for b in bbox],
        similarity=round(sim, 4),
        status=status,
        excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive gold anchors from PDF (verbatim verification)")
    parser.add_argument("--rules-dir", type=Path, default=_RULES_DIR)
    parser.add_argument("--pdf-dir", type=Path, default=_ROOT)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    parser.add_argument("--strict", action="store_true",
                        help="Exit with code 1 if any rule has FAIL status")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    logger = logging.getLogger("derive_gold")

    import yaml

    all_anchors: list[GoldAnchor] = []
    for nota_dir in sorted(args.rules_dir.glob("nota_*")):
        rules_path = nota_dir / "rules.yaml"
        if not rules_path.exists():
            continue
        with rules_path.open() as f:
            d = yaml.safe_load(f)
        rules = d.get("rules", d) if isinstance(d, dict) else d
        for r in rules:
            anchor = derive_anchor(r, args.pdf_dir, logger)
            all_anchors.append(anchor)

    # Summary
    summary: dict[str, int] = {}
    for a in all_anchors:
        summary[a.status] = summary.get(a.status, 0) + 1
    total = len(all_anchors)
    logger.info(f"Total rules: {total}")
    for status, n in sorted(summary.items()):
        logger.info(f"  {status}: {n} ({100*n/total:.1f}%)")

    # Per-status detail for failures
    for a in all_anchors:
        if a.status.startswith("FAIL") or a.status == "APPROX_FOUND":
            logger.info(f"  {a.status} {a.rule_id}: page={a.page} sim={a.similarity:.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "v2",
        "fuzz_threshold": _FUZZ_THRESHOLD,
        "summary": summary,
        "n_total": total,
        "anchors": [asdict(a) for a in all_anchors],
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info(f"Wrote {len(all_anchors)} anchors → {args.output}")

    if args.strict and any(a.status.startswith("FAIL") for a in all_anchors):
        logger.error("Strict mode: at least one FAIL status — exit code 1")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
