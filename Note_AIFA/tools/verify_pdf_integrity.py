"""
PDF Integrity Verification Tool
================================

Verifies that all 7 AIFA PDFs in the workspace match the SHA256 checksums
declared in ../audit/pdf_checksums.json.

Usage:
    python tools/verify_pdf_integrity.py
    python tools/verify_pdf_integrity.py --strict  # exit non-zero on mismatch

Audit context: introduced as part of Day 1 fix F6-G3 BLOC (versioning PDF AIFA
assente). Allows the rule_engine to detect at startup whether the PDFs in repo
have been swapped with a different (newer/older/wrong) version, which would
silently invalidate the rules.yaml mappings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_NOTE_AIFA_DIR = _HERE.parent
_CHECKSUMS_FILE = _NOTE_AIFA_DIR.parent / "audit" / "pdf_checksums.json"


def verify(strict: bool = False) -> int:
    """Verify all PDFs against the manifest. Returns exit code (0 = OK, 1 = mismatch)."""
    if not _CHECKSUMS_FILE.exists():
        print(f"ERROR: checksum manifest not found: {_CHECKSUMS_FILE}", file=sys.stderr)
        return 2

    with open(_CHECKSUMS_FILE, encoding="utf-8") as f:
        manifest = json.load(f)

    pdf_specs: dict[str, dict] = manifest.get("pdfs", {})
    if not pdf_specs:
        print("ERROR: manifest has no PDF entries", file=sys.stderr)
        return 2

    n_ok = 0
    n_missing = 0
    n_mismatch = 0

    for filename, spec in sorted(pdf_specs.items()):
        path = _NOTE_AIFA_DIR / filename
        if not path.exists():
            print(f"  [MISSING] {filename}")
            n_missing += 1
            continue

        with open(path, "rb") as f:
            data = f.read()
        actual_sha = hashlib.sha256(data).hexdigest()
        actual_size = len(data)

        expected_sha = spec.get("sha256", "")
        expected_size = spec.get("size_bytes", 0)

        if actual_sha == expected_sha and actual_size == expected_size:
            print(f"  [OK]      {filename}  ({actual_size:>9} bytes)")
            n_ok += 1
        else:
            print(f"  [MISMATCH] {filename}")
            print(f"     expected sha256={expected_sha[:16]}... size={expected_size}")
            print(f"     actual   sha256={actual_sha[:16]}... size={actual_size}")
            n_mismatch += 1

    print(f"\nSummary: {n_ok} OK, {n_missing} missing, {n_mismatch} mismatch (total: {len(pdf_specs)})")

    if strict and (n_missing or n_mismatch):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero on any missing or mismatched PDF",
    )
    args = parser.parse_args()
    return verify(strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
