"""
Congela gli output /evaluate del rule engine per tutti i 122 casi gold in un
JSON statico (webapp/src/data/evaluations.json), così la web app renderizza
verdetto + citazioni verbatim SENZA backend acceso (lavoro front/UI/UX offline).

Richiede il rule engine attivo su :8000 al momento del bake.
Rilanciare solo se cambiano regole o gold case.

    python3 demo/bake_evaluations.py
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import data_loader as dl

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent / "webapp" / "src" / "data" / "evaluations.json"
_ENGINE = "http://localhost:8000/evaluate"


def _post(body: dict) -> dict:
    req = urllib.request.Request(
        _ENGINE,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    cases = dl.load_gold_cases()
    out: dict[str, dict] = {}
    errors = 0
    for c in cases:
        body = {
            "schema_version": "3.3",
            "note_id": c["nota_id"],
            "drug_id": c["drug_id"],
            "patient_data": c["patient_data"],
            "clinician_asserted": c["clinician_asserted"],
        }
        try:
            out[c["case_id"]] = _post(body)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  ! {c['case_id']}: {exc}")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baked {len(out)}/{len(cases)} evaluations ({errors} errori) -> {_OUT}")


if __name__ == "__main__":
    main()
