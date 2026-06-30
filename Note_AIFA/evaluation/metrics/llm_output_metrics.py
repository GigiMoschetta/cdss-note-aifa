"""
Bundle of deterministic per-case LLM-output metrics:

  - claim_coverage         — gold_claims (FASE B) covered in LLM answer?
  - citation_set_metrics   — precision/recall of LLM citations vs retrieved chunks
  - decision_compliance    — aggregate of validators (decision_consistent / contradicted /
                              citation_complete / hallucination / ungrounded / justification)
  - rouge_paraphrase       — ROUGE-L F1 between LLM motivation and retrieved chunks
                              (NOT a quality metric — diagnostic for paraphrase distance)
  - sentence_support       — % LLM sentences with max-cosine ≥ 0.7 to retrieved chunks
  - decision_rationale_alignment — % blocking_rules mentioned in LLM motivation

All deterministic, no LLM judge.

Usage:
  python -m evaluation.metrics.llm_output_metrics \\
      --pipeline-report   evaluation/results/pipeline_report.json \\
      --explanations-dir  evaluation/results/pipeline_explanations \\
      --gold-dir          evaluation/gold_standard \\
      --output            evaluation/results/llm_output_metrics.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from statistics import mean


_PROJECT = Path(__file__).resolve().parent.parent.parent


# ── Text utilities ────────────────────────────────────────────────────────────

_IT_STOPWORDS = {
    "il","lo","la","i","gli","le","un","uno","una","del","della","dello","dei",
    "degli","delle","di","a","da","in","su","con","per","tra","fra","ed","e","o",
    "che","cui","non","si","se","anche","come","ma","al","allo","alla","ai","agli",
    "alle","nel","nello","nella","nei","negli","nelle","è","sono","essere","stato",
    "deve","devono","dovrà","può","possono","ha","hanno","avere","essendo",
    "questo","questa","questi","queste","ciò","ad","sul","sulla","sui","sulle",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    text = re.sub(r"[«»\"'`‘’“”„‚]", " ", text)
    text = re.sub(r"[,;:.!?()\[\]{}–—_/\\*–·•]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str, drop_stopwords: bool = True) -> list[str]:
    toks = _normalize(text).split()
    if drop_stopwords:
        toks = [t for t in toks if t not in _IT_STOPWORDS]
    return toks


def _ngrams(text: str, n: int = 3) -> list[str]:
    words = _normalize(text).split()
    if len(words) < n:
        return [_normalize(text)] if text else []
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


def _ngram_coverage(needle: str, haystack: str, n: int = 3) -> float:
    grams = _ngrams(needle, n)
    if not grams:
        return 0.0
    haystack_norm = _normalize(haystack)
    return sum(1 for g in grams if g in haystack_norm) / len(grams)


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÀÈÉÌÒÙ])", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]


def _extract_motivation(explanation: str) -> str:
    m = re.search(
        r"^\s*2\.\s*MOTIVAZIONE\s*\n(.*?)(?=^\s*\d+\.\s*[A-ZÀÈÉÌÒÙ]|\Z)",
        explanation, flags=re.MULTILINE | re.DOTALL,
    )
    return m.group(1).strip() if m else explanation


# ── Chunk text loader ─────────────────────────────────────────────────────────

from evaluation.metrics._chroma_helpers import get_chroma_collection as _get_chroma_collection  # noqa: E402


def _load_chunk_texts_by_id(case_chunks: list[dict]) -> dict[str, str]:
    by_nota: dict[str, list[str]] = {}
    for c in case_chunks:
        cid = c.get("chunk_id", "")
        if not cid:
            continue
        pdf = c.get("pdf_file", "")
        nid = "97" if "97" in pdf else "13" if "13" in pdf else "66" if "66" in pdf else "01" if "01" in pdf or "Nota_01" in pdf else None
        if nid:
            by_nota.setdefault(nid, []).append(cid)
    out: dict[str, str] = {}
    for nid, ids in by_nota.items():
        col = _get_chroma_collection(nid)
        if col is None:
            continue
        try:
            res = col.get(ids=ids, include=["documents"])
            for cid, doc in zip(res.get("ids", []), res.get("documents", []) or []):
                out[cid] = doc or ""
        except Exception as exc:
            print(f"  WARN: chunk lookup {nid}: {exc}", file=sys.stderr)
    return out


# ── Gold loader ───────────────────────────────────────────────────────────────

def _load_gold_index(gold_dir: Path) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for nota in ("01", "13", "66", "97"):
        f = gold_dir / f"nota_{nota}_cases.json"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fp:
            for c in json.load(fp).get("cases", []):
                idx[c["id"]] = c
    return idx


# ── Embedding helper for sentence support ──────────────────────────────────────

_EMB_MODEL = None


def _get_embedder():
    global _EMB_MODEL
    if _EMB_MODEL is not None:
        return _EMB_MODEL
    import os
    from sentence_transformers import SentenceTransformer
    # SBERT_DEVICE override (default cpu): the overnight runs this stage while
    # Ollama still holds ~10GB on the 12GB RTX 3060, so auto-CUDA hits
    # CUBLAS_STATUS_ALLOC_FAILED. The model is tiny (~470MB) and ~122 cases of
    # short sentences encode in <2 min on CPU, so CPU is the safe default.
    device = os.environ.get("SBERT_DEVICE", "cpu")
    _EMB_MODEL = SentenceTransformer(
        "paraphrase-multilingual-mpnet-base-v2", device=device
    )
    return _EMB_MODEL


def _cos_sim_matrix(a: list[str], b: list[str]):
    """Return matrix M[i][j] = cosine(a[i], b[j])."""
    if not a or not b:
        return [[0.0] * len(b) for _ in a]
    emb = _get_embedder()
    import numpy as np
    A = emb.encode(a, normalize_embeddings=True, show_progress_bar=False)
    B = emb.encode(b, normalize_embeddings=True, show_progress_bar=False)
    return (A @ B.T).tolist()


# ── Per-metric implementations ────────────────────────────────────────────────

def _token_containment(needle: str, haystack: str) -> float:
    """Fraction of needle's content tokens present in haystack."""
    a = set(_tokens(needle))
    b = set(_tokens(haystack))
    if not a:
        return 0.0
    return len(a & b) / len(a)


