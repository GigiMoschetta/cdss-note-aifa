"""
Tests for deterministic FONTI post-compose, parse_fonti analytics,
supporting citation check, and provenance cross-validation.
"""

from rag_pipeline.orchestrator.validators import (
    ParsedCitation,
    _citation_covers,
    _find_missing_supporting_citations,
    _find_ungrounded_citations,
    parse_fonti,
)

# ── parse_fonti tests (analytics only) ────────────────────────────────────

class TestParseFonti:

    def test_single_page(self):
        text = "- nota-97.pdf, p. 3"
        result = parse_fonti(text, ["nota-97.pdf"])
        assert len(result) == 1
        assert result[0] == ParsedCitation("nota-97.pdf", 3, 3)

    def test_page_range(self):
        text = "- nota-97.pdf, pp. 3-4"
        result = parse_fonti(text, ["nota-97.pdf"])
        assert any(c.page_start == 3 and c.page_end == 4 for c in result)

    def test_bare_page_no_false_positive(self):
        """Bare '3' in '13 farmaci' should NOT match as page 3."""
        text = "13 farmaci elencati nel documento"
        result = parse_fonti(text, ["nota-97.pdf"])
        assert len(result) == 0

    def test_pdf_filename_required(self):
        """Page reference alone without known PDF → empty list."""
        text = "p. 3"
        result = parse_fonti(text, ["nota-97.pdf"])
        assert len(result) == 0

    def test_multiple_pdfs(self):
        text = "- nota-97.pdf, p. 3\n- nota-13.pdf, p. 5"
        result = parse_fonti(text, ["nota-97.pdf", "nota-13.pdf"])
        assert len(result) >= 2
        pdfs = {c.pdf_file for c in result}
        assert "nota-97.pdf" in pdfs
        assert "nota-13.pdf" in pdfs


class TestCitationCovers:

    def test_single_page_covers(self):
        citations = [ParsedCitation("nota-97.pdf", 3, 3)]
        assert _citation_covers(citations, "nota-97.pdf", 3) is True

    def test_range_covers(self):
        citations = [ParsedCitation("nota-97.pdf", 3, 5)]
        assert _citation_covers(citations, "nota-97.pdf", 4) is True

    def test_page_outside_range(self):
        citations = [ParsedCitation("nota-97.pdf", 3, 5)]
        assert _citation_covers(citations, "nota-97.pdf", 6) is False

    def test_wrong_pdf(self):
        citations = [ParsedCitation("nota-97.pdf", 3, 3)]
        assert _citation_covers(citations, "nota-13.pdf", 3) is False


# ── Deterministic FONTI compose tests ─────────────────────────────────────

class TestComposeDeterministicFonti:

    def _make_orchestrator(self):
        """Create a minimal CDSSOrchestrator for testing the FONTI compose method."""
        from unittest.mock import MagicMock

        from rag_pipeline.orchestrator.cdss_orchestrator import CDSSOrchestrator

        orch = CDSSOrchestrator.__new__(CDSSOrchestrator)
        orch.retriever = MagicMock()
        orch.llm_backend = "test"
        orch.llm_model = "test"
        orch.rule_index = None
        orch.rule_engine_url = ""
        return orch

    def _make_evidence(self, pdf_file, page, missing=False):
        from rag_pipeline.orchestrator.schemas import NormativeEvidence
        return NormativeEvidence(
            evidence_id="test",
            rule_id="TEST_001",
            rule_type="EXCL_HARD",
            role="blocking",
            reason="test",
            pdf_file=pdf_file,
            page=page,
            exact_text="test snippet",
            evidence_missing=missing,
        )

    def _make_chunk(self, pdf_file, page):
        from rag_pipeline.orchestrator.schemas import RetrievedChunk
        return RetrievedChunk(
            chunk_id="c1",
            text="chunk text",
            pdf_file=pdf_file,
            nota_id="97",
            page=page,
            page_end=page,
            score=0.0,
            retrieval_stage="anchor_guided",
        )

    def test_replaces_existing_fonti(self):
        orch = self._make_orchestrator()
        explanation = "1. DECISIONE\nRIMBORSABILE\n\n5. FONTI\n- old ref"
        ev = [self._make_evidence("nota-97.pdf", 3)]
        chunks = []
        result = orch._compose_deterministic_fonti(explanation, ev, chunks)
        assert "old ref" not in result
        assert "nota-97.pdf, p. 3" in result

    def test_appends_when_missing(self):
        orch = self._make_orchestrator()
        explanation = "1. DECISIONE\nRIMBORSABILE"
        ev = [self._make_evidence("nota-97.pdf", 3)]
        result = orch._compose_deterministic_fonti(explanation, ev, [])
        assert "5. FONTI" in result
        assert "nota-97.pdf, p. 3" in result

    def test_deduplicates(self):
        orch = self._make_orchestrator()
        ev = [
            self._make_evidence("nota-97.pdf", 3),
            self._make_evidence("nota-97.pdf", 3),  # duplicate
        ]
        chunks = [self._make_chunk("nota-97.pdf", 3)]  # also duplicate
        result = orch._compose_deterministic_fonti("test", ev, chunks)
        count = result.count("nota-97.pdf, p. 3")
        assert count == 1, f"Expected 1 occurrence, got {count}"

    def test_evidence_missing_skipped(self):
        orch = self._make_orchestrator()
        ev = [self._make_evidence("nota-97.pdf", 3, missing=True)]
        result = orch._compose_deterministic_fonti("test", ev, [])
        assert "nota-97.pdf, p. 3" not in result


