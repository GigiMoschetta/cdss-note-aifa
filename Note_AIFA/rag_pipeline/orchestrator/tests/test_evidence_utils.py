"""
Tests for evidence_utils.py — pure functions, no mocking required.

Covers:
- normalize_pdf_filename: whitespace, case, trailing-space-before-ext
- pdf_stem: extension removal
- find_chunks_for_anchor: 3-strategy cascade (exact, ±1 offset, stem-only)
- extract_snippet: sentence/word/hard truncation
- make_evidence_id: determinism, length, normalization
"""

from rag_pipeline.orchestrator.evidence_utils import (
    extract_snippet,
    find_chunks_for_anchor,
    make_evidence_id,
    normalize_pdf_filename,
    pdf_stem,
)
from rag_pipeline.orchestrator.schemas import RetrievedChunk

# ── Helpers ────────────────────────────────────────────────────────────────

def _chunk(chunk_id: str, pdf_file: str, page: int,
           page_end: int | None = None, stage: str = "anchor_guided") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="normative text",
        pdf_file=pdf_file,
        nota_id="97",
        page=page,
        page_end=page_end or page,
        score=0.0,
        retrieval_stage=stage,
    )


# ── normalize_pdf_filename ─────────────────────────────────────────────────

class TestNormalizePdfFilename:

    def test_trailing_space_before_extension(self):
        assert normalize_pdf_filename("Nota_66 .pdf") == "nota_66.pdf"

    def test_uppercase_extension(self):
        assert normalize_pdf_filename("NOTA_97.PDF") == "nota_97.pdf"

    def test_leading_trailing_whitespace(self):
        assert normalize_pdf_filename("  nota-13.pdf ") == "nota-13.pdf"

    def test_already_normalized(self):
        assert normalize_pdf_filename("nota-97.pdf") == "nota-97.pdf"

    def test_hyphenated_filename(self):
        assert normalize_pdf_filename("nota-97-all-2.pdf") == "nota-97-all-2.pdf"

    def test_mixed_case(self):
        assert normalize_pdf_filename("Nota_01.pdf") == "nota_01.pdf"

    def test_multiple_spaces_before_ext(self):
        assert normalize_pdf_filename("Nota_66  .pdf") == "nota_66.pdf"


# ── pdf_stem ───────────────────────────────────────────────────────────────

class TestPdfStem:

    def test_basic(self):
        assert pdf_stem("Nota_66.pdf") == "nota_66"

    def test_hyphenated(self):
        assert pdf_stem("nota-97-all-2.pdf") == "nota-97-all-2"

    def test_trailing_space_variant(self):
        assert pdf_stem("Nota_66 .pdf") == "nota_66"

    def test_uppercase(self):
        assert pdf_stem("NOTA_13.PDF") == "nota_13"


# ── find_chunks_for_anchor ─────────────────────────────────────────────────

class TestFindChunksForAnchor:

    def test_strategy1_exact_match(self):
        chunks = [_chunk("c1", "nota-97.pdf", 3)]
        matched, notes = find_chunks_for_anchor(chunks, "nota-97.pdf", 3)
        assert len(matched) == 1
        assert matched[0].chunk_id == "c1"
        assert notes == "exact_match"

    def test_strategy1_case_insensitive(self):
        chunks = [_chunk("c1", "nota-97.pdf", 3)]
        matched, notes = find_chunks_for_anchor(chunks, "NOTA-97.PDF", 3)
        assert len(matched) == 1
        assert notes == "exact_match"

    def test_strategy1_trailing_space_normalized(self):
        chunks = [_chunk("c1", "nota_66.pdf", 3)]
        matched, notes = find_chunks_for_anchor(chunks, "Nota_66 .pdf", 3)
        assert len(matched) == 1
        assert notes == "exact_match"

    def test_strategy2_page_minus_one(self):
        chunks = [_chunk("c1", "nota-97.pdf", 2)]
        matched, notes = find_chunks_for_anchor(chunks, "nota-97.pdf", 3)
        assert len(matched) == 1
        assert notes == "page_offset_-1"

    def test_strategy2_page_plus_one(self):
        chunks = [_chunk("c1", "nota-97.pdf", 4)]
        matched, notes = find_chunks_for_anchor(chunks, "nota-97.pdf", 3)
        assert len(matched) == 1
        assert notes == "page_offset_+1"

    def test_strategy3_stem_match(self):
        # Anchor page 99 doesn't match any chunk page, but stem matches
        chunks = [_chunk("c1", "nota_66.pdf", 5)]
        matched, notes = find_chunks_for_anchor(chunks, "nota_66.pdf", 99)
        assert notes == "stem_match"
        assert matched[0].chunk_id == "c1"

    def test_no_match(self):
        chunks = [_chunk("c1", "nota-97.pdf", 3)]
        matched, notes = find_chunks_for_anchor(chunks, "nota-13.pdf", 99)
        assert matched == []
        assert notes == "no_match"

    def test_strategy1_wins_over_strategy2(self):
        chunks = [
            _chunk("exact", "nota-97.pdf", 3),
            _chunk("offset", "nota-97.pdf", 2),
        ]
        matched, notes = find_chunks_for_anchor(chunks, "nota-97.pdf", 3)
        assert notes == "exact_match"
        assert matched[0].chunk_id == "exact"

    def test_multiple_chunks_at_same_page(self):
        chunks = [
            _chunk("c1", "nota-97.pdf", 3),
            _chunk("c2", "nota-97.pdf", 3),
        ]
        matched, notes = find_chunks_for_anchor(chunks, "nota-97.pdf", 3)
        assert len(matched) == 2
        assert notes == "exact_match"

    def test_stage_filter_excludes_semantic(self):
        chunks = [
            _chunk("c1", "nota-97.pdf", 3, stage="anchor_guided"),
            _chunk("c2", "nota-97.pdf", 3, stage="semantic"),
        ]
        matched, _ = find_chunks_for_anchor(
            chunks, "nota-97.pdf", 3, stage_filter="anchor_guided"
        )
        assert len(matched) == 1
        assert matched[0].chunk_id == "c1"

    def test_stage_filter_none_uses_all(self):
        chunks = [
            _chunk("c1", "nota-97.pdf", 3, stage="anchor_guided"),
            _chunk("c2", "nota-97.pdf", 3, stage="semantic"),
        ]
        matched, _ = find_chunks_for_anchor(
            chunks, "nota-97.pdf", 3, stage_filter=None
        )
        assert len(matched) == 2

    def test_empty_chunks_list(self):
        matched, notes = find_chunks_for_anchor([], "nota-97.pdf", 3)
        assert matched == []
        assert notes == "no_match"


