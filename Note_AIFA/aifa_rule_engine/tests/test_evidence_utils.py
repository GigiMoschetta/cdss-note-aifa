"""
Unit tests for rag_pipeline.orchestrator.evidence_utils.

No LLM, no ChromaDB, no rule engine — pure function tests.
"""
from __future__ import annotations

import pytest
from rag_pipeline.orchestrator.evidence_utils import (
    _MAX_SNIPPET_CHARS,
    extract_snippet,
    find_chunks_for_anchor,
    make_evidence_id,
    normalize_pdf_filename,
)
from rag_pipeline.orchestrator.schemas import RetrievedChunk

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chunk(
    chunk_id: str = "c1",
    text: str = "Sample text.",
    pdf_file: str = "Nota_97.pdf",
    page: int = 1,
    retrieval_stage: str = "anchor_guided",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        pdf_file=pdf_file,
        nota_id="97",
        page=page,
        page_end=page,
        section="",
        score=0.0,
        retrieval_stage=retrieval_stage,
    )


# ── Test 1: normalize_pdf_filename ────────────────────────────────────────────

def test_normalize_pdf_filename_trailing_space():
    """'Nota_66 .pdf' → 'nota_66.pdf' (space before extension removed)."""
    assert normalize_pdf_filename("Nota_66 .pdf") == "nota_66.pdf"


def test_normalize_pdf_filename_uppercase():
    """'NOTA_97.PDF' → 'nota_97.pdf'."""
    assert normalize_pdf_filename("NOTA_97.PDF") == "nota_97.pdf"


def test_normalize_pdf_filename_preserves_internal_space():
    """'Nota 97.pdf' keeps the space between words (only pre-extension space removed)."""
    assert normalize_pdf_filename("Nota 97.pdf") == "nota 97.pdf"


def test_normalize_pdf_filename_strips_surrounding_whitespace():
    """Leading/trailing whitespace is stripped."""
    assert normalize_pdf_filename("  Nota_01.pdf  ") == "nota_01.pdf"


# ── Test 2: find_chunks_for_anchor — page ±1 offset ─────────────────────────

def test_page_offset_matching():
    """
    Chunk at page=0, anchor asks page=1 → matched via +1 offset fallback.
    This covers the 0-based vs 1-based page numbering mismatch.
    """
    chunk = _make_chunk(pdf_file="Nota_97.pdf", page=0)
    matched, notes = find_chunks_for_anchor(
        retrieved_chunks=[chunk],
        pdf_file="Nota_97.pdf",
        page=1,
    )
    assert len(matched) == 1
    assert matched[0].chunk_id == chunk.chunk_id
    assert "page_offset" in notes


def test_exact_match_preferred_over_offset():
    """When an exact match exists, it wins over an offset match."""
    exact  = _make_chunk(chunk_id="exact",  pdf_file="Nota_97.pdf", page=5)
    offset = _make_chunk(chunk_id="offset", pdf_file="Nota_97.pdf", page=4)
    matched, notes = find_chunks_for_anchor(
        retrieved_chunks=[offset, exact],
        pdf_file="Nota_97.pdf",
        page=5,
    )
    assert len(matched) == 1
    assert matched[0].chunk_id == "exact"
    assert notes == "exact_match"


# ── Test 3: extract_snippet — length cap ─────────────────────────────────────

def test_snippet_length_cap():
    """A text of 5000 chars is capped to ≤ _MAX_SNIPPET_CHARS chars."""
    long_text = "A " * 2500   # 5000 chars
    snippet, char_range = extract_snippet([long_text])
    assert snippet is not None
    assert len(snippet) <= _MAX_SNIPPET_CHARS
    assert char_range is not None
    assert char_range[0] == 0
    assert char_range[1] == len(snippet)


def test_snippet_short_text_unchanged():
    """A text shorter than the cap is returned verbatim."""
    text = "Questa è la prescrizione per il farmaco."
    snippet, char_range = extract_snippet([text])
    assert snippet == text
    assert char_range == (0, len(text))


def test_snippet_empty_input():
    """Empty list returns ('', None)."""
    snippet, char_range = extract_snippet([])
    assert snippet == ""
    assert char_range is None


# ── Test 4: evidence_missing when no chunks ───────────────────────────────────

def test_no_match_when_empty_retrieved_chunks():
    """
    find_chunks_for_anchor with an empty chunk list returns ([], 'no_match').
    In _build_normative_evidence this triggers evidence_missing=True.
    """
    matched, notes = find_chunks_for_anchor(
        retrieved_chunks=[],
        pdf_file="Nota_13.pdf",
        page=3,
    )
    assert matched == []
    assert notes == "no_match"


def test_no_match_when_stage_filter_excludes_all():
    """
    If the only available chunk has retrieval_stage='semantic' and stage_filter
    is 'anchor_guided', nothing matches → evidence_missing would be True.
    """
    semantic_chunk = _make_chunk(
        pdf_file="Nota_13.pdf", page=3, retrieval_stage="semantic"
    )
    matched, notes = find_chunks_for_anchor(
        retrieved_chunks=[semantic_chunk],
        pdf_file="Nota_13.pdf",
        page=3,
        stage_filter="anchor_guided",
    )
    assert matched == []
    assert notes == "no_match"


# ── Test 5: make_evidence_id — deterministic ─────────────────────────────────

def test_make_evidence_id_deterministic():
    """Same inputs always produce the same 12-char hex ID."""
    id1 = make_evidence_id("N97-001", "Nota_97.pdf", 5, "blocking")
    id2 = make_evidence_id("N97-001", "Nota_97.pdf", 5, "blocking")
    assert id1 == id2
    assert len(id1) == 12
    assert all(c in "0123456789abcdef" for c in id1)


def test_make_evidence_id_normalises_filename():
    """
    'Nota_66 .pdf' and 'nota_66.pdf' produce the same ID (normalisation applied).
    """
    id_with_space  = make_evidence_id("N66-001", "Nota_66 .pdf", 2, "blocking")
    id_without_space = make_evidence_id("N66-001", "nota_66.pdf", 2, "blocking")
    assert id_with_space == id_without_space


def test_make_evidence_id_different_roles():
    """Different roles produce different IDs."""
    blocking   = make_evidence_id("N97-001", "Nota_97.pdf", 5, "blocking")
    supporting = make_evidence_id("N97-001", "Nota_97.pdf", 5, "supporting")
    assert blocking != supporting
