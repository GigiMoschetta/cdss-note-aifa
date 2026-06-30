"""
Esporta i 122 casi gold arricchiti + cataloghi (regole, flag clinici) in un
JSON statico consumato dalla web app React (webapp/src/data/cases.json).

Riusa data_loader.py (logica canonica di caricamento/arricchimento). Va
rilanciato solo se cambiano i gold case o le regole YAML.

    python3 demo/export_cases.py
"""
from __future__ import annotations

import json
from pathlib import Path

import data_loader as dl

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent / "webapp" / "src" / "data" / "cases.json"


def _classify(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def build_flag_catalog(cases: list[dict]) -> dict[str, dict]:
    """Mappa key -> {label, icon, severity, kind, unit} per ogni campo clinico
    presente nei patient_data, così la UI sa come etichettare i toggle/what-if."""
    catalog: dict[str, dict] = {}
    numeric = dl._NUMERIC_LABELS  # {key: (label, unit)}
    for c in cases:
        for k, v in c["patient_data"].items():
            if k in catalog:
                continue
            kind = _classify(v)
            if kind == "number" and k in numeric:
                lbl, unit = numeric[k]
                catalog[k] = {"label": lbl, "icon": "🔢", "severity": "info",
                              "kind": "number", "unit": unit}
            else:
                label, icon, sev = dl._meta_for_flag(k)
                catalog[k] = {"label": label, "icon": icon, "severity": sev,
                              "kind": kind, "unit": ""}
    return catalog


def build_rule_catalog() -> dict[str, dict]:
    raw = dl.load_rule_catalog()
    return {
        rid: {
            "description_it": r.get("description_it", ""),
            "rule_type": r.get("rule_type", ""),
        }
        for rid, r in raw.items()
    }


def main() -> None:
    cases = dl.load_gold_cases()
    payload = {
        "generated_from": "data_loader.load_gold_cases()",
        "n_cases": len(cases),
        "highlight_case_ids": dl.HIGHLIGHT_CASES,
        "cases": [
            {
                "case_id": c["case_id"],
                "nota_id": c["nota_id"],
                "drug_id": c["drug_id"],
                "drug_class_label": c["drug_class_label"],
                "drug_icon": c["drug_icon"],
                "drug_severity": c["drug_severity"],
                "category_human": c["category_human"],
                "description": c["description"],
                "complexity": c["complexity"],
                "expected_decision": c["expected_decision"],
                "expected_status": c["expected_status"],
                "expected_route_to": c["expected_route_to"],
                "patient": {
                    "full_name": c["full_name"],
                    "first_name": c["first_name"],
                    "last_name": c["last_name"],
                    "initials": c["initials"],
                    "avatar_url": c["avatar_url"],
                    "sex": c["patient_sex"],
                    "age": c["patient_age"],
                    **c["vanity"],
                },
                "patient_data": c["patient_data"],
                "clinician_asserted": c["clinician_asserted"],
            }
            for c in cases
        ],
        "flag_catalog": build_flag_catalog(cases),
        "rule_catalog": build_rule_catalog(),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} cases + {len(payload['flag_catalog'])} flags + "
          f"{len(payload['rule_catalog'])} rules -> {_OUT}")


if __name__ == "__main__":
    main()