# ── extract_snippet ────────────────────────────────────────────────────────

class TestExtractSnippet:

    def test_empty_list(self):
        snippet, char_range = extract_snippet([])
        assert snippet == ""
        assert char_range is None

    def test_all_whitespace(self):
        snippet, char_range = extract_snippet(["   ", "\n", ""])
        assert snippet == ""
        assert char_range is None

    def test_short_text_returned_as_is(self):
        snippet, char_range = extract_snippet(["hello world"])
        assert snippet == "hello world"
        assert char_range == (0, 11)

    def test_multiple_texts_joined(self):
        snippet, _ = extract_snippet(["hello", "world"])
        assert snippet == "hello world"

    def test_long_text_truncated_at_sentence(self):
        # Build text with a sentence boundary well within max_chars
        prefix = "A" * 120
        long = prefix + ". Then more text. " + "B" * 900
        snippet, _ = extract_snippet([long], max_chars=200)
        assert len(snippet) < len(long)
        assert snippet.endswith(".")

    def test_long_text_truncated_at_word(self):
        # No sentence boundary: many words, no periods
        long = "word " * 300
        snippet, _ = extract_snippet([long], max_chars=100)
        assert len(snippet) <= 100
        # Should end at a word boundary (space stripped)
        assert not snippet.endswith(" ")

    def test_char_range_starts_at_zero(self):
        snippet, char_range = extract_snippet(["some text"])
        assert char_range[0] == 0

    def test_char_range_matches_snippet_length(self):
        snippet, char_range = extract_snippet(["some text"])
        assert char_range == (0, len(snippet))

    def test_respects_max_chars_parameter(self):
        long = "X" * 2000
        snippet, _ = extract_snippet([long], max_chars=500)
        assert len(snippet) <= 500


# ── make_evidence_id ───────────────────────────────────────────────────────

class TestMakeEvidenceId:

    def test_deterministic(self):
        id1 = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        id2 = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        assert id1 == id2

    def test_length_is_12(self):
        ev_id = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        assert len(ev_id) == 12

    def test_different_role_different_id(self):
        blocking = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        supporting = make_evidence_id("R1", "nota-97.pdf", 3, "supporting")
        assert blocking != supporting

    def test_different_page_different_id(self):
        id_p3 = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        id_p4 = make_evidence_id("R1", "nota-97.pdf", 4, "blocking")
        assert id_p3 != id_p4

    def test_different_rule_different_id(self):
        id_r1 = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        id_r2 = make_evidence_id("R2", "nota-97.pdf", 3, "blocking")
        assert id_r1 != id_r2

    def test_normalized_filename_same_id(self):
        id1 = make_evidence_id("R1", "Nota_66 .pdf", 3, "blocking")
        id2 = make_evidence_id("R1", "nota_66.pdf", 3, "blocking")
        assert id1 == id2

    def test_hex_characters_only(self):
        ev_id = make_evidence_id("R1", "nota-97.pdf", 3, "blocking")
        assert all(c in "0123456789abcdef" for c in ev_id)
