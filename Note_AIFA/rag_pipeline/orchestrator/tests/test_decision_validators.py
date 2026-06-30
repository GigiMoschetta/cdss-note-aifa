"""
Tests for the untested decision-logic validators.

Covers:
- _check_decision_consistent: all 4 decision types (RIMBORSABILE, NON_RIMBORSABILE,
  NON_DETERMINABILE, ROUTED)
- _check_decision_contradicted: the Italian negation regex (critical safety check)
- _decision_in_text: underscore/space variants
- _find_missing_citations: with/without FONTI section
- _find_suspected_hallucinations: drug presence in chunks vs explanation
- _extract_section: regex section extraction
- validate_response: integration of all checks
"""
from unittest.mock import MagicMock

from rag_pipeline.orchestrator.schemas import NormativeEvidence, RetrievedChunk
from rag_pipeline.orchestrator.validators import (
    _check_decision_consistent,
    _check_decision_contradicted,
    _decision_in_text,
    _extract_section,
    _find_missing_citations,
    _find_suspected_hallucinations,
    validate_response,
)

# ── Helpers ────────────────────────────────────────────────────────────────

def _anchor(pdf_file="nota-97.pdf", page=3):
    a = MagicMock()
    a.pdf_file = pdf_file
    a.page = page
    return a


def _blocking_rule(rule_id="R1", pdf_file="nota-97.pdf", page=3):
    br = MagicMock()
    br.rule_id = rule_id
    br.anchor = _anchor(pdf_file, page)
    return br


def _result(decision="RIMBORSABILE", route_to=None, drug="apixaban",
            blocking=None):
    r = MagicMock()
    r.reimbursement_decision = decision
    r.route_to = route_to
    r.drug_evaluated = drug
    r.rag_payload = MagicMock()
    r.rag_payload.blocking_rules = blocking or []
    r.rag_payload.passed_rules = []
    return r


def _chunk(chunk_id="c1", text="normative text", pdf_file="nota-97.pdf", page=3):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        pdf_file=pdf_file,
        nota_id="97",
        page=page,
        page_end=page,
        score=0.0,
        retrieval_stage="anchor_guided",
    )


# ── _decision_in_text ─────────────────────────────────────────────────────

class TestDecisionInText:

    def test_exact_match(self):
        assert _decision_in_text("RIMBORSABILE", "Il farmaco è RIMBORSABILE.")

    def test_underscore_to_space_variant(self):
        assert _decision_in_text("NON_RIMBORSABILE", "Il farmaco è NON RIMBORSABILE.")

    def test_no_separator_variant(self):
        assert _decision_in_text("NON_RIMBORSABILE", "NONRIMBORSABILE")

    def test_case_insensitive(self):
        assert _decision_in_text("RIMBORSABILE", "il farmaco è rimborsabile")

    def test_not_present(self):
        assert not _decision_in_text("RIMBORSABILE", "nessuna decisione qui")


# ── _check_decision_consistent ────────────────────────────────────────────

class TestCheckDecisionConsistent:

    def test_rimborsabile_present(self):
        result = _result("RIMBORSABILE")
        assert _check_decision_consistent("Il farmaco è RIMBORSABILE secondo la Nota.", result)

    def test_rimborsabile_missing(self):
        result = _result("RIMBORSABILE")
        assert not _check_decision_consistent("Il farmaco non è idoneo.", result)

    def test_non_rimborsabile_present(self):
        result = _result("NON_RIMBORSABILE")
        assert _check_decision_consistent("Decisione: NON_RIMBORSABILE.", result)

    def test_non_rimborsabile_space_variant(self):
        result = _result("NON_RIMBORSABILE")
        assert _check_decision_consistent("Il farmaco è NON RIMBORSABILE.", result)

    def test_non_determinabile_present(self):
        result = _result("NON_DETERMINABILE")
        assert _check_decision_consistent("Decisione: NON_DETERMINABILE.", result)

    def test_routed_route_to_present(self):
        result = _result(decision=None, route_to="66")
        assert _check_decision_consistent("Valutare secondo la Nota 66.", result)

    def test_routed_route_to_missing(self):
        result = _result(decision=None, route_to="66")
        assert not _check_decision_consistent("Nessun riferimento.", result)


# ── _check_decision_contradicted — Italian negation (critical safety check) ─

