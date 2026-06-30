"""
M6 — Readability (Gulpease index, Italian-specific)
====================================================

Gulpease index: G = 89 + (300·F - 10·LP) / W
  where F = number of sentences (frasi)
        LP = total letters
        W = total words

Range:
  G ≥ 80 — readable for primary school
  60 ≤ G < 80 — readable for middle school
  40 ≤ G < 60 — readable for high school
  G < 40 — difficult

Output normalized to [0, 1]:
  norm = clamp((G - 30) / 60, 0, 1)
  → G=30 → 0, G=60 → 0.5, G=90 → 1.0
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from statistics import mean, median, stdev

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_EXPLANATIONS_DIR = _ROOT / "evaluation" / "results" / "pipeline_explanations"
_OUTPUT = _ROOT / "evaluation" / "results" / "readability_gulpease.json"


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_SENT_RE = re.compile(r"[.!?]+")


def _gulpease(text: str) -> tuple[float, dict]:
    """Compute Gulpease index. Returns (G, components)."""
    # Strip evidence boxes / source lists / structured fields (only narrative text)
    narrative = re.sub(r"---\s*PROVA.*?---\s*FINE\s*---", "", text, flags=re.DOTALL | re.IGNORECASE)
    narrative = re.sub(r"---\s*DATI\s*MANCANTI.*?---\s*FINE\s*DATI.*?---", "", narrative, flags=re.DOTALL | re.IGNORECASE)
    narrative = re.sub(r"^\s*5\.\s*FONTI.*", "", narrative, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
    # Remove section headers like "1. DECISIONE"
    narrative = re.sub(r"^\s*\d+\.\s+[A-ZÀ-Ÿ ]{3,}\s*$", "", narrative, flags=re.MULTILINE)

    words = _WORD_RE.findall(narrative)
    W = len(words)
    LP = sum(len(w) for w in words)
    sentences = [s.strip() for s in _SENT_RE.split(narrative) if s.strip()]
    F = len(sentences)

    if W == 0:
        return (0.0, {"F": 0, "LP": 0, "W": 0})

    G = 89 + (300 * F - 10 * LP) / W
    return (G, {"F": F, "LP": LP, "W": W})


def _normalize_gulpease(G: float) -> float:
    """Clamp to [0,1]. Linear from G=30→0 to G=90→1."""
    return max(0.0, min(1.0, (G - 30.0) / 60.0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--explanations-dir", type=Path, default=_EXPLANATIONS_DIR)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("gulpease")

    files = sorted(args.explanations_dir.glob("*.txt"))
    log.info(f"Loaded {len(files)} explanations")

    per_case: list[dict] = []
    g_values: list[float] = []
    norm_values: list[float] = []

    for f in files:
        text = f.read_text()
        G, comp = _gulpease(text)
        norm = _normalize_gulpease(G)
        per_case.append({
            "case_id": f.stem,
            "gulpease_raw": round(G, 2),
            "gulpease_norm": round(norm, 4),
            "components": comp,
            "bucket": (
                "facile" if G >= 80 else
                "scuola_media" if G >= 60 else
                "scuola_superiore" if G >= 40 else
                "difficile"
            ),
        })
        g_values.append(G)
        norm_values.append(norm)

    bucket_counts: dict[str, int] = {}
    for c in per_case:
        b = c["bucket"]
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    out = {
        "metric": "M6_readability_gulpease",
        "description": "Gulpease readability index (Italian-specific) normalized to [0,1]",
        "tautological": False,
        "n_cases_total": len(files),
        "aggregate": {
            "mean_gulpease_raw": round(mean(g_values), 2) if g_values else None,
            "median_gulpease_raw": round(median(g_values), 2) if g_values else None,
            "std_gulpease_raw": round(stdev(g_values), 2) if len(g_values) > 1 else 0.0,
            "mean_gulpease_norm": round(mean(norm_values), 4) if norm_values else None,
            "median_gulpease_norm": round(median(norm_values), 4) if norm_values else None,
            "buckets": bucket_counts,
        },
        "per_case": per_case,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(f"Gulpease mean={out['aggregate']['mean_gulpease_raw']}, norm={out['aggregate']['mean_gulpease_norm']} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
