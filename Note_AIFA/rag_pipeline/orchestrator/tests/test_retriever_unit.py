"""
Tests for retriever.py — ChromaRetriever internals.

All ChromaDB interactions are mocked (MagicMock). No real DB required.

Covers:
- _get_collection: cache hit, cache miss, collection not found
- _parse_get_result: empty, single chunk, type casting (page as int)
- _parse_query_result: nested list unwrapping, distance → score
- _get_by_anchor: exact match, range fallback, trailing-space variant,
                  exception handling
- _retrieve_semantic: empty query, None collection, exclude_ids dedup
- _apply_reranker: normal flow, exception fallback
- retrieve: Stage A first, Stage B deduplicated, no duplicate chunk_ids
"""
from unittest.mock import MagicMock

import pytest
from rag_pipeline.orchestrator.retriever import ChromaRetriever
from rag_pipeline.orchestrator.schemas import RetrievedChunk


@pytest.fixture(autouse=True)
def _pin_collection_suffix(monkeypatch):
    """Verifica Totale 2026-05-29: questi unit test montano collezioni mock con
    nome NON suffissato (es. ``r._collection_cache["nota_97"]``). Il default di
    produzione di ``CHROMA_COLLECTION_SUFFIX`` è ``"_v2"`` (allineato a
    ``ingest_v2.py``); qui lo fissiamo a ``""`` per coerenza col setup dei mock,
    senza alterare il comportamento di produzione."""
    monkeypatch.setenv("CHROMA_COLLECTION_SUFFIX", "")


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_retriever(reranker=None):
    """Build a ChromaRetriever bypassing __init__ (no real ChromaDB)."""
    r = ChromaRetriever.__new__(ChromaRetriever)
    r._client = MagicMock()
    r._embedding_fn = MagicMock()
    r._collection_cache = {}
    r._reranker = reranker
    return r


def _chroma_get_result(ids, docs, metas):
    """Build the dict structure ChromaDB .get() returns."""
    return {"ids": ids, "documents": docs, "metadatas": metas}


def _chroma_query_result(ids, docs, metas, distances):
    """Build the dict structure ChromaDB .query() returns (nested lists)."""
    return {
        "ids": [ids],
        "documents": [docs],
        "metadatas": [metas],
        "distances": [distances],
    }


def _chunk_meta(pdf_file="nota-97.pdf", page=3, page_end=None,
                nota_id="97", section=""):
    return {
        "pdf_file": pdf_file,
        "page": page,
        "page_end": page_end or page,
        "nota_id": nota_id,
        "section": section,
    }


def _eval_result(nota_id="97", blocking=None, passed=None, summary="paziente con FANV"):
    r = MagicMock()
    r.nota_evaluated = nota_id
    r.rag_payload = MagicMock()
    r.rag_payload.blocking_rules = blocking or []
    r.rag_payload.passed_rules = passed or []
    r.rag_payload.clinical_context_summary = summary
    return r


def _blocking_rule(pdf_file="nota-97.pdf", page=3):
    br = MagicMock()
    br.anchor = MagicMock()
    br.anchor.pdf_file = pdf_file
    br.anchor.page = page
    return br


# ── _get_collection ───────────────────────────────────────────────────────

