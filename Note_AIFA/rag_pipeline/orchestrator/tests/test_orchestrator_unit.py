"""
Tests for CDSSOrchestrator internals.

All external dependencies (rule engine, retriever, LLM) are mocked.

Covers:
- _build_normative_evidence: blocking/supporting roles, evidence_missing fallback,
  page_key deduplication, _MAX_BLOCKING / _MAX_SUPPORTING / _MAX_EVIDENCES_TOTAL caps
- _call_llm: backend dispatch (openai/ollama/unknown)
- explain (async): full pipeline with mocks, CDSSResponse fields populated
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from rag_pipeline.orchestrator.cdss_orchestrator import CDSSOrchestrator
from rag_pipeline.orchestrator.evidence_utils import (
    _MAX_BLOCKING,
    _MAX_EVIDENCES_TOTAL,
    _MAX_SUPPORTING,
)
from rag_pipeline.orchestrator.schemas import RetrievedChunk

from aifa_rule_engine.models.results import (  # type: ignore
    EvaluationResult,
    RagPayload,
)


def _real_eval_result(decision="RIMBORSABILE") -> EvaluationResult:
    """Build a minimal but real EvaluationResult that satisfies Pydantic validation."""
    return EvaluationResult(
        decision_status="FINAL",
        reimbursement_decision=decision,
        nota_evaluated="97",
        drug_evaluated="apixaban",
        rag_payload=RagPayload(
            decision_status="FINAL",
            reimbursement_decision=decision,
            blocking_rules=[],
            passed_rules=[],
            unknown_rules=[],
            missing_fields=[],
            computed_scores={},
            clinical_context_summary="paziente con FANV, apixaban",
        ),
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_orchestrator(rule_index=None, llm_backend="ollama"):
    orch = CDSSOrchestrator.__new__(CDSSOrchestrator)
    orch.retriever = MagicMock()
    orch.llm_backend = llm_backend
    orch.llm_model = "llama3.1:8b"
    orch.rule_index = rule_index
    orch.rule_engine_url = "http://localhost:8000"
    return orch


def _chunk(chunk_id="c1", pdf_file="nota-97.pdf", page=3, stage="anchor_guided"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="il farmaco è indicato per pazienti con FANV. Criteri soddisfatti.",
        pdf_file=pdf_file,
        nota_id="97",
        page=page,
        page_end=page,
        score=0.0,
        retrieval_stage=stage,
    )


def _blocking_rule(rule_id="R1", pdf_file="nota-97.pdf", page=3, rule_type="EXCL_HARD"):
    br = MagicMock()
    br.rule_id = rule_id
    br.rule_type = rule_type
    br.reason = "criterio bloccante"
    br.anchor = MagicMock()
    br.anchor.pdf_file = pdf_file
    br.anchor.page = page
    br.anchor.section = ""
    br.rule_evaluated_as = "TRUE"
    return br


def _eval_result(decision="RIMBORSABILE", nota="97", drug="apixaban",
                 blocking=None, passed=None, missing_coverage=None,
                 route_to=None):
    r = MagicMock()
    r.reimbursement_decision = decision
    r.decision_status = "FINAL" if route_to is None else "ROUTED"
    r.nota_evaluated = nota
    r.drug_evaluated = drug
    r.route_to = route_to
    r.route_reason = None
    r.missing_fields_coverage = missing_coverage or []
    r.missing_fields_guidance = []
    r.clinical_flags = []
    r.rag_payload = MagicMock()
    r.rag_payload.blocking_rules = blocking or []
    r.rag_payload.passed_rules = passed or []
    r.rag_payload.computed_scores = {}
    r.rag_payload.clinical_context_summary = "paziente con FANV, apixaban"
    return r


# ── _build_normative_evidence ─────────────────────────────────────────────

class TestBuildNormativeEvidence:

    def test_blocking_rule_with_chunk_evidence_not_missing(self):
        orch = _make_orchestrator()
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        result = _eval_result(blocking=[br])
        chunks = [_chunk("c1", "nota-97.pdf", 3)]

        evidence = orch._build_normative_evidence(result, chunks)

        assert len(evidence) == 1
        ev = evidence[0]
        assert ev.role == "blocking"
        assert ev.evidence_missing is False
        assert ev.rule_id == "R1"
        assert ev.exact_text != ""

    def test_blocking_rule_no_chunk_evidence_missing(self):
        orch = _make_orchestrator()
        # Use a completely different PDF so even stem-only Strategy 3 cannot match
        br = _blocking_rule(pdf_file="nota-97.pdf", page=3)
        result = _eval_result(blocking=[br])
        chunks = [_chunk("c1", "nota-13.pdf", 3)]  # different PDF → no match at all

        evidence = orch._build_normative_evidence(result, chunks)

        assert len(evidence) == 1
        ev = evidence[0]
        assert ev.evidence_missing is True
        assert ev.exact_text == ""
        assert ev.chunk_ids == []

    def test_supporting_rule_with_chunk(self):
        orch = _make_orchestrator()
        result = _eval_result(
            passed=[{"rule_id": "R2", "anchor": {"pdf_file": "nota-97.pdf", "page": 3}}]
        )
        chunks = [_chunk("c1", "nota-97.pdf", 3)]

        evidence = orch._build_normative_evidence(result, chunks)

        assert any(ev.role == "supporting" for ev in evidence)

    def test_supporting_rule_no_pdf_skipped(self):
        orch = _make_orchestrator()
        result = _eval_result(
            passed=[{"rule_id": "R2", "anchor": {"pdf_file": "", "page": 0}}]
        )
        chunks = []

        evidence = orch._build_normative_evidence(result, chunks)
        assert evidence == []

    def test_page_key_deduplication(self):
        """Same (pdf_file, page) from two rules → only one evidence entry."""
        orch = _make_orchestrator()
        br1 = _blocking_rule("R1", "nota-97.pdf", 3)
        br2 = _blocking_rule("R2", "nota-97.pdf", 3)  # same page
        result = _eval_result(blocking=[br1, br2])
        chunks = [_chunk("c1", "nota-97.pdf", 3)]

        evidence = orch._build_normative_evidence(result, chunks)
        assert len(evidence) == 1

    def test_blocking_cap_enforced(self):
        orch = _make_orchestrator()
        blocking = [_blocking_rule(f"R{i}", "nota-97.pdf", i) for i in range(_MAX_BLOCKING + 3)]
        result = _eval_result(blocking=blocking)
        chunks = []

        evidence = orch._build_normative_evidence(result, chunks)
        blocking_ev = [e for e in evidence if e.role == "blocking"]
        assert len(blocking_ev) <= _MAX_BLOCKING

    def test_supporting_cap_enforced(self):
        orch = _make_orchestrator()
        passed = [
            {"rule_id": f"P{i}", "anchor": {"pdf_file": "nota-97.pdf", "page": i + 100}}
            for i in range(_MAX_SUPPORTING + 3)
        ]
        result = _eval_result(passed=passed)
        chunks = []

        evidence = orch._build_normative_evidence(result, chunks)
        supporting_ev = [e for e in evidence if e.role == "supporting"]
        assert len(supporting_ev) <= _MAX_SUPPORTING

    def test_total_cap_enforced(self):
        orch = _make_orchestrator()
        blocking = [_blocking_rule(f"B{i}", "nota-97.pdf", i) for i in range(15)]
        passed = [
            {"rule_id": f"P{i}", "anchor": {"pdf_file": "nota-97.pdf", "page": i + 100}}
            for i in range(15)
        ]
        result = _eval_result(blocking=blocking, passed=passed)
        chunks = []

        evidence = orch._build_normative_evidence(result, chunks)
        assert len(evidence) <= _MAX_EVIDENCES_TOTAL

    def test_blocking_comes_before_supporting(self):
        orch = _make_orchestrator()
        br = _blocking_rule("B1", "nota-97.pdf", 3)
        result = _eval_result(
            blocking=[br],
            passed=[{"rule_id": "P1", "anchor": {"pdf_file": "nota-97.pdf", "page": 5}}],
        )
        chunks = [_chunk("c1", "nota-97.pdf", 3), _chunk("c2", "nota-97.pdf", 5)]

        evidence = orch._build_normative_evidence(result, chunks)
        roles = [ev.role for ev in evidence]
        if "supporting" in roles:
            blocking_idx = roles.index("blocking")
            supporting_idx = roles.index("supporting")
            assert blocking_idx < supporting_idx


# ── _call_llm ─────────────────────────────────────────────────────────────

class TestCallLlm:
    """Strategy-pattern dispatch (refactor RE-M5).

    `_call_llm` no longer branches on `llm_backend` strings — it delegates to
    `self._llm.complete(prompt)`. Tests now stub the backend strategy itself.
    """

    @pytest.mark.asyncio
    async def test_ollama_backend_dispatched(self):
        from rag_pipeline.orchestrator.llm_backends import OllamaBackend
        orch = _make_orchestrator(llm_backend="ollama")
        orch._llm = OllamaBackend("llama3.1:8b")
        orch._llm.complete = AsyncMock(return_value=("text", 100, 50))
        result = await orch._call_llm("test prompt")
        orch._llm.complete.assert_called_once_with("test prompt")
        assert result == ("text", 100, 50)

    @pytest.mark.asyncio
    async def test_openai_backend_dispatched(self):
        from rag_pipeline.orchestrator.llm_backends import OpenAIBackend
        orch = _make_orchestrator(llm_backend="openai")
        orch._llm = OpenAIBackend("gpt-4o-mini")
        orch._llm.complete = AsyncMock(return_value=("text", 200, 80))
        result = await orch._call_llm("test prompt")
        orch._llm.complete.assert_called_once_with("test prompt")
        assert result == ("text", 200, 80)

    def test_unknown_backend_raises(self):
        from rag_pipeline.orchestrator.llm_backends import build_backend
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            build_backend("unknown_llm", "any-model")


# ── explain — full pipeline (async) ──────────────────────────────────────

class TestExplain:

    def _setup_orch_with_mocks(self, decision="RIMBORSABILE"):
        """Build orchestrator with all external calls mocked.

        CDSSResponse.evaluation_result requires a real EvaluationResult (Pydantic
        won't accept a MagicMock), so we build a minimal but valid instance.
        """
        orch = _make_orchestrator(rule_index=MagicMock())

        real_result = _real_eval_result(decision)
        orch._call_rule_engine = AsyncMock(return_value=real_result)
        orch.retriever.retrieve.return_value = [_chunk()]
        orch._call_llm = AsyncMock(
            return_value=(f"1. DECISIONE\n{decision}\n\n2. MOTIVAZIONE\ntesto\n\n"
                          "3. RACCOMANDAZIONI\nNessuna.\n\n"
                          "4. DATI MANCANTI\nDati completi.\n\n"
                          "5. FONTI\n- nota-97.pdf, p. 3",
                          500, 100)
        )
        return orch, real_result

    @pytest.mark.asyncio
    async def test_explain_returns_cdss_response(self):
        from rag_pipeline.orchestrator.schemas import CDSSResponse
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert isinstance(response, CDSSResponse)

    @pytest.mark.asyncio
    async def test_explain_evaluation_result_preserved(self):
        orch, eval_result = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert response.evaluation_result is eval_result

    @pytest.mark.asyncio
    async def test_explain_explanation_populated(self):
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert "RIMBORSABILE" in response.generated_explanation

    @pytest.mark.asyncio
    async def test_explain_validation_present(self):
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert response.validation is not None
        assert response.validation.decision_consistent is True

    @pytest.mark.asyncio
    async def test_explain_normative_evidence_populated(self):
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert isinstance(response.normative_evidence, list)

    @pytest.mark.asyncio
    async def test_explain_chunks_stored(self):
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert len(response.retrieved_chunks) >= 1

    @pytest.mark.asyncio
    async def test_explain_token_counts_stored(self):
        orch, _ = self._setup_orch_with_mocks("RIMBORSABILE")
        response = await orch.explain("97", "apixaban", {})
        assert response.prompt_tokens == 500
        assert response.completion_tokens == 100