class TestCheckDecisionContradicted:

    # Decision=RIMBORSABILE cases

    def test_rimb_contradicted_by_non_rimborsabile_tag(self):
        result = _result("RIMBORSABILE")
        assert _check_decision_contradicted("Il farmaco è NON_RIMBORSABILE.", result)

    def test_rimb_contradicted_by_non_rimborsabile_space(self):
        result = _result("RIMBORSABILE")
        assert _check_decision_contradicted("Il farmaco è NON RIMBORSABILE.", result)

    def test_rimb_not_contradicted_by_itself(self):
        result = _result("RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Il farmaco è RIMBORSABILE secondo la Nota.", result
        )

    # Decision=NON_RIMBORSABILE cases

    def test_non_rimb_contradicted_by_bare_positive(self):
        result = _result("NON_RIMBORSABILE")
        assert _check_decision_contradicted(
            "Il farmaco è RIMBORSABILE per questa indicazione.", result
        )

    def test_non_rimb_not_contradicted_by_own_tag(self):
        result = _result("NON_RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Decisione: NON_RIMBORSABILE.", result
        )

    def test_non_rimb_not_contradicted_by_italian_negation_e(self):
        """'non è rimborsabile' is a correct statement — must NOT flag as contradiction."""
        result = _result("NON_RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Il farmaco non è rimborsabile in questa indicazione.", result
        )

    def test_non_rimb_not_contradicted_by_italian_negation_risulta(self):
        result = _result("NON_RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Il farmaco non risulta rimborsabile secondo la Nota.", result
        )

    def test_non_rimb_not_contradicted_by_italian_negation_appare(self):
        result = _result("NON_RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Il farmaco non appare rimborsabile.", result
        )

    def test_non_rimb_not_contradicted_by_italian_negation_viene(self):
        result = _result("NON_RIMBORSABILE")
        assert not _check_decision_contradicted(
            "Il farmaco non viene rimborsato.", result
        )

    def test_non_determinabile_never_contradicted(self):
        """NON_DETERMINABILE contradiction check not implemented — always False."""
        result = _result("NON_DETERMINABILE")
        assert not _check_decision_contradicted("RIMBORSABILE oppure NON_RIMBORSABILE?", result)


# ── _find_missing_citations ───────────────────────────────────────────────

class TestFindMissingCitations:

    def test_no_blocking_rules_empty(self):
        result = _result("RIMBORSABILE", blocking=[])
        missing = _find_missing_citations("nessuna fonte", result)
        assert missing == []

    def test_citation_present_returns_empty(self):
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        explanation = "5. FONTI\n- nota-97.pdf, p. 3"
        missing = _find_missing_citations(explanation, result)
        assert missing == []

    def test_citation_missing_returns_anchor(self):
        # Use page=8 — "8" does not appear in "nota-13.pdf" so no false-positive match
        br = _blocking_rule(pdf_file="nota-97.pdf", page=8)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        explanation = "5. FONTI\n- nota-13.pdf, p. 5"
        missing = _find_missing_citations(explanation, result)
        assert len(missing) == 1
        assert "nota-97.pdf" in missing[0] or "8" in missing[0]

    def test_multiple_rules_one_missing(self):
        br1 = _blocking_rule("R1", "nota-97.pdf", 3)
        br2 = _blocking_rule("R2", "nota-13.pdf", 5)
        result = _result("NON_RIMBORSABILE", blocking=[br1, br2])
        explanation = "5. FONTI\n- nota-97.pdf, p. 3"
        missing = _find_missing_citations(explanation, result)
        assert len(missing) == 1
        assert "nota-13.pdf" in missing[0] or "5" in missing[0]

    def test_no_fonti_section_searches_whole_text(self):
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        # Page 3 appears in the body, no FONTI section
        explanation = "Il farmaco è escluso come indicato a p.3 del documento."
        missing = _find_missing_citations(explanation, result)
        # p.3 or 3 is in the text → should be considered cited
        assert missing == []

    def test_page_in_fonti_section_suffices(self):
        br = _blocking_rule(pdf_file="nota-66.pdf", page=2)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        explanation = "1. DECISIONE\nNON_RIMBORSABILE\n\n5. FONTI\n- nota-66.pdf, p. 2"
        missing = _find_missing_citations(explanation, result)
        assert missing == []


# ── _find_suspected_hallucinations ───────────────────────────────────────