def claim_coverage(case_gold: dict, llm_text: str) -> dict:
    """For each gold_claim, check if covered in the LLM text.
    A claim is considered covered if EITHER:
      - 3-gram coverage ≥ 0.40, OR
      - token containment (excerpt content tokens in LLM) ≥ 0.60
    """
    claims = case_gold.get("gold_claims", []) or []
    if not claims:
        return {"n_claims": 0, "score": None}

    motiv = _extract_motivation(llm_text)

    per_claim = []
    must_total = 0
    must_covered = 0
    pref_total = 0
    pref_covered = 0
    for c in claims:
        cov = _ngram_coverage(c["text"], motiv, n=3)
        cont = _token_containment(c["text"], motiv + " " + llm_text)
        covered = (cov >= 0.40) or (cont >= 0.60)
        if c.get("must_appear"):
            must_total += 1
            if covered:
                must_covered += 1
        elif c.get("preferred"):
            pref_total += 1
            if covered:
                pref_covered += 1
        per_claim.append({
            "id": c.get("id"),
            "text": c["text"],
            "covered": covered,
            "coverage_3gram": round(cov, 4),
            "token_containment": round(cont, 4),
            "must_appear": bool(c.get("must_appear")),
            "preferred": bool(c.get("preferred")),
        })

    required_rate = must_covered / must_total if must_total else 1.0
    pref_rate = pref_covered / pref_total if pref_total else 0.0
    score = required_rate + 0.20 * pref_rate

    return {
        "n_claims": len(claims),
        "n_must_appear": must_total,
        "n_must_covered": must_covered,
        "n_preferred": pref_total,
        "n_preferred_covered": pref_covered,
        "required_coverage_rate": round(required_rate, 4),
        "preferred_coverage_rate": round(pref_rate, 4),
        "score": round(min(score, 1.0), 4),
        "per_claim": per_claim,
    }


