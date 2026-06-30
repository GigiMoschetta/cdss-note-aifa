"""
regenerate_expected_outputs_v2.py
==================================

Generates expected_outputs_v2 with PDF-derived gold excerpts attached to each
activated rule. The excerpt_pdf_verbatim comes from
evaluation/gold_standard/pdf_derived_anchors.json (output of derive_gold_from_pdf.py).

Usage:
    python evaluation/scripts/regenerate_expected_outputs_v2.py

Output:
    evaluation/gold_standard/nota_{01,13,66,97}_expected_outputs_v2.json

Each case has:
    - case_id, description, input, actual_result   (as before)
    - pdf_gold:
        blocking_rules_with_pdf_anchor: [
            {rule_id, pdf_file, page, char_start, char_end, line_start, line_end,
             bbox, excerpt_pdf_verbatim, sha256_chunk, anchor_status}
        ]
        passed_rules_with_pdf_anchor: [...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Audit fix V3-H6 (2026-05-06): import ENGINE_VERSION from the single source of
# truth instead of hardcoding "3.4.0". Pre-fix the literal would silently diverge
# from the engine on every version bump.
from aifa_rule_engine import ENGINE_VERSION

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent  # Note_AIFA/
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RULES_DIR = _ROOT / "aifa_rule_engine" / "rules"


def _load_anchors(path: Path) -> dict[str, dict]:
    d = json.loads(path.read_text())
    return {a["rule_id"]: a for a in d["anchors"]}


def _attach_pdf_gold(rule_payload: list, anchors: dict[str, dict]) -> list:
    """For each rule in payload, attach pdf_gold info if available."""
    augmented: list = []
    for r in rule_payload:
        rule_id = r.get("rule_id") if isinstance(r, dict) else None
        pdf_anchor = anchors.get(rule_id) if rule_id else None
        if pdf_anchor:
            augmented.append({
                "rule_id": rule_id,
                "rule_type": r.get("rule_type"),
                "description_it": pdf_anchor["description_it"],
                "pdf_file": pdf_anchor["pdf_file"],
                "page": pdf_anchor["page"],
                "char_start": pdf_anchor["char_start"],
                "char_end": pdf_anchor["char_end"],
                "line_start": pdf_anchor["line_start"],
                "line_end": pdf_anchor["line_end"],
                "bbox": pdf_anchor["bbox"],
                "excerpt_pdf_verbatim": pdf_anchor["excerpt_pdf_verbatim"],
                "anchor_status": pdf_anchor["status"],
                "anchor_similarity": pdf_anchor["similarity"],
                "excerpt_sha256": pdf_anchor["excerpt_sha256"],
            })
        else:
            augmented.append({
                "rule_id": rule_id,
                "anchor_status": "NO_ANCHOR_AVAILABLE",
            })
    return augmented


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchors", type=Path,
                        default=_GOLD_DIR / "pdf_derived_anchors.json")
    parser.add_argument("--gold-dir", type=Path, default=_GOLD_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    logger = logging.getLogger("regen_v2")

    if not args.anchors.exists():
        logger.error(f"Anchor file missing: {args.anchors}")
        logger.error("Run tools/derive_gold_from_pdf.py first.")
        return 1

    anchors = _load_anchors(args.anchors)
    logger.info(f"Loaded {len(anchors)} PDF-derived anchors")

    # Load rule engine
    sys.path.insert(0, str(_ROOT))
    from aifa_rule_engine.engine.rule_loader import load_rules
    from aifa_rule_engine.engine.evaluator import evaluate
    rule_index = load_rules(_RULES_DIR)
    logger.info(f"Loaded {len(rule_index.rules)} rules")

    for nota_id in ["01", "13", "66", "97"]:
        cases_path = args.gold_dir / f"nota_{nota_id}_cases.json"
        if not cases_path.exists():
            logger.warning(f"missing {cases_path}")
            continue

        cases_data = json.loads(cases_path.read_text())
        cases = cases_data.get("cases", cases_data) if isinstance(cases_data, dict) else cases_data

        outputs: list[dict[str, Any]] = []
        n_with_anchor = 0

        for case in cases:
            case_id = case.get("case_id") or case.get("id") or "?"
            inp = case.get("input", {})
            try:
                # Run rule engine (this is the safety-decision oracle, kept as-is)
                result = evaluate(
                    nota_id=inp.get("nota_id", nota_id),
                    drug_id=inp.get("drug_id", ""),
                    patient_data=inp.get("patient_data", {}),
                    clinician_asserted=inp.get("clinician_asserted", {}),
                    rule_index=rule_index,
                )
                actual = result.model_dump() if hasattr(result, "model_dump") else result
            except Exception as e:
                logger.error(f"  {case_id}: rule engine failed: {e}")
                outputs.append({
                    "case_id": case_id,
                    "description": case.get("description", ""),
                    "input": inp,
                    "error": str(e),
                })
                continue

            rag = actual.get("rag_payload", {})
            blocking = rag.get("blocking_rules", [])
            passed = rag.get("passed_rules", [])

            # Attach PDF-derived anchor info
            blocking_with_pdf = _attach_pdf_gold(blocking, anchors)
            passed_with_pdf = _attach_pdf_gold(passed, anchors)
            if any(b.get("excerpt_pdf_verbatim") for b in blocking_with_pdf):
                n_with_anchor += 1

            outputs.append({
                "case_id": case_id,
                "description": case.get("description", ""),
                "input": inp,
                "actual_result": actual,
                "pdf_gold": {
                    "blocking_rules_with_pdf_anchor": blocking_with_pdf,
                    "passed_rules_with_pdf_anchor": passed_with_pdf,
                },
            })

        out = {
            "schema_version": "v2",
            "nota_id": nota_id,
            "engine_version": ENGINE_VERSION,
            "total_cases": len(outputs),
            "n_cases_with_pdf_anchored_blocking": n_with_anchor,
            "errors": [o for o in outputs if "error" in o],
            "outputs": outputs,
        }
        out_path = args.gold_dir / f"nota_{nota_id}_expected_outputs_v2.json"
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        logger.info(
            f"  nota_{nota_id}: {len(outputs)} cases "
            f"({n_with_anchor} with PDF-anchored blocking) → {out_path}"
        )

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