# ── P2-1: Supporting citation check ──────────────────────────────────────

class TestMissingSupportingCitations:

    def _make_result(self, passed_rules):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.rag_payload.passed_rules = passed_rules
        result.rag_payload.blocking_rules = []
        return result

    def test_supporting_anchor_cited(self):
        """Supporting rule anchor cited in FONTI → not missing."""
        result = self._make_result([
            {"rule_id": "R1", "anchor": {"pdf_file": "nota-97.pdf", "page": 3}}
        ])
        explanation = "5. FONTI\n- nota-97.pdf, p. 3"
        missing = _find_missing_supporting_citations(explanation, result)
        assert missing == []

    def test_supporting_anchor_not_cited(self):
        """Supporting rule anchor NOT in FONTI → flagged as missing."""
        result = self._make_result([
            {"rule_id": "R1", "anchor": {"pdf_file": "nota-13.pdf", "page": 5}}
        ])
        explanation = "5. FONTI\n- nota-97.pdf, p. 3"
        missing = _find_missing_supporting_citations(explanation, result)
        assert len(missing) == 1
        assert "nota-13.pdf" in missing[0]


# ── P2-2: Provenance cross-validation ────────────────────────────────────

class TestUngroundedCitations:

    def _make_chunk(self, pdf_file, page, page_end=None):
        from rag_pipeline.orchestrator.schemas import RetrievedChunk
        return RetrievedChunk(
            chunk_id="c1",
            text="text",
            pdf_file=pdf_file,
            nota_id="97",
            page=page,
            page_end=page_end or page,
            score=0.0,
            retrieval_stage="anchor_guided",
        )

    def _make_result(self):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.rag_payload.blocking_rules = []
        result.rag_payload.passed_rules = []
        return result

    def test_grounded_citation(self):
        """Citation referencing a page in retrieved chunks → not ungrounded."""
        chunks = [self._make_chunk("nota-97.pdf", 3)]
        explanation = "5. FONTI\n- nota-97.pdf, p. 3"
        result = self._make_result()
        ungrounded = _find_ungrounded_citations(explanation, result, chunks)
        assert ungrounded == []

    def test_ungrounded_citation(self):
        """Citation referencing a page NOT in chunks → flagged."""
        chunks = [self._make_chunk("nota-97.pdf", 3)]
        explanation = "5. FONTI\n- nota-97.pdf, p. 99"
        result = self._make_result()
        ungrounded = _find_ungrounded_citations(explanation, result, chunks)
        assert len(ungrounded) == 1
        assert "p.99" in ungrounded[0]

    def test_no_fonti_section(self):
        """No FONTI section → no ungrounded citations."""
        chunks = [self._make_chunk("nota-97.pdf", 3)]
        explanation = "Just some text without FONTI"
        result = self._make_result()
        ungrounded = _find_ungrounded_citations(explanation, result, chunks)
        assert ungrounded == []