_CITATION_RE = re.compile(
    r"([A-Za-z0-9_\-]+(?:\s)?\.pdf),?\s*p\.?\s*(\d+)",
    re.IGNORECASE,
)


def citation_set_metrics(case_chunks: list[dict], llm_text: str, gold: dict) -> dict:
    """Precision/recall of LLM citations vs retrieved chunks (and gold reference)."""
    cited_pairs = set()
    for m in _CITATION_RE.finditer(llm_text):
        pdf = m.group(1).strip().replace(" ", "")
        page = int(m.group(2))
        cited_pairs.add((pdf, page))

    retrieved_pairs = set()
    for c in case_chunks:
        pdf = (c.get("pdf_file") or "").strip().replace(" ", "")
        page = c.get("page")
        if pdf and page is not None:
            retrieved_pairs.add((pdf, int(page)))

    intersect = cited_pairs & retrieved_pairs
    precision = len(intersect) / len(cited_pairs) if cited_pairs else 0.0
    recall = len(intersect) / len(retrieved_pairs) if retrieved_pairs else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # Gold-citation recall: was the specific gold pdf_reference cited?
    gold_ref = gold.get("pdf_reference") or {}
    gold_pdf = (gold_ref.get("pdf_file") or "").strip().replace(" ", "")
    gold_page = gold_ref.get("page")
    gold_cited = (gold_pdf, int(gold_page)) in cited_pairs if gold_page is not None else None

    return {
        "n_llm_citations": len(cited_pairs),
        "n_retrieved_pages": len(retrieved_pairs),
        "n_overlap": len(intersect),
        "citation_precision": round(precision, 4),
        "citation_recall": round(recall, 4),
        "citation_f1": round(f1, 4),
        "gold_citation_in_llm": gold_cited,
    }


def decision_compliance(pipeline_case: dict) -> dict:
    """Aggregate the existing validator flags into a [0,1] score."""
    val = pipeline_case.get("details", {}) or {}
    decision_consistent = bool(pipeline_case.get("decision_consistent"))
    decision_contradicted = bool(val.get("decision_contradicted"))
    citation_complete = bool(pipeline_case.get("citation_complete"))
    has_hallucination = bool(pipeline_case.get("has_hallucination"))
    ungrounded = bool(val.get("ungrounded_citations"))
    justification_complete = bool(val.get("justification_complete", True))

    score = mean([
        decision_consistent,
        not decision_contradicted,
        citation_complete,
        not has_hallucination,
        not ungrounded,
        justification_complete,
    ])
    return {
        "decision_consistent": decision_consistent,
        "decision_contradicted": decision_contradicted,
        "citation_complete": citation_complete,
        "has_hallucination": has_hallucination,
        "has_ungrounded_citations": ungrounded,
        "justification_complete": justification_complete,
        "score": round(score, 4),
    }


def rouge_paraphrase(motiv: str, chunks_text: str) -> dict:
    """ROUGE-L F1 between motivation and concatenated chunks (paraphrase distance)."""
    a = _normalize(motiv).split()
    b = _normalize(chunks_text).split()
    if not a or not b:
        return {"rouge_l_f1": 0.0}

    # LCS-based ROUGE-L
    m, n = len(a), len(b)
    # cap to keep memory reasonable
    cap = 1500
    a = a[:cap]
    b = b[:cap]
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    lcs = dp[m][n]
    if lcs == 0:
        return {"rouge_l_f1": 0.0, "lcs_len": 0}
    p = lcs / m
    r = lcs / n
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "rouge_l_f1": round(f1, 4),
        "rouge_l_precision": round(p, 4),
        "rouge_l_recall": round(r, 4),
        "lcs_len": lcs,
    }


