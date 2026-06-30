"""
auto_fix_excerpts.py — Replace YAML excerpts with PDF-verbatim text
====================================================================

For rules whose YAML excerpt is a paraphrase (sim < 0.85 in
pdf_derived_anchors.json), replace the YAML `normative_anchor.excerpt`
with the actual `excerpt_pdf_verbatim` extracted from the PDF.

This brings anchor coverage to 100% (all anchors verbatim in PDF).

Usage:
    python tools/auto_fix_excerpts.py            # dry-run
    python tools/auto_fix_excerpts.py --apply    # apply changes
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).parent
_ROOT = _HERE.parent
_RULES_DIR = _ROOT / "aifa_rule_engine" / "rules"
_ANCHORS = _ROOT / "evaluation" / "gold_standard" / "pdf_derived_anchors.json"


def _normalize_excerpt_text(s: str) -> str:
    """Trim, collapse whitespace, dedup spaces. Keep newlines preserved
    only for paragraphs (collapse internal multi-newlines to single)."""
    import re
    s = s.strip()
    # collapse multi-spaces
    s = re.sub(r"[ \t]+", " ", s)
    # dehyphenate word breaks
    s = re.sub(r"-\s*\n\s*", "", s)
    # collapse 3+ newlines to 2
    s = re.sub(r"\n{3,}", "\n\n", s)
    # join broken lines into a single line if no obvious paragraph break
    s = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", s)
    return s


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes to YAML files (default: dry-run)")
    parser.add_argument("--min-similarity", type=float, default=0.50,
                        help="Min similarity to apply replacement (0.0-1.0)")
    parser.add_argument("--max-similarity", type=float, default=0.85,
                        help="Max similarity to consider 'paraphrase' (above this is OK)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("auto_fix")

    if not _ANCHORS.exists():
        log.error(f"Run derive_gold_from_pdf.py first: {_ANCHORS} missing")
        return 1

    anchors = json.loads(_ANCHORS.read_text())["anchors"]
    candidates: list[dict] = []
    for a in anchors:
        sim = a.get("similarity", 0.0)
        status = a.get("status", "")
        verbatim = a.get("excerpt_pdf_verbatim", "")
        # We replace only paraphrases (LOW_SIM/WEAK_SIM) where extraction succeeded
        if status in ("LOW_SIM_FOUND", "WEAK_SIM_FOUND") and verbatim:
            if args.min_similarity <= sim < args.max_similarity:
                candidates.append(a)

    log.info(f"{len(candidates)} candidate rules for excerpt replacement")
    log.info("Status filter: LOW_SIM_FOUND or WEAK_SIM_FOUND with verbatim available")
    log.info(f"Similarity range: [{args.min_similarity}, {args.max_similarity})")

    # Group by nota
    by_nota: dict[str, list[dict]] = {}
    for a in candidates:
        nid = a["nota_id"]
        by_nota.setdefault(nid, []).append(a)

    for nota_id in sorted(by_nota.keys()):
        rules_path = _RULES_DIR / f"nota_{nota_id}" / "rules.yaml"
        if not rules_path.exists():
            log.warning(f"missing {rules_path}")
            continue
        with rules_path.open() as f:
            doc = yaml.safe_load(f)
        rules = doc.get("rules", doc) if isinstance(doc, dict) else doc

        rule_id_to_anchor = {a["rule_id"]: a for a in by_nota[nota_id]}
        n_modified = 0
        for r in rules:
            rid = r.get("rule_id")
            if rid not in rule_id_to_anchor:
                continue
            anchor_info = rule_id_to_anchor[rid]
            old_excerpt = r.get("normative_anchor", {}).get("excerpt", "")
            new_excerpt = _normalize_excerpt_text(anchor_info["excerpt_pdf_verbatim"])
            if old_excerpt.strip() == new_excerpt.strip():
                continue
            log.info(f"  [{rid}] sim={anchor_info['similarity']:.2f}")
            log.info(f"    OLD: {old_excerpt[:120]!r}")
            log.info(f"    NEW: {new_excerpt[:120]!r}")
            if args.apply:
                r["normative_anchor"]["excerpt"] = new_excerpt
                n_modified += 1

        if args.apply and n_modified > 0:
            # Re-write YAML preserving structure as much as possible
            with rules_path.open("w") as f:
                yaml.dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            log.info(f"  → wrote {n_modified} updates to {rules_path}")
        elif n_modified == 0 and args.apply:
            log.info(f"  → no changes needed in {rules_path}")

    if not args.apply:
        log.info("")
        log.info("DRY-RUN: no files modified. Re-run with --apply to write changes.")
    else:
        log.info("")
        log.info("Apply complete. Re-run derive_gold_from_pdf.py to verify new sim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