class TestFindSuspectedHallucinations:

    def test_drug_in_chunks_not_flagged(self):
        result = _result(drug="apixaban")
        chunks = [_chunk(text="il farmaco apixaban è indicato per FANV")]
        halluc = _find_suspected_hallucinations(
            "apixaban è rimborsabile", result, chunks
        )
        assert "apixaban" not in halluc

    def test_drug_not_in_chunks_flagged(self):
        result = _result(drug="apixaban")
        chunks = [_chunk(text="testo normativo generico senza farmaci specifici")]
        halluc = _find_suspected_hallucinations(
            "omeprazolo è indicato per la gastroprotezione", result, chunks
        )
        assert "omeprazolo" in halluc

    def test_evaluated_drug_always_exempt(self):
        """The drug being evaluated is always allowed in the explanation."""
        result = _result(drug="nimesulide")
        chunks = [_chunk(text="testo senza nimesulide")]
        halluc = _find_suspected_hallucinations(
            "nimesulide è controindicata", result, chunks
        )
        assert "nimesulide" not in halluc

    def test_no_known_drugs_in_explanation(self):
        result = _result(drug="apixaban")
        chunks = [_chunk(text="testo normativo")]
        halluc = _find_suspected_hallucinations(
            "il paziente non soddisfa i criteri normativi", result, chunks
        )
        assert halluc == []

    def test_empty_chunks(self):
        result = _result(drug="apixaban")
        halluc = _find_suspected_hallucinations(
            "ibuprofene è controindicato", result, []
        )
        assert "ibuprofene" in halluc


# ── _extract_section ──────────────────────────────────────────────────────

class TestExtractSection:

    def test_extracts_fonti_section(self):
        text = "1. DECISIONE\nRIMBORSABILE\n\n5. FONTI\n- nota-97.pdf, p. 3\n"
        result = _extract_section(text, "FONTI")
        assert result is not None
        assert "nota-97.pdf" in result

    def test_extracts_motivazione_section(self):
        text = "1. DECISIONE\nRIMBORSABILE\n\n2. MOTIVAZIONE\ncriteri soddisfatti\n\n3. RACCOMANDAZIONI\n"
        result = _extract_section(text, "MOTIVAZIONE")
        assert result is not None
        assert "criteri soddisfatti" in result

    def test_section_at_end_of_text(self):
        text = "1. DECISIONE\nNON_RIMBORSABILE\n\n5. FONTI\n- nota-66.pdf, p. 2"
        result = _extract_section(text, "FONTI")
        assert result is not None
        assert "nota-66.pdf" in result

    def test_missing_section_returns_none(self):
        text = "1. DECISIONE\nRIMBORSABILE"
        result = _extract_section(text, "FONTI")
        assert result is None

    def test_case_insensitive(self):
        text = "1. DECISIONE\nok\n\n5. fonti\n- nota.pdf"
        result = _extract_section(text, "FONTI")
        assert result is not None


# ── validate_response — integration ──────────────────────────────────────

class TestValidateResponse:

    def _make_evidence(self, rule_id="R1", exact_text="testo normativo specifico",
                       role="blocking", missing=False):
        return NormativeEvidence(
            evidence_id="test",
            rule_id=rule_id,
            rule_type="EXCL_HARD",
            role=role,
            reason="test",
            pdf_file="nota-97.pdf",
            page=3,
            exact_text=exact_text,
            evidence_missing=missing,
        )

    def test_returns_validation_flags_object(self):
        from rag_pipeline.orchestrator.schemas import ValidationFlags
        result = _result("RIMBORSABILE", blocking=[])
        flags = validate_response("Il farmaco è RIMBORSABILE.", result, [])
        assert isinstance(flags, ValidationFlags)

    def test_consistent_rimborsabile(self):
        result = _result("RIMBORSABILE", blocking=[])
        flags = validate_response("Il farmaco è RIMBORSABILE.", result, [])
        assert flags.decision_consistent is True
        assert flags.decision_contradicted is False

    def test_contradicted_flagged(self):
        result = _result("RIMBORSABILE", blocking=[])
        flags = validate_response(
            "Decisione: NON_RIMBORSABILE in questa indicazione.", result, []
        )
        assert flags.decision_contradicted is True

    def test_all_citations_present(self):
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        explanation = "1. DECISIONE\nNON_RIMBORSABILE\n\n5. FONTI\n- nota-97.pdf, p. 3"
        flags = validate_response(explanation, result, [])
        assert flags.citation_complete is True
        assert flags.missing_citations == []

    def test_empty_evidence_justification_complete(self):
        result = _result("RIMBORSABILE", blocking=[])
        flags = validate_response("Il farmaco è RIMBORSABILE.", result, [], [])
        assert flags.justification_complete is True