def sentence_support(motiv: str, chunk_texts: list[str]) -> dict:
    """For each LLM sentence, compute max cosine sim with any chunk (mpnet).

    Returns support rates at two thresholds (loose 0.5 and strict 0.7) plus the
    mean max-sim across sentences. Loose captures topical anchoring; strict
    captures near-paraphrase grounding.
    """
    sentences = _split_sentences(motiv)
    if not sentences or not chunk_texts:
        return {
            "n_sentences": 0,
            "support_rate": 0.0,           # backward-compat: alias for support_rate_strict
            "support_rate_strict": 0.0,
            "support_rate_loose": 0.0,
            "mean_max_sim": 0.0,
        }
    sim_matrix = _cos_sim_matrix(sentences, chunk_texts)
    max_sims = [max(row) if row else 0.0 for row in sim_matrix]
    support_strict = sum(1 for s in max_sims if s >= 0.7) / len(max_sims)
    support_loose = sum(1 for s in max_sims if s >= 0.5) / len(max_sims)
    return {
        "n_sentences": len(sentences),
        "support_rate": round(support_strict, 4),       # backward-compat alias
        "support_rate_strict": round(support_strict, 4),
        "support_rate_loose": round(support_loose, 4),
        "mean_max_sim": round(mean(max_sims), 4),
    }


def decision_rationale_alignment(motiv: str, gold: dict, rules_idx: dict[str, dict]) -> dict:
    """% of expected blocking/passed rules that are mentioned in motivation."""
    expected_rules = (
        gold.get("expected_rule_engine", {}).get("expected_blocking_rule_ids", [])
        + gold.get("expected_rule_engine", {}).get("expected_clinical_flag_rule_ids", [])
    )
    if not expected_rules:
        return {"n_rules": 0, "alignment_rate": None}

    norm_motiv = _normalize(motiv)
    mentioned = 0
    per_rule = []
    for rid in expected_rules:
        rule = rules_idx.get(rid)
        if not rule:
            continue
        anchor = rule.get("normative_anchor", {}) or {}
        keys = [
            rid.lower(),
            (rule.get("description_it") or "")[:80].lower(),
            f"{anchor.get('pdf_file','')}_{anchor.get('page','')}".lower(),
        ]
        is_mentioned = any(_ngram_coverage(k, norm_motiv) >= 0.3 for k in keys if k)
        # Also: rule's anchor page+file cited?
        page_cit = f"{anchor.get('pdf_file','')} p.{anchor.get('page','')}"
        is_mentioned = is_mentioned or (page_cit.lower() in norm_motiv)
        if is_mentioned:
            mentioned += 1
        per_rule.append({"rule_id": rid, "mentioned": is_mentioned})
    rate = mentioned / len(expected_rules)
    return {
        "n_rules": len(expected_rules),
        "n_mentioned": mentioned,
        "alignment_rate": round(rate, 4),
        "per_rule": per_rule,
    }


# ── Orchestration ─────────────────────────────────────────────────────────────

