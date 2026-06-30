"""
Apply HIGH-confidence excerpt fixes from audit/excerpt_fixes_proposed.json
to the actual rules.yaml files.

Only fixes with confidence >= MIN_CONF are applied automatically.
Lower-confidence fixes are listed as TODO for manual review.

Usage:
    python tools/apply_excerpt_fixes.py [--min-confidence 0.5] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml


_PROJECT = Path(__file__).resolve().parent.parent
_RULES_DIR = _PROJECT / "aifa_rule_engine" / "rules"
_AUDIT_DIR = _PROJECT.parent / "audit"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--min-confidence", type=float, default=0.5)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    with open(_AUDIT_DIR / "excerpt_fixes_proposed.json", encoding="utf-8") as f:
        data = json.load(f)
    proposals = data["proposals"]

    eligible = [p for p in proposals if p["confidence"] >= args.min_confidence and p["suggested_verbatim"].strip()]
    skipped = [p for p in proposals if p not in eligible]

    print(f"Total proposals:      {len(proposals)}")
    print(f"Eligible (conf ≥ {args.min_confidence}): {len(eligible)}")
    print(f"Skipped (low conf):   {len(skipped)}")
    print()

    if args.dry_run:
        for prop in eligible:
            print(f"[DRY-RUN] would fix `{prop['rule_id']}` (conf {prop['confidence']})")
        return 0

    # Group by file
    by_nota: dict[str, list[dict]] = {}
    for prop in eligible:
        by_nota.setdefault(prop["nota_id"], []).append(prop)

    n_applied = 0
    for nota, props in by_nota.items():
        path = _RULES_DIR / f"nota_{nota}" / "rules.yaml"
        # Backup
        backup = path.with_suffix(".yaml.bak_excerpt_fix")
        if not backup.exists():
            shutil.copy(path, backup)

        # Read raw text (preserve formatting)
        text = path.read_text(encoding="utf-8")

        for prop in props:
            rule_id = prop["rule_id"]
            new_excerpt = prop["suggested_verbatim"].strip().replace("’", "'").replace(" ", " ")
            new_page = prop["suggested_page"]
            current_excerpt = prop["current_excerpt"].strip()

            # Find the rule block in the raw text
            marker = f"rule_id: {rule_id}"
            idx = text.find(marker)
            if idx == -1:
                print(f"  [WARN] {rule_id}: marker not found in {path.name}")
                continue
            # Find the excerpt within this rule's normative_anchor block
            # Strategy: find next 'excerpt:' after marker, replace its multi-line value
            block_end = text.find("\n- rule_id:", idx + 1)
            block_end = block_end if block_end != -1 else len(text)
            block = text[idx:block_end]
            excerpt_line_start = block.find("excerpt:")
            if excerpt_line_start == -1:
                print(f"  [WARN] {rule_id}: no excerpt: line in block")
                continue
            # Replace the entire excerpt block (handles YAML folded scalars: '>-' or '|-')
            # Find the indent of the next non-empty line after 'excerpt:'
            after = block[excerpt_line_start + len("excerpt:"):]
            # The value starts after possible '>-', '|-', or inline
            # Strategy: rewrite as a single quoted string
            # Find the end of the excerpt block: next line that starts at same or lower indentation than 'excerpt:'
            excerpt_indent = len(block[:excerpt_line_start].rsplit("\n", 1)[-1])
            lines_after = after.split("\n")
            consumed = 0
            for li, line in enumerate(lines_after):
                if li == 0:
                    consumed += len(line) + 1
                    continue  # this is the rest of "excerpt: ..." line
                stripped_line_indent = len(line) - len(line.lstrip(" "))
                if line.strip() == "":
                    consumed += len(line) + 1
                    continue
                if stripped_line_indent <= excerpt_indent:
                    break
                consumed += len(line) + 1
            old_excerpt_block = after[:consumed]

            # Build replacement: single-line YAML quoted scalar (no newlines)
            indent_str = " " * excerpt_indent
            # YAML escape: replace " with \" in the new_excerpt
            escaped = new_excerpt.replace("\\", "\\\\").replace("\"", "\\\"")
            new_block = f' "{escaped}"\n'
            # Replace within the rule block
            new_text = (
                text[:idx + excerpt_line_start + len("excerpt:")]
                + new_block
                + text[idx + excerpt_line_start + len("excerpt:") + consumed:]
            )

            # Optional: page fix
            if new_page != prop["current_page"]:
                # Replace 'page: <old>' with 'page: <new>' in this block
                old_page_str = f"page: {prop['current_page']}"
                new_page_str = f"page: {new_page}"
                # Only inside the current rule block
                rule_block = new_text[idx:idx + len(block) + (len(new_block) - len(old_excerpt_block))]
                new_text = new_text.replace(rule_block, rule_block.replace(old_page_str, new_page_str, 1), 1)

            text = new_text
            n_applied += 1
            print(f"  ✓ {rule_id}: excerpt updated (conf {prop['confidence']})")

        path.write_text(text, encoding="utf-8")
        print(f"  → wrote {path}")

    print()
    print(f"Applied {n_applied} excerpt fixes.")
    print(f"Backups: aifa_rule_engine/rules/nota_*/rules.yaml.bak_excerpt_fix")

    if skipped:
        print()
        print(f"NOT applied ({len(skipped)} low-confidence — manual review needed):")
        for prop in skipped:
            print(f"  - {prop['rule_id']:30s} conf={prop['confidence']:.3f}  status={prop['audit_status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
