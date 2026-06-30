"""
M4 — Explanation Uniqueness (EU)
=================================

Measures whether the LLM produces case-specific explanations or generic text
reused across many cases.

  - exact_duplicate_rate: % of explanations that share an exact bytewise hash
                          with at least one other explanation
  - mean_pairwise_jaccard: mean Jaccard similarity of token sets across all
                          (i,j) pairs of explanations
  - mean_pairwise_cosine_tfidf: mean TF-IDF cosine similarity (semantic-ish)

EU = (1 - exact_duplicate_rate) * (1 - mean_pairwise_cosine_tfidf)

A higher EU means more case-specific output. Range [0, 1].

This is NON-tautological and complements existing metrics: it directly
measures whether the LLM adds case-specific value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from statistics import mean

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_PIPELINE_REPORT = _ROOT / "evaluation" / "results" / "pipeline_report.json"
_EXPLANATIONS_DIR = _ROOT / "evaluation" / "results" / "pipeline_explanations"
_OUTPUT = _ROOT / "evaluation" / "results" / "explanation_uniqueness.json"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[\w']+\b", text.lower()))


def _normalize_text(text: str) -> str:
    """Strip volatile fields (timestamps, latencies) before hashing."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--explanations-dir", type=Path, default=_EXPLANATIONS_DIR)
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("eu")

    if not args.explanations_dir.exists():
        log.error(f"Explanations dir missing: {args.explanations_dir}")
        return 1

    files = sorted(args.explanations_dir.glob("*.txt"))
    log.info(f"Loaded {len(files)} explanations")

    case_data: list[dict] = []
    for f in files:
        text = f.read_text()
        norm = _normalize_text(text)
        sha = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        toks = _tokenize(norm)
        case_data.append({
            "case_id": f.stem,
            "sha256": sha,
            "tokens": toks,
            "char_count": len(text),
        })

    # Exact duplicate detection
    sha_to_cases: dict[str, list[str]] = {}
    for c in case_data:
        sha_to_cases.setdefault(c["sha256"], []).append(c["case_id"])
    duplicate_groups = {sha: cases for sha, cases in sha_to_cases.items() if len(cases) > 1}
    cases_in_dup = sum(len(g) for g in duplicate_groups.values())
    exact_dup_rate = cases_in_dup / len(case_data) if case_data else 0.0

    # Pairwise Jaccard (subsample if too many cases)
    n = len(case_data)
    jaccard_sum = 0.0
    pairs_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            ti, tj = case_data[i]["tokens"], case_data[j]["tokens"]
            if not ti and not tj:
                continue
            j_score = len(ti & tj) / len(ti | tj) if (ti | tj) else 0.0
            jaccard_sum += j_score
            pairs_count += 1
    mean_jaccard = jaccard_sum / pairs_count if pairs_count else 0.0

    # TF-IDF cosine (sklearn is heavy, so simple variant: just within-corpus IDF)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        texts = [_normalize_text(open(f).read()) for f in files]
        vec = TfidfVectorizer(token_pattern=r"\b[\w']+\b", lowercase=True)
        mat = vec.fit_transform(texts)
        sim = cosine_similarity(mat)
        # Mean of upper triangle (excluding diagonal)
        import numpy as np
        iu = np.triu_indices_from(sim, k=1)
        mean_cosine = float(sim[iu].mean()) if len(iu[0]) > 0 else 0.0
    except ImportError:
        mean_cosine = mean_jaccard  # fallback proxy
        log.warning("sklearn not available, using Jaccard as cosine proxy")

    eu_score = (1.0 - exact_dup_rate) * (1.0 - mean_cosine)

    out = {
        "metric": "M4_explanation_uniqueness",
        "description": "Case-specific quality of LLM output: 1 - duplicate_rate × 1 - mean_pairwise_cosine_TFIDF",
        "tautological": False,
        "n_cases_total": len(case_data),
        "aggregate": {
            "exact_duplicate_rate": round(exact_dup_rate, 4),
            "n_unique_hashes": len(sha_to_cases),
            "n_duplicate_groups": len(duplicate_groups),
            "n_cases_in_duplicate_groups": cases_in_dup,
            "mean_pairwise_jaccard": round(mean_jaccard, 4),
            "mean_pairwise_cosine_tfidf": round(mean_cosine, 4),
            "eu_score": round(eu_score, 4),
        },
        "duplicate_groups": [
            {"sha256": sha, "cases": cases, "n": len(cases)}
            for sha, cases in sorted(duplicate_groups.items(), key=lambda kv: -len(kv[1]))
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log.info(
        f"EU score={eu_score:.4f}, dup_rate={exact_dup_rate:.4f}, "
        f"mean_cosine={mean_cosine:.4f}, n_dup_groups={len(duplicate_groups)} → {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
