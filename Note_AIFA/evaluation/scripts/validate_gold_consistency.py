"""
Gold standard consistency validator (audit P0.10).

Detects desc/expected/category mismatches in gold cases. Fails CI if any case
has a `description` that contradicts `expected_rule_engine.reimbursement_decision`.

Heuristic: leading token of description (RIMBORSABILE | NON_RIMBORSABILE |
NON_DETERMINABILE | RIMBORSABILE_bypass | RIMBORSABILE_with_warning) must agree
with the expected decision. Cases where the description does NOT start with one
of these tokens are skipped (not enforceable).

Exit code: 0 if all consistent, 1 if any mismatch found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parent.parent / "gold_standard"

# Map description prefix → expected decision
_PREFIX_MAP = {
    "RIMBORSABILE_bypass": "RIMBORSABILE",
    "RIMBORSABILE_with_warning": "RIMBORSABILE",
    "RIMBORSABILE": "RIMBORSABILE",
    "NON_RIMBORSABILE": "NON_RIMBORSABILE",
    "NON_DETERMINABILE": "NON_DETERMINABILE",
}


def _expected_from_description(desc: str) -> str | None:
    desc = desc.strip()
    # Order matters — longer prefixes first.
    for prefix in sorted(_PREFIX_MAP, key=len, reverse=True):
        if desc.startswith(prefix):
            return _PREFIX_MAP[prefix]
    return None


def main() -> int:
    mismatches: list[str] = []
    n_checked = 0
    n_skipped = 0

    for nota in ("01", "13", "66", "97"):
        path = _GOLD_DIR / f"nota_{nota}_cases.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data.get("cases", []):
            cid = c["id"]
            desc = c.get("description", "")
            expected = c.get("expected_rule_engine", {}).get("reimbursement_decision")
            inferred = _expected_from_description(desc)
            if inferred is None:
                n_skipped += 1
                continue
            n_checked += 1
            if inferred != expected:
                mismatches.append(
                    f"  {cid}: description prefix='{inferred}' but "
                    f"expected_rule_engine.reimbursement_decision='{expected}'\n"
                    f"     description: {desc[:140]}"
                )

    print(f"Gold consistency check: {n_checked} cases verified, {n_skipped} skipped (no recognised prefix)")

    if mismatches:
        print(f"\n[FAIL] {len(mismatches)} mismatch(es) detected:", file=sys.stderr)
        for m in mismatches:
            print(m, file=sys.stderr)
        return 1
    print("[PASS] All gold cases consistent (description prefix == expected decision)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
