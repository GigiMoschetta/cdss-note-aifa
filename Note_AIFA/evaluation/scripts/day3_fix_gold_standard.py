"""
Day 3 audit fix: re-derive gold standard from PDF (not from engine).

Two operations:
1. Add the new clinician-asserted fields introduced in Day 2 fixes
   (gravidanza, emorragia, ecc.) as default False to all relevant cases.
   Without this, the new EXCL_HARD rules return UNKNOWN → NON_DETERMINABILE.
2. Correct the cases where the previous ground truth perpetuated bugs:
   - N66-024 (ketorolac): expected was RIMBORSABILE, but ketorolac is NOT in PDF
     Nota 66 lista chiusa (Day 1 fix F1-N66-Div#1 BLOC). Should be NON_RIMBORSABILE.
   - N66-025 (dexketoprofene): same.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_GOLD = _HERE.parent / "gold_standard"

# Fields introduced in Day 2 fixes — added as `False` (safe defaults)
NOTA_97_NEW_FIELDS = {
    "emorragia_maggiore_in_atto": False,
    "diatesi_emorragica_congenita": False,
    "gravidanza": False,
    "ipersensibilita_farmaco": False,
}

NOTA_66_NEW_FIELDS = {
    "abuso_alcool": False,
    "farmaci_epatotossici_concomitanti": False,
    "allergia_asa_o_fans": False,
}

# Day 2 fix F1-N13-Div#2 BLOC: N13_PATH_002 (PATHWAY fail-fast) → N13_GWARN_001 (WARNING).
# Update gold standard cases that previously expected blocking on N13_PATH_002.
GOLD_CORRECTIONS_N13 = {
    "N13-009": {
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": ["N13_GWARN_001"],
        },
        "description_suffix": " [V3.4 FIX: ex-PATHWAY N13_PATH_002 → GUIDANCE_WARN N13_GWARN_001 (Day 2 BLOC fix)]",
    },
    "N13-012": {
        "expected_rule_engine": {
            "reimbursement_decision": "RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": [],
            "expected_clinical_flag_rule_ids": [],
        },
        "description_suffix": " [V3.4 FIX: terapia_primo_livello_tentata=null no longer fail-fast (Day 2 PATHWAY→WARN refactor)]",
    },
}

# Cases where the previous ground truth perpetuated a bug (Day 1 BLOC fix F1-N66-Div#1):
# ketorolac and dexketoprofene are NOT in PDF Nota 66 lista chiusa.
GOLD_CORRECTIONS_N66 = {
    "N66-024": {
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N66_INCL_001"],
            "expected_clinical_flag_rule_ids": [],
        },
        "description_suffix": " [V3.4 FIX: ground truth corrected — ketorolac is NOT in PDF Nota 66 lista chiusa, EMA-restricted (PDF p.4 AV-12)]",
    },
    "N66-025": {
        "expected_rule_engine": {
            "reimbursement_decision": "NON_RIMBORSABILE",
            "decision_status": "FINAL",
            "missing_fields_coverage": [],
            "expected_blocking_rule_ids": ["N66_INCL_001"],
            "expected_clinical_flag_rule_ids": [],
        },
        "description_suffix": " [V3.4 FIX: ground truth corrected — dexketoprofene is NOT in PDF Nota 66 lista chiusa]",
    },
}


def _add_fields_to_case(case: dict, fields: dict[str, bool]) -> bool:
    """Add fields to case patient_data (only those missing). Returns True if modified."""
    pdata = case["input"].setdefault("patient_data", {})
    modified = False
    for field, default in fields.items():
        if field not in pdata:
            pdata[field] = default
            modified = True
    return modified


def _apply_correction(case: dict, correction: dict) -> bool:
    """Apply a ground truth correction to a case. Returns True if modified."""
    case["expected_rule_engine"] = correction["expected_rule_engine"]
    if "description_suffix" in correction:
        suffix = correction["description_suffix"]
        if suffix not in case["description"]:
            case["description"] = case["description"] + suffix
    return True


def fix_nota(nota_id: str, new_fields: dict[str, bool],
             gold_corrections: dict[str, dict] | None = None) -> tuple[int, int]:
    """Fix one nota's gold standard. Returns (n_field_added, n_corrections_applied)."""
    path = _GOLD / f"nota_{nota_id}_cases.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    n_field_added = 0
    n_corrections = 0
    for case in data["cases"]:
        if _add_fields_to_case(case, new_fields):
            n_field_added += 1
        if gold_corrections and case["id"] in gold_corrections:
            _apply_correction(case, gold_corrections[case["id"]])
            n_corrections += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return n_field_added, n_corrections


def main() -> int:
    print("Day 3 audit fix — re-derive gold standard from PDF")
    print("=" * 60)

    print("\nNota 97 — adding 4 new contraindication fields:")
    n_field, n_corr = fix_nota("97", NOTA_97_NEW_FIELDS)
    print(f"  Cases with new fields added: {n_field}")
    print(f"  Ground truth corrections applied: {n_corr}")

    print("\nNota 66 — adding 3 new contraindication fields + correcting 2 ground truth bugs:")
    n_field, n_corr = fix_nota("66", NOTA_66_NEW_FIELDS, GOLD_CORRECTIONS_N66)
    print(f"  Cases with new fields added: {n_field}")
    print(f"  Ground truth corrections applied (N66-024, N66-025): {n_corr}")

    print("\nNota 13 — applying 2 ground truth corrections (N13_PATH_002 → N13_GWARN_001):")
    n_field, n_corr = fix_nota("13", {}, GOLD_CORRECTIONS_N13)
    print(f"  Cases with new fields added: {n_field}")
    print(f"  Ground truth corrections applied (N13-009, N13-012): {n_corr}")

    print("\nNota 01: no new fields, no corrections.")

    print("\n" + "=" * 60)
    print("Done. Re-run `make eval-rule-engine` to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
