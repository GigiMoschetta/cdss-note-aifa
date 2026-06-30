"""
Boundary perturbation summary report (Fase 5.5).

Reads `evaluation/results/robustness_boundary.json` (produced by the existing
`evaluation/robustness/boundary_perturbation.py`) and generates a thesis-ready
markdown table grouped by probe family. The brief explicitly asks for
"scenari … borderline e con dati mancanti", so this report puts the borderline
behaviour (CHA2DS2-VASc=2/3, eta=74/75, VFG≈30, peso<60, ecc.) front-and-centre.

Output:
    evaluation/results/boundary_report.md  (markdown table for the thesis)
    evaluation/results/boundary_report.json (machine-readable summary)
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

log = logging.getLogger("boundary_report")
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")


def _summarize(probes: list[dict]) -> dict[str, dict[str, Any]]:
    by_family: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "pass": 0, "fail": 0, "values": []}
    )
    for p in probes:
        fam = p.get("probe_name") or "unknown"
        rec = by_family[fam]
        rec["n"] += 1
        if p.get("pass"):
            rec["pass"] += 1
        else:
            rec["fail"] += 1
        rec["values"].append(p.get("value"))
    # finalize
    out = {}
    for fam, rec in sorted(by_family.items()):
        rate = rec["pass"] / rec["n"] if rec["n"] else 0.0
        out[fam] = {
            "n_probes": rec["n"],
            "pass": rec["pass"],
            "fail": rec["fail"],
            "pass_rate": round(rate, 4),
            "values_tested": rec["values"],
        }
    return out


def _markdown(report: dict, totals: dict) -> str:
    lines: list[str] = [
        "# Boundary perturbation report",
        "",
        "Probes that target threshold values where the rule engine could plausibly "
        "flip its decision (eta=74/75, peso=60, VFG=30, creat=1.5, score=1/2/3, …).",
        "Generated from `evaluation/robustness/boundary_perturbation.py`.",
        "",
        f"**Totals:** {totals['n_probes']} probes, "
        f"pass rate **{totals['pass_rate']:.4f}** "
        f"({totals['n_pass']}/{totals['n_probes']}).",
        "",
        "| Probe family | n | pass | fail | pass rate | Values tested |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for fam, rec in report.items():
        vals = ", ".join(repr(v) for v in rec["values_tested"])
        lines.append(
            f"| `{fam}` | {rec['n_probes']} | {rec['pass']} | {rec['fail']} | "
            f"{rec['pass_rate']:.4f} | {vals} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=Path("evaluation/results/robustness_boundary.json"),
    )
    parser.add_argument(
        "--output-md", type=Path,
        default=Path("evaluation/results/boundary_report.md"),
    )
    parser.add_argument(
        "--output-json", type=Path,
        default=Path("evaluation/results/boundary_report.json"),
    )
    args = parser.parse_args()

    if not args.input.exists():
        log.error(
            "Boundary results not found: %s — run "
            "`python -m evaluation.robustness.boundary_perturbation` first.",
            args.input,
        )
        return 2

    src = json.loads(args.input.read_text(encoding="utf-8"))
    probes = src.get("probes", [])
    if not probes:
        log.error("No probes in %s", args.input)
        return 2

    by_family = _summarize(probes)
    totals = {
        "n_probes": src.get("n_probes", len(probes)),
        "n_pass": src.get("n_pass", sum(1 for p in probes if p.get("pass"))),
        "n_fail": src.get("n_fail", sum(1 for p in probes if not p.get("pass"))),
        "pass_rate": src.get("pass_rate", 0.0),
    }

    out_json = {
        "totals": totals,
        "by_probe_family": by_family,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(out_json, indent=2, ensure_ascii=False))

    md = _markdown(by_family, totals)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(md)

    log.info(
        "Boundary report: %d probes, %.2f%% pass — wrote %s + %s",
        totals["n_probes"], 100 * totals["pass_rate"],
        args.output_md, args.output_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
