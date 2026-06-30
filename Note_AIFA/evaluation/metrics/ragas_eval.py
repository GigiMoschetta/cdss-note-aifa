"""
RAGAS evaluation against the gold standard.

Computes 6 RAGAS metrics over every gold case for which we have a saved
LLM explanation (`evaluation/results/pipeline_explanations/{case_id}.txt`):

    - faithfulness         : claims in the answer that can be inferred from
                              the retrieved contexts (NLI by judge LLM).
    - answer_relevancy     : is the answer pertinent to the question?
    - context_precision    : are top-ranked contexts the relevant ones?
    - context_recall       : do retrieved contexts cover the ground truth?
    - answer_similarity    : embedding similarity answer ↔ ground truth.
    - answer_correctness   : combined factual + similarity score.

Backend (offline, no API key):
    - Judge LLM        : Ollama llama3.1:8b (same model as the orchestrator)
    - Embeddings       : sentence-transformers/paraphrase-multilingual-mpnet-base-v2
                          (same as ingest.py — keeps embedding space coherent)

For each case we build the RAGAS sample as:

    user_input        — synthesized question, e.g. "Il farmaco apixaban è
                        rimborsabile dal SSN secondo la Nota AIFA 97 per
                        il paziente fornito? Quali criteri normativi
                        determinano la decisione e quali fonti la giustificano?"
    response          — full LLM `generated_explanation` (5 sezioni)
    retrieved_contexts— text of the chunks retrieved by the orchestrator,
                        looked up from ChromaDB by chunk_id
    reference         — gold pdf_reference.excerpt (verbatim from PDF)

Outputs:
    JSON with per-case scores + aggregate (mean & median per metric).

Usage:
    python -m evaluation.metrics.ragas_eval \\
        --pipeline-report evaluation/results/pipeline_report.json \\
        --explanations-dir evaluation/results/pipeline_explanations \\
        --gold-dir evaluation/gold_standard \\
        --output evaluation/results/ragas_report.json \\
        [--limit 10]                # smoke test on first N cases
        [--metrics faithfulness,answer_correctness]   # subset
        [--ollama-model llama3.1:8b]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, median


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_chunk_texts(case_chunks: list[dict]) -> list[str]:
    """Look up chunk texts from ChromaDB by chunk_id, preserving rank order.

    Honours CHROMA_COLLECTION_SUFFIX env var (audit fix 2026-05-04 P0.1).
    """
    # Lazy import so module can be imported even when chromadb is unavailable
    try:
        from evaluation.metrics._chroma_helpers import get_chroma_collection
    except ImportError as e:
        print(f"chroma helpers not available: {e}", file=sys.stderr)
        return []

    by_nota: dict[str, list[tuple[int, str]]] = {}
    for rank, c in enumerate(case_chunks):
        cid = c.get("chunk_id", "")
        if not cid:
            continue
        pdf = c.get("pdf_file", "")
        if "97" in pdf:
            nid = "97"
        elif "13" in pdf:
            nid = "13"
        elif "66" in pdf:
            nid = "66"
        elif "01" in pdf or "Nota_01" in pdf:
            nid = "01"
        else:
            continue
        by_nota.setdefault(nid, []).append((rank, cid))

    rank_to_text: dict[int, str] = {}
    for nid, items in by_nota.items():
        col = get_chroma_collection(nid)
        if col is None:
            continue
        try:
            ids = [cid for _, cid in items]
            res = col.get(ids=ids, include=["documents"])
            id_to_doc = dict(zip(res.get("ids", []), res.get("documents", []) or []))
            for rank, cid in items:
                rank_to_text[rank] = id_to_doc.get(cid, "") or ""
        except Exception as exc:
            print(f"  WARN: chunk lookup failed for nota_{nid}: {exc}", file=sys.stderr)

    return [rank_to_text[r] for r in sorted(rank_to_text)]


def _synthesize_question(case: dict) -> str:
    inp = case.get("input", {})
    drug = inp.get("drug_id", "il farmaco")
    nota = inp.get("nota_id", "?")
    return (
        f"Il farmaco {drug} è rimborsabile dal SSN secondo la Nota AIFA {nota} "
        f"per il paziente descritto? Quali criteri normativi determinano la decisione "
        f"e quali fonti del PDF la giustificano?"
    )


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--gold-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int, default=None, help="evaluate only first N cases")
    p.add_argument(
        "--case-ids",
        default=None,
        help="comma-separated case_id list (overrides --limit). Useful for stratified subsets.",
    )
    p.add_argument(
        "--metrics",
        default="faithfulness,answer_relevancy,context_precision,context_recall,"
                "answer_similarity,answer_correctness",
        help="comma-separated subset of: "
             "faithfulness,answer_relevancy,context_precision,context_recall,"
             "answer_similarity,answer_correctness",
    )
    p.add_argument("--ollama-model", default=os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    p.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    p.add_argument(
        "--embed-model",
        default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    )
    args = p.parse_args()

    # Lazy imports (heavy)
    from datasets import Dataset
    from langchain_ollama import ChatOllama, OllamaEmbeddings  # noqa: F401
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas import evaluate, RunConfig
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        Faithfulness,
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        AnswerSimilarity,
        AnswerCorrectness,
    )

    metric_map = {
        "faithfulness": Faithfulness,
        "answer_relevancy": AnswerRelevancy,
        "context_precision": ContextPrecision,
        "context_recall": ContextRecall,
        "answer_similarity": AnswerSimilarity,
        "answer_correctness": AnswerCorrectness,
    }
    selected = [m.strip() for m in args.metrics.split(",") if m.strip()]
    metrics_objs = [metric_map[m]() for m in selected if m in metric_map]
    if not metrics_objs:
        print(f"ERROR: no valid metrics in {selected}", file=sys.stderr)
        return 1

    # Build dataset
    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)
    case_results = report.get("case_results", [])
    gold_idx = _load_gold_index(Path(args.gold_dir))
    expl_dir = Path(args.explanations_dir)

    samples: list[dict] = []
    case_ids: list[str] = []
    skipped_no_expl = 0
    skipped_no_gold = 0
    skipped_no_chunks = 0

    requested_ids: set[str] | None = None
    if args.case_ids:
        requested_ids = {x.strip() for x in args.case_ids.split(",") if x.strip()}

    for cr in case_results:
        cid = cr["case_id"]
        if requested_ids is not None and cid not in requested_ids:
            continue
        gold = gold_idx.get(cid)
        if gold is None:
            skipped_no_gold += 1
            continue
        expl_file = expl_dir / f"{cid}.txt"
        if not expl_file.exists():
            skipped_no_expl += 1
            continue
        explanation = expl_file.read_text(encoding="utf-8").strip()
        if not explanation:
            skipped_no_expl += 1
            continue
        contexts = _load_chunk_texts(cr.get("retrieved_chunks_metadata", []))
        if not contexts:
            skipped_no_chunks += 1
            continue
        # Prefer the FASE B gold_answer (longer, semantically closer to LLM output)
        # and fall back to pdf_reference.excerpt if gold_answer is missing.
        gold_answer = (gold.get("gold_answer") or "").strip()
        excerpt = gold_answer or (gold.get("pdf_reference", {}) or {}).get("excerpt", "").strip()
        if not excerpt:
            excerpt = (
                gold.get("description", "")
                or "Il sistema deve indicare la decisione corretta motivandola con le fonti AIFA."
            )

        samples.append(
            {
                "user_input": _synthesize_question(gold),
                "response": explanation,
                "retrieved_contexts": contexts,
                "reference": excerpt,
            }
        )
        case_ids.append(cid)

        if args.limit and len(samples) >= args.limit:
            break

    if not samples:
        print(
            f"ERROR: 0 evaluable cases (skipped: no_gold={skipped_no_gold} "
            f"no_expl={skipped_no_expl} no_chunks={skipped_no_chunks})",
            file=sys.stderr,
        )
        return 1

    print(
        f"Evaluating {len(samples)} cases  "
        f"(skipped: no_gold={skipped_no_gold}, no_expl={skipped_no_expl}, no_chunks={skipped_no_chunks})"
    )

    # Build wrappers
    judge_llm = ChatOllama(
        model=args.ollama_model,
        base_url=args.ollama_base_url,
        temperature=0.0,
        num_ctx=8192,
    )
    embeddings = HuggingFaceEmbeddings(
        model_name=args.embed_model,
        model_kwargs={"device": os.getenv("RAGAS_EMBED_DEVICE", "cpu")},
    )
    ragas_llm = LangchainLLMWrapper(judge_llm)
    ragas_emb = LangchainEmbeddingsWrapper(embeddings)

    # Inject backends into metrics that need them
    for m in metrics_objs:
        if hasattr(m, "llm"):
            m.llm = ragas_llm
        if hasattr(m, "embeddings"):
            m.embeddings = ragas_emb

    ds = Dataset.from_list(samples)

    # Italianize prompts — adapt + cache to disk for reproducibility.
    # RAGAS 0.4.x API:
    #   m.adapt_prompts(language=..., llm=...)  → coroutine returning dict[name, Prompt]
    #   m.set_prompts(**adapted_prompts)         → install translated prompts on the metric
    #   m.save_prompts(path)                     → persist to disk
    #   m.load_prompts(path)                     → re-load from disk
    import asyncio
    cache_dir = _PROJECT_ROOT / "evaluation" / "metrics" / "ragas_prompts_it_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for m in metrics_objs:
        try:
            cache_path = cache_dir / m.__class__.__name__.lower()
            italian_marker_files = [
                f for f in (cache_path.iterdir() if cache_path.exists() else [])
                if "italian" in f.name.lower()
            ]
            if italian_marker_files:
                m.load_prompts(str(cache_path), language="italian")
                print(f"  [cache] loaded IT prompts for {m.__class__.__name__}")
            else:
                print(f"  [adapt] translating prompts to IT for {m.__class__.__name__}…")
                adapted = asyncio.run(m.adapt_prompts(language="italian", llm=ragas_llm))
                if adapted:
                    m.set_prompts(**adapted)
                cache_path.mkdir(parents=True, exist_ok=True)
                m.save_prompts(str(cache_path))
                print(f"  [cache] saved IT prompts → {cache_path}")
        except Exception as exc:
            print(f"  [warn] adapt_prompts skipped for {m.__class__.__name__}: {exc}")

    print(f"Running RAGAS metrics: {', '.join(selected)}  (judge: {args.ollama_model})")
    t0 = time.monotonic()
    # 2026-05-13 overnight fix: Llama 3.1 8B parser failure rate is high on the
    # post-RAG-fix explanations (longer answers → more out-of-format outputs).
    # max_retries=5 multiplies failure cost 5x and pushes total wall_time from
    # historical 11h to projected 26h. Reduced to max_retries=1 (failure becomes
    # NaN quickly, in line with raise_exceptions=False) and max_workers=2 to use
    # GPU at ~50% load (single Ollama instance handles 2 concurrent reqs well).
    run_config = RunConfig(timeout=900, max_retries=1, max_workers=2)
    result = evaluate(
        dataset=ds,
        metrics=metrics_objs,
        llm=ragas_llm,
        embeddings=ragas_emb,
        raise_exceptions=False,
        run_config=run_config,
        show_progress=True,
    )
    elapsed = time.monotonic() - t0
    print(f"\nRAGAS evaluation finished in {elapsed:.1f}s")

    df = result.to_pandas()
    metric_columns = [c for c in df.columns if c in selected]

    per_case: list[dict] = []
    for i, cid in enumerate(case_ids):
        row = df.iloc[i]
        scores = {c: (None if row[c] is None or (isinstance(row[c], float) and (row[c] != row[c])) else float(row[c])) for c in metric_columns}
        per_case.append({"case_id": cid, **scores})

    aggregate = {}
    for c in metric_columns:
        vals = [r[c] for r in per_case if r[c] is not None]
        if not vals:
            aggregate[c] = {"mean": None, "median": None, "n": 0}
            continue
        aggregate[c] = {
            "mean": round(mean(vals), 4),
            "median": round(median(vals), 4),
            "n": len(vals),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }

    out = {
        "metric": "ragas",
        "judge_llm": args.ollama_model,
        "embed_model": args.embed_model,
        "n_cases": len(per_case),
        "wall_time_s": round(elapsed, 1),
        "aggregate": aggregate,
        "per_case": per_case,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"RAGAS — {len(per_case)} cases | judge: {args.ollama_model}")
    print(f"{'=' * 60}")
    for c, agg in aggregate.items():
        if agg["n"] == 0:
            print(f"  {c:25s} (no scores)")
            continue
        print(
            f"  {c:25s} mean={agg['mean']:.4f}  median={agg['median']:.4f}  "
            f"min={agg.get('min'):.4f}  max={agg.get('max'):.4f}  n={agg['n']}"
        )
    print(f"\nReport written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
