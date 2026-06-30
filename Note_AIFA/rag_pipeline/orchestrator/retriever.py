"""
Phase 2 — Two-Stage ChromaDB Retriever
=======================================

Stage A — Anchor-guided (deterministic, 100% precision by construction):
    For each blocking_rule and passed_rule in RagPayload, retrieve the chunk(s)
    that match {pdf_file, page} exactly using ChromaDB metadata filters.
    These are the exact regulatory passages that determined the decision.

Stage B — Semantic (contextual enrichment):
    Query the nota-specific collection using clinical_context_summary as the
    query string. Retrieves k=5 semantically similar chunks. Results are
    deduplicated against Stage A.

Integration contract:
    - Collection naming must match ingest.py: f"nota_{nota_id}"
    - Metadata keys must match ingest.py: {pdf_file, page, section, nota_id, ...}
    - NormativeAnchor.pdf_file must equal chunk metadata["pdf_file"]
      (both use the normalized filename without trailing spaces)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from aifa_rule_engine.models.results import EvaluationResult  # type: ignore[attr-defined]

from .schemas import RetrievedChunk

log = logging.getLogger(__name__)

# Default ChromaDB path — overridden by CHROMA_DB_DIR env var
_DEFAULT_DB_DIR = Path(__file__).parent.parent / "chroma_db"
_DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# Pinned HuggingFace commit hashes (audit Day 1 fix F6-4):
# the embedding/reranker model weights served by HF Hub can change over time.
# Pinning the exact revision guarantees reproducibility — if the user re-runs
# `make ingest` years from now, the embeddings (and therefore ChromaDB index
# and retrieval results) are bit-identical to the ones used to evaluate the
# thesis. Override via env vars EMBEDDING_REVISION / RERANKER_REVISION.
_DEFAULT_EMBEDDING_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
_DEFAULT_RERANKER_REVISION  = "c5ee24cb16019beea0893ab7796b1df96625c6b8"

# Stage B retrieval parameters
_SEMANTIC_K = 5          # final top-n after reranking
_SEMANTIC_FETCH_K = 15   # over-fetch multiplier for reranker candidates


def _meta_to_chunk(chunk_id: str, doc: str, meta: dict, stage: str, score: float) -> RetrievedChunk:
    """Build a RetrievedChunk from ChromaDB metadata (handles both v1 and v2 schemas)."""
    bbox = [
        float(meta.get("bbox_x0", 0.0)),
        float(meta.get("bbox_y0", 0.0)),
        float(meta.get("bbox_x1", 0.0)),
        float(meta.get("bbox_y1", 0.0)),
    ]
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=doc,
        pdf_file=meta.get("pdf_file", ""),
        nota_id=meta.get("nota_id", ""),
        page=int(meta.get("page", 0)),
        page_end=int(meta.get("page_end", meta.get("page", 0))),
        section=meta.get("section", ""),
        score=score,
        retrieval_stage=stage,
        char_start=int(meta.get("char_start", 0)),
        char_end=int(meta.get("char_end", 0)),
        line_start=int(meta.get("line_start", 0)),
        line_end=int(meta.get("line_end", 0)),
        bbox=bbox,
        sha256=meta.get("sha256", ""),
        is_in_table=bool(meta.get("is_in_table", False)),
        table_id=meta.get("table_id", ""),
        schema_version=meta.get("schema_version", "v1"),
    )

# Cross-encoder reranker model — overridable via RERANKER_MODEL env var
# Bug fix ARCH-2 (audit): previously used 'ms-marco-MiniLM-L-6-v2' which is
# trained on MS-MARCO English query-passage pairs. For Italian normative text
# this is a domain mismatch (the embedder is multilingual but the reranker
# projects italian text to an English-trained space).
# Replaced with 'nickprock/cross-encoder-italian-bert-stsb' — Italian-specific
# cross-encoder fine-tuned on Italian STSB. Verified to discriminate correctly
# on AIFA-style query-passage pairs (e.g. "protesi valvolare" vs
# "DOAC controindicati" → 0.59 relevance, vs unrelated "CHA2DS2 score" → 0.04).
_DEFAULT_RERANKER_MODEL = "nickprock/cross-encoder-italian-bert-stsb"


def _build_reranker(model_name: str, revision: str | None = None) -> Any | None:
    """
    Instantiate a LlamaIndex SentenceTransformerRerank post-processor.

    Args:
        model_name: HuggingFace model identifier (e.g. "cross-encoder/ms-marco-MiniLM-L-6-v2")
        revision: optional HuggingFace commit hash for reproducibility (audit fix F6-4).
                  If None, HF resolves to "main" branch HEAD.

    Returns None (and logs a warning) if the package is not installed, so the
    retriever falls back to cosine-only ranking without crashing.
    """
    try:
        import torch
        from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank  # type: ignore[import]
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Audit fix 2026-05-06 (H9): the previous code logged the revision but
        # never passed it. SentenceTransformerRerank does not accept a `revision`
        # kwarg, so we pre-download a pinned snapshot via huggingface_hub and
        # point the reranker at the local path — same trick as for the embedder.
        model_resolved = model_name
        if revision:
            try:
                from huggingface_hub import snapshot_download
                model_resolved = snapshot_download(repo_id=model_name, revision=revision)
                log.info("Reranker pinned to revision %s (local snapshot: %s)",
                         revision[:8], model_resolved)
            except Exception as exc:
                # Audit V4 2026-05-12: AIFA_STRICT_CLEANROOM=1 turns this into
                # a hard failure so the cleanroom run cannot silently degrade
                # reproducibility when offline / hub unavailable.
                if os.getenv("AIFA_STRICT_CLEANROOM", "0") == "1":
                    raise RuntimeError(
                        f"AIFA_STRICT_CLEANROOM=1: reranker pinned revision "
                        f"{revision} required for model {model_name} is "
                        f"unavailable: {exc}"
                    ) from exc
                log.warning(
                    "Reranker revision pinning FAILED (revision=%s): %s — "
                    "falling back to unpinned model name.",
                    revision[:8], exc,
                )
        reranker = SentenceTransformerRerank(
            model=model_resolved,
            top_n=_SEMANTIC_K,
            device=device,
        )
        log.info("Reranker loaded: %s (top_n=%d, device=%s)", model_name, _SEMANTIC_K, device)
        return reranker
    except ImportError:
        log.warning(
            "llama-index-postprocessor-sbert-rerank not installed. "
            "Stage B will use cosine ranking only. "
            "Run: pip install llama-index-postprocessor-sbert-rerank"
        )
        return None


def build_retriever(
    db_dir: str | Path | None = None,
    embedding_model: str | None = None,
) -> ChromaRetriever:
    """Factory: build a ChromaRetriever from environment or explicit arguments."""
    db_path = Path(db_dir or os.getenv("CHROMA_DB_DIR", str(_DEFAULT_DB_DIR)))
    model = embedding_model or os.getenv("EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    return ChromaRetriever(db_dir=db_path, embedding_model=model)


class ChromaRetriever:
    """
    Wraps ChromaDB client and exposes two-stage retrieval against ingested AIFA PDFs.

    Usage:
        retriever = build_retriever()
        chunks = retriever.retrieve(evaluation_result)
    """

    def __init__(self, db_dir: Path, embedding_model: str) -> None:
        import chromadb

        # Force GPU if available for embedding (RTX 3060 12GB → ~10x speedup)
        import torch
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("Embedding device: %s", device)

        # Audit fix 2026-05-06 (C20 escalated): pin embedding model to a
        # specific HuggingFace commit hash. The previous code defined
        # _DEFAULT_EMBEDDING_REVISION but never passed it downstream — HF would
        # silently resolve to "main" HEAD, breaking bit-identical reproducibility
        # claimed in the thesis. Solution: download the snapshot once into a
        # local cache and point chromadb at the local path.
        embedding_revision = os.getenv("EMBEDDING_REVISION", _DEFAULT_EMBEDDING_REVISION)
        try:
            from huggingface_hub import snapshot_download
            local_path = snapshot_download(
                repo_id=embedding_model,
                revision=embedding_revision,
                # cache_dir defaults to HF cache, but a per-revision subdir is
                # implicitly used so reuse-across-runs is automatic.
            )
            embedding_resolved = local_path
            log.info("Embedding model pinned to revision %s (local snapshot: %s)",
                     embedding_revision[:8], local_path)
        except Exception as exc:
            # Network unavailable or hub down — fall back to model name resolution
            # (which may use HF cache or main HEAD). Log clearly to avoid silent
            # reproducibility loss. Audit V4 2026-05-12: AIFA_STRICT_CLEANROOM=1
            # turns this into a hard failure for cleanroom runs.
            if os.getenv("AIFA_STRICT_CLEANROOM", "0") == "1":
                raise RuntimeError(
                    f"AIFA_STRICT_CLEANROOM=1: embedding pinned revision "
                    f"{embedding_revision} required for model {embedding_model} "
                    f"is unavailable: {exc}"
                ) from exc
            embedding_resolved = embedding_model
            log.warning(
                "Embedding revision pinning FAILED (revision=%s): %s — "
                "falling back to unpinned model name. Reproducibility guarantee "
                "is therefore best-effort.",
                embedding_revision[:8], exc,
            )

        self._client = chromadb.PersistentClient(path=str(db_dir))
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=embedding_resolved,
            device=device,
            normalize_embeddings=True,
        )
        self._embedding_revision = embedding_revision
        self._collection_cache: dict[str, Any] = {}

        reranker_model = os.getenv("RERANKER_MODEL", _DEFAULT_RERANKER_MODEL)
        # Note: the pinned reranker revision (_DEFAULT_RERANKER_REVISION) may not
        # exist on HuggingFace Hub if the model has been updated or deleted. In
        # that case snapshot_download will fail and _build_reranker falls back to
        # the unpinned model name (or raises if AIFA_STRICT_CLEANROOM=1).
        reranker_revision = os.getenv("RERANKER_REVISION", _DEFAULT_RERANKER_REVISION)
        self._reranker = _build_reranker(reranker_model, revision=reranker_revision)

        log.info("ChromaRetriever initialized. DB: %s, Model: %s (revision=%s), Device: %s",
                 db_dir, embedding_model, embedding_revision[:8], device)

    # ── Public API ─────────────────────────────────────────────────────────────

    def retrieve(self, result: EvaluationResult) -> list[RetrievedChunk]:
        """
        Run the full two-stage retrieval for a given EvaluationResult.

        Returns a deduplicated list of RetrievedChunk, Stage A results first.
        """
        nota_id = result.nota_evaluated

        # Stage A: anchor-guided (deterministic)
        stage_a = self._retrieve_anchor_guided(result, nota_id)
        seen_ids: set[str] = {c.chunk_id for c in stage_a}

        # Stage B: semantic enrichment
        stage_b = self._retrieve_semantic(result, nota_id, exclude_ids=seen_ids)

        log.info(
            "Retrieval complete: %d anchor-guided + %d semantic chunks",
            len(stage_a), len(stage_b),
        )
        return stage_a + stage_b

    # ── Stage A: Anchor-guided retrieval ──────────────────────────────────────

    def _retrieve_anchor_guided(
        self,
        result: EvaluationResult,
        nota_id: str,
    ) -> list[RetrievedChunk]:
        """
        Retrieve chunks by exact metadata match on {pdf_file, page} from anchors.

        Sources:
        - blocking_rules: the decisive rules that caused the denial / uncertainty
        - passed_rules:   rules that passed (context for the explanation)
        """
        anchors: list[tuple[str, int]] = []  # (pdf_file, page) pairs to fetch

        for br in result.rag_payload.blocking_rules:
            anchors.append((br.anchor.pdf_file, br.anchor.page))

        for pr in result.rag_payload.passed_rules:
            # passed_rules anchors are stored as plain dicts (from .model_dump())
            anchor_dict = pr.get("anchor", {})
            pdf_file = anchor_dict.get("pdf_file", "")
            page     = anchor_dict.get("page", 0)
            if pdf_file and page:
                anchors.append((pdf_file, page))

        # Deduplicate (same pdf+page may appear in multiple rules)
        unique_anchors = list(dict.fromkeys(anchors))

        chunks: list[RetrievedChunk] = []
        for pdf_file, page in unique_anchors:
            fetched = self._get_by_anchor(nota_id, pdf_file, page)
            chunks.extend(fetched)

        return chunks

    def _get_by_anchor(
        self,
        nota_id: str,
        pdf_file: str,
        page: int,
    ) -> list[RetrievedChunk]:
        """ChromaDB metadata filter: retrieve all chunks from a specific {pdf_file, page}.

        Tries the canonical pdf_file name first, then a variant with a trailing space
        before the extension (e.g. 'Nota_66.pdf' → 'Nota_66 .pdf') to handle ingestion
        artifacts from PDF files whose OS-level filename contains a trailing space.
        """
        collection = self._get_collection(nota_id)
        if collection is None:
            return []

        # Build candidate filenames: exact match + space-before-extension variant
        candidates = [pdf_file]
        # e.g. 'Nota_66.pdf' → 'Nota_66 .pdf'
        if "." in pdf_file and not pdf_file.endswith(" .pdf"):
            stem, ext = pdf_file.rsplit(".", 1)
            candidates.append(f"{stem} .{ext}")

        for candidate in candidates:
            try:
                # Exact page match (fast path)
                result = collection.get(
                    where={"$and": [{"pdf_file": {"$eq": candidate}}, {"page": {"$eq": page}}]},
                    include=["documents", "metadatas"],
                )
                chunks = self._parse_get_result(result, stage="anchor_guided")
                if chunks:
                    return chunks

                # Fallback: anchor page within [chunk.page, chunk.page_end]
                result = collection.get(
                    where={"$and": [
                        {"pdf_file": {"$eq": candidate}},
                        {"page": {"$lte": page}},
                        {"page_end": {"$gte": page}},
                    ]},
                    include=["documents", "metadatas"],
                )
                chunks = self._parse_get_result(result, stage="anchor_guided")
                if chunks:
                    return chunks
            except Exception as exc:
                log.warning("Anchor-guided retrieval failed for %s p.%d: %s", candidate, page, exc)

        return []

    # ── Stage B: Semantic retrieval ────────────────────────────────────────────

    def _retrieve_semantic(
        self,
        result: EvaluationResult,
        nota_id: str,
        exclude_ids: set[str],
    ) -> list[RetrievedChunk]:
        """
        Semantic search using clinical_context_summary as the query.

        When the LlamaIndex reranker is available:
          1. Over-fetch _SEMANTIC_FETCH_K=15 cosine candidates from ChromaDB.
          2. Wrap them as LlamaIndex NodeWithScore objects (chunk stored in metadata).
          3. Apply SentenceTransformerRerank → returns top-_SEMANTIC_K=5 by joint
             (query, passage) cross-encoder score.
          4. Reconstruct RetrievedChunk objects from node metadata.

        Falls back to cosine top-5 when the reranker package is not installed.

        Deduplicates against Stage A results (by chunk_id) in both paths.
        """
        query = result.rag_payload.clinical_context_summary
        if not query.strip():
            return []

        collection = self._get_collection(nota_id)
        if collection is None:
            return []

        # Over-fetch more candidates when reranker is active
        fetch_k = (_SEMANTIC_FETCH_K if self._reranker else _SEMANTIC_K) + len(exclude_ids)

        try:
            result_data = collection.query(
                query_texts=[query],
                n_results=fetch_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            log.warning("Semantic retrieval failed for nota_%s: %s", nota_id, exc)
            return []

        candidates = self._parse_query_result(result_data, stage="semantic")
        # Deduplicate against Stage A before reranking
        candidates = [c for c in candidates if c.chunk_id not in exclude_ids]

        if self._reranker and candidates:
            candidates = self._apply_reranker(candidates, query)

        return candidates[:_SEMANTIC_K]

    def _apply_reranker(
        self,
        chunks: list[RetrievedChunk],
        query: str,
    ) -> list[RetrievedChunk]:
        """
        Wrap RetrievedChunk objects as LlamaIndex NodeWithScore, run the
        cross-encoder reranker, and return reranked chunks (still as
        RetrievedChunk, with score updated to the cross-encoder score).
        """
        try:
            from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode  # type: ignore[import]

            nodes = [
                NodeWithScore(
                    node=TextNode(
                        text=c.text,
                        id_=c.chunk_id,
                        metadata={"chunk": c},
                    ),
                    score=c.score,
                )
                for c in chunks
            ]
            query_bundle = QueryBundle(query_str=query)
            reranked = self._reranker.postprocess_nodes(nodes, query_bundle=query_bundle)

            result: list[RetrievedChunk] = []
            for node_with_score in reranked:
                original_chunk: RetrievedChunk = node_with_score.node.metadata["chunk"]
                # Return a new RetrievedChunk with the cross-encoder score
                result.append(RetrievedChunk(
                    chunk_id=original_chunk.chunk_id,
                    text=original_chunk.text,
                    pdf_file=original_chunk.pdf_file,
                    nota_id=original_chunk.nota_id,
                    page=original_chunk.page,
                    page_end=original_chunk.page_end,
                    section=original_chunk.section,
                    score=float(node_with_score.score or 0.0),
                    retrieval_stage=original_chunk.retrieval_stage,
                    char_start=original_chunk.char_start,
                    char_end=original_chunk.char_end,
                    line_start=original_chunk.line_start,
                    line_end=original_chunk.line_end,
                    bbox=list(original_chunk.bbox),
                    sha256=original_chunk.sha256,
                    is_in_table=original_chunk.is_in_table,
                    table_id=original_chunk.table_id,
                    schema_version=original_chunk.schema_version,
                ))
            return result

        except Exception as exc:
            log.warning("Reranker failed, falling back to cosine ranking: %s", exc)
            return chunks

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_collection(self, nota_id: str) -> Any | None:
        # CHROMA_COLLECTION_SUFFIX default is "_v2" to match ingest_v2.py naming
        # convention. Without .env, retriever searches "nota_XX_v2" collections.
        # Override via env var CHROMA_COLLECTION_SUFFIX if a different suffix is used.
        suffix = os.getenv("CHROMA_COLLECTION_SUFFIX", "_v2")
        name = f"nota_{nota_id}{suffix}"
        if name in self._collection_cache:
            return self._collection_cache[name]
        try:
            col = self._client.get_collection(
                name=name,
                embedding_function=self._embedding_fn,
            )
            self._collection_cache[name] = col
            return col
        except Exception as exc:
            log.error(
                "ChromaDB collection '%s' not found. Run 'make ingest' first. Error: %s",
                name, exc,
            )
            return None

    def _parse_get_result(
        self,
        result: dict[str, Any],
        stage: str,
    ) -> list[RetrievedChunk]:
        chunks = []
        ids       = result.get("ids", []) or []
        documents = result.get("documents", []) or []
        metadatas = result.get("metadatas", []) or []

        for chunk_id, doc, meta in zip(ids, documents, metadatas):
            chunks.append(_meta_to_chunk(chunk_id, doc, meta, stage, score=0.0))
        # Stable deterministic ordering: by chunk_id ascending. Anchor-guided
        # results have score=0 so primary sort is irrelevant; chunk_id is the
        # tiebreaker that guarantees identical ordering across runs even when
        # ChromaDB's internal iteration order changes.
        chunks.sort(key=lambda c: c.chunk_id)
        return chunks

    def _parse_query_result(
        self,
        result: dict[str, Any],
        stage: str,
    ) -> list[RetrievedChunk]:
        chunks = []
        # ChromaDB query returns nested lists (one per query text — we always send 1)
        ids_list       = (result.get("ids")       or [[]])[0]
        docs_list      = (result.get("documents") or [[]])[0]
        metas_list     = (result.get("metadatas") or [[]])[0]
        distances_list = (result.get("distances") or [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids_list, docs_list, metas_list, distances_list):
            chunks.append(_meta_to_chunk(chunk_id, doc, meta, stage, score=float(dist)))
        # Deterministic ordering: distance ascending (= cosine similarity desc),
        # tiebreaker chunk_id ascending. ChromaDB does not guarantee a stable
        # order between candidates with identical distance; a chunk_id tiebreaker
        # makes the overall pipeline reproducible bit-for-bit.
        chunks.sort(key=lambda c: (c.score, c.chunk_id))
        return chunks
