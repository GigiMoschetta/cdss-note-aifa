"""
Aggregate NLI / similarity comparison across multiple models.

Reads:
  - evaluation/results/semantic_faithfulness_v2_<tag>.json (one per NLI model)
  - evaluation/results/semantic_similarity_italian.json (italian STSB cross-enc)

Writes:
  - evaluation/results/nli_comparison_summary.json
  - evaluation/results/nli_comparison_summary.md

The set of source files is auto-detected from a glob pattern; new model runs
just need to dump their JSON in the conventional path.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_RESULTS = _ROOT / "evaluation" / "results"


def _load_nli(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    agg = d.get("aggregate", {})
    return {
        "model": d.get("model", "?"),
        "metric": d.get("metric", "?"),
        "n_evaluated": agg.get("n_cases_evaluated", 0),
        "mean_entailment": agg.get("sf_mean_entailment"),
        "median_entailment": agg.get("sf_median_entailment"),
        "mean_contradiction": agg.get("sf_mean_contradiction"),
        "n_high_contradiction": agg.get("n_with_high_contradiction_total"),
        "source_file": path.name,
    }


def _load_ssim(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    agg = d.get("aggregate", {})
    return {
        "model": d.get("model", "?"),
        "metric": d.get("metric", "?"),
        "n_evaluated": agg.get("n_cases_evaluated", 0),
        "mean": agg.get("ssim_mean"),
        "median": agg.get("ssim_median"),
        "n_low_support": agg.get("n_low_support_total"),
        "source_file": path.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=_RESULTS)
    parser.add_argument("--output-md", type=Path, default=_RESULTS / "nli_comparison_summary.md")
    parser.add_argument("--output-json", type=Path, default=_RESULTS / "nli_comparison_summary.json")
    args = parser.parse_args()

    nli_files = sorted(args.results_dir.glob("semantic_faithfulness_v2*.json"))
    nli_entries = []
    for p in nli_files:
        # Skip pre-fix backups
        if "_pre_fix" in p.name:
            continue
        e = _load_nli(p)
        if e:
            nli_entries.append(e)

    ssim_path = args.results_dir / "semantic_similarity_italian.json"
    ssim_entry = _load_ssim(ssim_path)

    # ── JSON output ──
    out_json = {
        "nli_models": nli_entries,
        "italian_similarity": ssim_entry,
    }
    args.output_json.write_text(json.dumps(out_json, indent=2, ensure_ascii=False))

    # ── Markdown summary ──
    lines = ["# NLI / Italian-similarity model comparison", ""]
    lines.append("## NLI (entailment vs contradiction over MOTIVAZIONE sentences)")
    lines.append("")
    lines.append("| Modello | n | mean_entailment | median_entailment | mean_contradiction | n_high_contr |")
    lines.append("|---|---|---|---|---|---|")
    for e in nli_entries:
        model_short = e['model'].split('/')[-1]
        lines.append(
            f"| `{model_short}` | {e['n_evaluated']} | "
            f"{e['mean_entailment']} | {e['median_entailment']} | "
            f"{e['mean_contradiction']} | {e['n_high_contradiction']} |"
        )
    lines.append("")
    lines.append("**Higher entailment = better.  Lower contradiction = better.**")
    lines.append("")
    if ssim_entry:
        lines.append("## Italian semantic similarity (STSB cross-encoder)")
        lines.append("")
        lines.append("| Modello | n | mean (norm [0,1]) | median | n_low_support (<0.5) |")
        lines.append("|---|---|---|---|---|")
        m_short = ssim_entry['model'].split('/')[-1]
        lines.append(
            f"| `{m_short}` | {ssim_entry['n_evaluated']} | "
            f"{ssim_entry['mean']} | {ssim_entry['median']} | {ssim_entry['n_low_support']} |"
        )
        lines.append("")
        lines.append("**M3-bis NOT a replacement for NLI** — it answers a similarity question, ")
        lines.append("not an entailment question. Both signals are reported for triangulation.")

    args.output_md.write_text("\n".join(lines))
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