def _load_rules_index() -> dict[str, dict]:
    import yaml
    idx: dict[str, dict] = {}
    for nota in ("01", "13", "66", "97"):
        with open(_PROJECT / "aifa_rule_engine" / "rules" / f"nota_{nota}" / "rules.yaml", encoding="utf-8") as f:
            for r in yaml.safe_load(f):
                idx[r["rule_id"]] = r
    return idx


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--gold-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--skip-rouge", action="store_true", help="ROUGE-L is O(N²), skip on large texts")
    p.add_argument("--skip-sentence-support", action="store_true")
    args = p.parse_args()

    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)
    case_results = report.get("case_results", [])
    if args.limit:
        case_results = case_results[:args.limit]

    expl_dir = Path(args.explanations_dir)
    gold_idx = _load_gold_index(Path(args.gold_dir))
    rules_idx = _load_rules_index()

    per_case = []
    for cr in case_results:
        cid = cr.get("case_id", "?")
        gold = gold_idx.get(cid, {})
        expl_path = expl_dir / f"{cid}.txt"
        explanation = expl_path.read_text(encoding="utf-8") if expl_path.exists() else ""
        if not explanation:
            per_case.append({"case_id": cid, "skip_reason": "no_explanation"})
            continue

        chunks = cr.get("retrieved_chunks_metadata", []) or []
        chunk_texts_dict = _load_chunk_texts_by_id(chunks)
        chunk_texts_list = list(chunk_texts_dict.values())
        chunks_concat = " ".join(chunk_texts_list)

        motiv = _extract_motivation(explanation)

        record = {"case_id": cid}
        record["claim_coverage"] = claim_coverage(gold, explanation) if gold else {"score": None}
        record["citation_set"] = citation_set_metrics(chunks, explanation, gold)
        record["decision_compliance"] = decision_compliance(cr)
        if not args.skip_rouge:
            record["rouge_paraphrase"] = rouge_paraphrase(motiv, chunks_concat)
        if not args.skip_sentence_support:
            record["sentence_support"] = sentence_support(motiv, chunk_texts_list)
        record["decision_rationale_alignment"] = decision_rationale_alignment(motiv, gold, rules_idx) if gold else {"alignment_rate": None}

        per_case.append(record)
        sys.stderr.write(".")
        sys.stderr.flush()
    sys.stderr.write("\n")

    # Aggregate
    valid = [r for r in per_case if "skip_reason" not in r]
    aggregate = {"n_cases": len(valid)}
    if valid:
        # Helper: collect a metric across per_case for aggregation
        def _agg(extractor):
            vals = []
            for r in valid:
                v = extractor(r)
                if v is not None:
                    vals.append(v)
            return {
                "mean": round(mean(vals), 4) if vals else None,
                "median": round(sorted(vals)[len(vals)//2], 4) if vals else None,
                "n": len(vals),
            }

        aggregate["claim_coverage_score"] = _agg(lambda r: r["claim_coverage"].get("score"))
        aggregate["citation_precision"] = _agg(lambda r: r["citation_set"]["citation_precision"])
        aggregate["citation_recall"] = _agg(lambda r: r["citation_set"]["citation_recall"])
        aggregate["citation_f1"] = _agg(lambda r: r["citation_set"]["citation_f1"])
        aggregate["gold_citation_recall"] = _agg(lambda r: 1.0 if r["citation_set"].get("gold_citation_in_llm") else 0.0)
        aggregate["decision_compliance_score"] = _agg(lambda r: r["decision_compliance"]["score"])
        if not args.skip_rouge:
            aggregate["rouge_l_f1"] = _agg(lambda r: r["rouge_paraphrase"]["rouge_l_f1"])
        if not args.skip_sentence_support:
            aggregate["sentence_support_rate"] = _agg(lambda r: r["sentence_support"]["support_rate"])
            aggregate["sentence_support_rate_strict"] = _agg(lambda r: r["sentence_support"].get("support_rate_strict"))
            aggregate["sentence_support_rate_loose"] = _agg(lambda r: r["sentence_support"].get("support_rate_loose"))
            aggregate["sentence_support_mean_max_sim"] = _agg(lambda r: r["sentence_support"].get("mean_max_sim"))
        aggregate["decision_rationale_alignment"] = _agg(lambda r: r["decision_rationale_alignment"].get("alignment_rate"))

    out = {"metric": "llm_output_metrics_bundle", "aggregate": aggregate, "per_case": per_case}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"LLM Output Metrics — {len(valid)} cases")
    print("=" * 60)
    for k, v in aggregate.items():
        if isinstance(v, dict):
            print(f"  {k:40s} mean={v.get('mean')} median={v.get('median')} n={v.get('n')}")
        else:
            print(f"  {k:40s} {v}")
    print(f"\nReport: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
