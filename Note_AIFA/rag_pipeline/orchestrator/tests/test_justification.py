"""
Tests for snippet-based justification verification.
"""

from rag_pipeline.orchestrator.validators import (
    _make_snippet_id,
    _normalize_snippet_text,
    check_justification_snippets,
)


def _make_evidence(rule_id, exact_text, role="blocking", missing=False):
    from rag_pipeline.orchestrator.schemas import NormativeEvidence
    return NormativeEvidence(
        evidence_id="test",
        rule_id=rule_id,
        rule_type="EXCL_HARD",
        role=role,
        reason="test",
        pdf_file="test.pdf",
        page=1,
        exact_text=exact_text,
        evidence_missing=missing,
    )


class TestSnippetIdDeterminism:

    def test_snippet_id_deterministic(self):
        """Same snippet always produces same snippet_id."""
        text = "Il farmaco è controindicato nei pazienti epatopatici."
        id1 = _make_snippet_id(text)
        id2 = _make_snippet_id(text)
        assert id1 == id2
        assert len(id1) == 10

    def test_normalize_snippet_text(self):
        """Punctuation, whitespace, and case are stripped consistently."""
        raw = "Il farmaco, è CONTROINDICATO!  Nei   pazienti..."
        norm = _normalize_snippet_text(raw)
        assert norm == "il farmaco è controindicato nei pazienti"

    def test_different_text_different_id(self):
        id1 = _make_snippet_id("text one")
        id2 = _make_snippet_id("text two")
        assert id1 != id2


class TestJustificationCheck:

    def test_primary_pass_snippet_id_present(self):
        """Explanation with snippet_id → justified=True."""
        text = "some normative text here"
        snippet_id = _make_snippet_id(text)
        ev = [_make_evidence("R1", text)]
        explanation = f"The decision is based on evidence. snippet_id: {snippet_id}"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is True
        assert missing == []

    def test_fallback_trigram_match_with_content_word(self):
        """Explanation with trigram + critical content word → justified=True."""
        text = "Il farmaco è controindicato nei pazienti epatopatici"
        ev = [_make_evidence("R1", text)]
        # Explanation contains "epatopatici" (the critical clinical term)
        explanation = "La decisione: il farmaco è controindicato nei pazienti epatopatici"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is True
        assert missing == []

    def test_trigram_match_without_content_word_rejected(self):
        """Audit fix 2026-05-06 (A4-P0-1): trigram match alone is NOT enough.

        Even if "il farmaco è controindicato nei pazienti" matches, the absence
        of the critical clinical term "epatopatici" (substituted with the
        generic "patologia") indicates the LLM may have hallucinated the
        clinical scope. Justification must require both trigram AND a
        non-stopword content word from the evidence.
        """
        text = "Il farmaco è controindicato nei pazienti epatopatici"
        ev = [_make_evidence("R1", text)]
        explanation = "La decisione: il farmaco è controindicato nei pazienti con patologia"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is False, (
            "Trigram-only match without 'epatopatici' content word must NOT "
            "be accepted — would hide LLM hallucination of clinical scope."
        )
        assert "R1" in missing

    def test_snippet_missing_from_explanation(self):
        """Explanation without snippet → justified=False."""
        text = "Testo normativo molto specifico"
        ev = [_make_evidence("R1", text)]
        explanation = "Una spiegazione completamente diversa senza riferimenti"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is False
        assert "R1" in missing

    def test_evidence_missing_skipped(self):
        """evidence_missing=True entries don't fail justification."""
        ev = [_make_evidence("R1", "some text", missing=True)]
        explanation = "No reference at all"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is True
        assert missing == []

    def test_supporting_role_skipped(self):
        """Supporting (non-blocking) evidence is not checked."""
        ev = [_make_evidence("R1", "some text", role="supporting")]
        explanation = "No reference at all"
        ok, missing = check_justification_snippets(explanation, ev)
        assert ok is True


class TestEvidenceBoxes:

    def _make_orchestrator(self):
        from unittest.mock import MagicMock

        from rag_pipeline.orchestrator.cdss_orchestrator import CDSSOrchestrator
        orch = CDSSOrchestrator.__new__(CDSSOrchestrator)
        orch.retriever = MagicMock()
        orch.llm_backend = "test"
        orch.llm_model = "test"
        orch.rule_index = None
        orch.rule_engine_url = ""
        return orch

    def test_append_evidence_boxes_format(self):
        """Deterministic post-compose produces expected format."""
        from unittest.mock import MagicMock
        orch = self._make_orchestrator()
        ev = [_make_evidence("R1", "test normative text")]

        mock_result = MagicMock()
        mock_result.reimbursement_decision = "NON_RIMBORSABILE"
        mock_result.rag_payload.blocking_rules = []

        result = orch._append_evidence_boxes("base text", ev, mock_result)
        assert "--- PROVA NORMATIVA ---" in result
        assert "Regola: R1" in result
        assert "snippet_id:" in result
        assert "--- FINE ---" in result

    def test_non_determinabile_lists_missing_fields(self):
        """UNKNOWN rules produce DATI MANCANTI box."""
        from unittest.mock import MagicMock
        orch = self._make_orchestrator()

        mock_result = MagicMock()
        mock_result.reimbursement_decision = "NON_DETERMINABILE"
        mock_result.missing_fields_coverage = ["eta", "sesso"]

        br = MagicMock()
        br.rule_id = "R1"
        br.rule_evaluated_as = "UNKNOWN"
        mock_result.rag_payload.blocking_rules = [br]

        result = orch._append_evidence_boxes("base text", [], mock_result)
        assert "--- DATI MANCANTI ---" in result
        assert "Regola: R1" in result
        assert "eta" in result
        assert "sesso" in result