class TestGetCollection:

    def test_first_call_fetches_from_client(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._client.get_collection.return_value = mock_col

        col = r._get_collection("97")

        r._client.get_collection.assert_called_once()
        assert col is mock_col

    def test_second_call_returns_cached(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._client.get_collection.return_value = mock_col

        col1 = r._get_collection("97")
        col2 = r._get_collection("97")

        assert r._client.get_collection.call_count == 1
        assert col1 is col2

    def test_not_found_returns_none(self):
        r = _make_retriever()
        r._client.get_collection.side_effect = Exception("collection not found")

        col = r._get_collection("99")

        assert col is None


# ── _parse_get_result ─────────────────────────────────────────────────────

class TestParseGetResult:

    def test_empty_result(self):
        r = _make_retriever()
        result = _chroma_get_result([], [], [])
        chunks = r._parse_get_result(result, stage="anchor_guided")
        assert chunks == []

    def test_single_chunk_fields(self):
        r = _make_retriever()
        result = _chroma_get_result(
            ["c1"],
            ["normative text"],
            [_chunk_meta("nota-97.pdf", 3, 4, "97", "Section A")],
        )
        chunks = r._parse_get_result(result, stage="anchor_guided")
        assert len(chunks) == 1
        c = chunks[0]
        assert c.chunk_id == "c1"
        assert c.text == "normative text"
        assert c.pdf_file == "nota-97.pdf"
        assert c.page == 3
        assert c.page_end == 4
        assert c.nota_id == "97"
        assert c.section == "Section A"
        assert c.score == 0.0
        assert c.retrieval_stage == "anchor_guided"

    def test_page_cast_to_int(self):
        r = _make_retriever()
        meta = _chunk_meta()
        meta["page"] = "3"       # ChromaDB may return strings
        meta["page_end"] = "4"
        result = _chroma_get_result(["c1"], ["text"], [meta])
        chunks = r._parse_get_result(result, stage="anchor_guided")
        assert isinstance(chunks[0].page, int)
        assert isinstance(chunks[0].page_end, int)

    def test_none_ids_returns_empty(self):
        r = _make_retriever()
        result = {"ids": None, "documents": None, "metadatas": None}
        chunks = r._parse_get_result(result, stage="anchor_guided")
        assert chunks == []


# ── _parse_query_result ───────────────────────────────────────────────────

class TestParseQueryResult:

    def test_empty_nested_list(self):
        r = _make_retriever()
        result = _chroma_query_result([], [], [], [])
        chunks = r._parse_query_result(result, stage="semantic")
        assert chunks == []

    def test_single_chunk_fields(self):
        r = _make_retriever()
        result = _chroma_query_result(
            ["c1"],
            ["semantic text"],
            [_chunk_meta("nota-97.pdf", 5)],
            [0.25],
        )
        chunks = r._parse_query_result(result, stage="semantic")
        assert len(chunks) == 1
        c = chunks[0]
        assert c.chunk_id == "c1"
        assert c.score == pytest.approx(0.25)
        assert c.retrieval_stage == "semantic"

    def test_distance_stored_as_float(self):
        r = _make_retriever()
        result = _chroma_query_result(["c1"], ["text"], [_chunk_meta()], [0.1])
        chunks = r._parse_query_result(result, stage="semantic")
        assert isinstance(chunks[0].score, float)


# ── _get_by_anchor ────────────────────────────────────────────────────────

class TestGetByAnchor:

    def test_exact_page_match_returns_chunk(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col
        mock_col.get.return_value = _chroma_get_result(
            ["c1"], ["text"], [_chunk_meta("nota-97.pdf", 3)]
        )
        chunks = r._get_by_anchor("97", "nota-97.pdf", 3)
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "c1"

    def test_exact_miss_range_fallback(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col

        def _get_side_effect(**kwargs):
            where = kwargs.get("where", {})
            conditions = where.get("$and", [])
            # First call (exact page==3) returns empty, second (range) returns chunk
            has_eq = any("$eq" in list(c.values())[0]
                         for c in conditions if isinstance(list(c.values())[0], dict))
            if has_eq and any(3 == list(c.values())[0].get("$eq")
                              for c in conditions if isinstance(list(c.values())[0], dict)):
                return _chroma_get_result([], [], [])
            return _chroma_get_result(["c1"], ["text"], [_chunk_meta("nota-97.pdf", 2, 4)])

        mock_col.get.side_effect = _get_side_effect
        chunks = r._get_by_anchor("97", "nota-97.pdf", 3)
        # The range fallback should find c1
        assert len(chunks) == 1

    def test_trailing_space_variant_tried(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_66"] = mock_col
        # All .get() calls return empty → forces the retriever to try both
        # "Nota_66.pdf" and "Nota_66 .pdf" (2 candidates × 2 queries each = 4 calls).
        mock_col.get.return_value = _chroma_get_result([], [], [])

        r._get_by_anchor("66", "Nota_66.pdf", 3)

        # At least 4 calls = both candidates (exact + range per candidate)
        assert mock_col.get.call_count >= 4

    def test_exception_returns_empty(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col
        mock_col.get.side_effect = Exception("ChromaDB error")
        chunks = r._get_by_anchor("97", "nota-97.pdf", 3)
        assert chunks == []

    def test_collection_none_returns_empty(self):
        r = _make_retriever()
        r._client.get_collection.side_effect = Exception("not found")
        chunks = r._get_by_anchor("99", "nota-99.pdf", 1)
        assert chunks == []


# ── _retrieve_semantic ────────────────────────────────────────────────────

class TestRetrieveSemantic:

    def test_empty_query_returns_empty(self):
        r = _make_retriever()
        result = _eval_result(summary="   ")
        chunks = r._retrieve_semantic(result, "97", exclude_ids=set())
        assert chunks == []

    def test_collection_none_returns_empty(self):
        r = _make_retriever()
        r._client.get_collection.side_effect = Exception("not found")
        result = _eval_result(summary="paziente con FANV e apixaban")
        chunks = r._retrieve_semantic(result, "97", exclude_ids=set())
        assert chunks == []

    def test_exclude_ids_removes_stage_a_chunks(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col
        mock_col.query.return_value = _chroma_query_result(
            ["c1", "c2", "c3"],
            ["text1", "text2", "text3"],
            [_chunk_meta(page=1), _chunk_meta(page=2), _chunk_meta(page=3)],
            [0.1, 0.2, 0.3],
        )
        result = _eval_result(summary="paziente con FANV")
        # c1 was already in Stage A
        chunks = r._retrieve_semantic(result, "97", exclude_ids={"c1"})
        ids = [c.chunk_id for c in chunks]
        assert "c1" not in ids

    def test_query_exception_returns_empty(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col
        mock_col.query.side_effect = Exception("query failed")
        result = _eval_result(summary="paziente con FANV")
        chunks = r._retrieve_semantic(result, "97", exclude_ids=set())
        assert chunks == []

    def test_result_limited_to_semantic_k(self):
        from rag_pipeline.orchestrator.retriever import _SEMANTIC_K
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col
        # Return more than _SEMANTIC_K chunks
        n = _SEMANTIC_K + 3
        mock_col.query.return_value = _chroma_query_result(
            [f"c{i}" for i in range(n)],
            ["text"] * n,
            [_chunk_meta(page=i) for i in range(n)],
            [0.1 * i for i in range(n)],
        )
        result = _eval_result(summary="paziente con FANV")
        chunks = r._retrieve_semantic(result, "97", exclude_ids=set())
        assert len(chunks) <= _SEMANTIC_K


# ── _apply_reranker ────────────────────────────────────────────────────────

class TestApplyReranker:

    def _make_chunk(self, chunk_id="c1", page=3):
        return RetrievedChunk(
            chunk_id=chunk_id,
            text="normative text",
            pdf_file="nota-97.pdf",
            nota_id="97",
            page=page,
            page_end=page,
            score=0.5,
            retrieval_stage="semantic",
        )

    def test_reranker_exception_returns_original(self):
        r = _make_retriever()
        mock_reranker = MagicMock()
        mock_reranker.postprocess_nodes.side_effect = Exception("reranker failed")
        r._reranker = mock_reranker

        chunks = [self._make_chunk("c1"), self._make_chunk("c2")]
        result = r._apply_reranker(chunks, "test query")
        # Should fall back to original list
        assert result == chunks


# ── retrieve — Stage A + Stage B integration ─────────────────────────────

class TestRetrieve:

    def test_stage_a_chunks_first(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col

        # Stage A: blocking rule anchor
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        eval_result = _eval_result("97", blocking=[br], summary="query")

        # _get() returns Stage A chunk, .query() returns Stage B chunk
        mock_col.get.return_value = _chroma_get_result(
            ["stageA"], ["text A"], [_chunk_meta("nota-97.pdf", 3)]
        )
        mock_col.query.return_value = _chroma_query_result(
            ["stageB"], ["text B"], [_chunk_meta("nota-97.pdf", 7)], [0.2]
        )

        chunks = r.retrieve(eval_result)
        ids = [c.chunk_id for c in chunks]
        assert ids[0] == "stageA"
        assert "stageB" in ids

    def test_no_duplicate_chunk_ids(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col

        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        eval_result = _eval_result("97", blocking=[br], summary="query")

        mock_col.get.return_value = _chroma_get_result(
            ["c1"], ["text A"], [_chunk_meta("nota-97.pdf", 3)]
        )
        # Stage B tries to return c1 again + c2
        mock_col.query.return_value = _chroma_query_result(
            ["c1", "c2"],
            ["text A", "text B"],
            [_chunk_meta("nota-97.pdf", 3), _chunk_meta("nota-97.pdf", 7)],
            [0.1, 0.2],
        )

        chunks = r.retrieve(eval_result)
        ids = [c.chunk_id for c in chunks]
        assert ids.count("c1") == 1  # no duplicates

    def test_retrieval_stage_labels_correct(self):
        r = _make_retriever()
        mock_col = MagicMock()
        r._collection_cache["nota_97"] = mock_col

        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        eval_result = _eval_result("97", blocking=[br], summary="query")

        mock_col.get.return_value = _chroma_get_result(
            ["c1"], ["text A"], [_chunk_meta("nota-97.pdf", 3)]
        )
        mock_col.query.return_value = _chroma_query_result(
            ["c2"], ["text B"], [_chunk_meta("nota-97.pdf", 7)], [0.2]
        )

        chunks = r.retrieve(eval_result)
        stage_map = {c.chunk_id: c.retrieval_stage for c in chunks}
        assert stage_map["c1"] == "anchor_guided"
        assert stage_map["c2"] == "semantic"
