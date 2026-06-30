"""
Integration tests: gold standard patient cases through the full pipeline.

For each of the 100 gold standard cases across 4 Note (97, 01, 13, 66):
  1. Runs the REAL rule engine (no HTTP, no mock) → EvaluationResult
  2. Verifies the decision matches the gold standard expectation
  3. Runs the REAL orchestrator.explain() with:
       - rule engine result pre-injected (mock _call_rule_engine)
       - retriever mocked (no ChromaDB needed)
       - LLM mocked with a realistic explanation matching the decision
  4. Verifies validation flags: decision_consistent=True, decision_contradicted=False

No external services required (Ollama, ChromaDB, HTTP).
All 100 cases run as individual pytest tests with their gold standard IDs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from rag_pipeline.orchestrator.cdss_orchestrator import CDSSOrchestrator
from rag_pipeline.orchestrator.schemas import CDSSResponse

from aifa_rule_engine.engine.evaluator import evaluate  # type: ignore
from aifa_rule_engine.engine.rule_loader import load_rules  # type: ignore

# ── Paths ──────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.parent.parent
_GOLD_DIR = _ROOT / "evaluation" / "gold_standard"
_RULES_DIR = Path(os.getenv("AIFA_RULES_DIR", str(_ROOT / "aifa_rule_engine" / "rules")))


# ── Load all gold standard cases at import time ────────────────────────────

def _load_all_cases() -> list[dict]:
    cases = []
    for nota in ["97", "01", "13", "66"]:
        path = _GOLD_DIR / f"nota_{nota}_cases.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            cases.extend(data.get("cases", []))
    return cases


_ALL_CASES = _load_all_cases()

# Guard against silent collection of zero parametrized tests when the gold standard
# dataset is missing (e.g. fresh CI checkout without data) — this would otherwise
# pass with "0 tests collected" instead of failing loudly.
assert _ALL_CASES, (
    f"Gold standard dataset is empty — expected JSON cases under {_GOLD_DIR}. "
    "Refusing to collect 0 parametrized tests silently."
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rule_index():
    """Load all rules once for the entire module (shared across all 100 tests)."""
    return load_rules(_RULES_DIR)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_orchestrator(rule_index) -> CDSSOrchestrator:
    orch = CDSSOrchestrator.__new__(CDSSOrchestrator)
    orch.retriever = MagicMock()
    orch.retriever.retrieve.return_value = []
    orch.llm_backend = "ollama"
    orch.llm_model = "llama3.1:8b"
    orch.rule_index = rule_index
    orch.rule_engine_url = "http://localhost:8000"
    return orch


def _build_fake_explanation(decision: str | None, nota_id: str,
                             drug: str, route_to: str | None) -> str:
    """
    Build a minimal but valid LLM explanation that:
    - Contains the exact decision string → decision_consistent = True
    - Does NOT contain the opposite decision → decision_contradicted = False
    - Follows the 5-section format required by validators
    """
    if decision == "RIMBORSABILE":
        decision_line = f"Il farmaco {drug} è RIMBORSABILE secondo la Nota {nota_id}."
    elif decision == "NON_RIMBORSABILE":
        decision_line = (
            f"Il farmaco {drug} è NON_RIMBORSABILE secondo la Nota {nota_id}. "
            f"Il farmaco non è rimborsabile per questa indicazione."
        )
    elif decision == "NON_DETERMINABILE":
        decision_line = (
            f"Il farmaco {drug} è NON_DETERMINABILE: "
            "dati clinici insufficienti per la valutazione."
        )
    else:
        # ROUTED: decision is None, route_to is set
        target = route_to or "?"
        decision_line = (
            f"Il farmaco {drug} deve essere valutato secondo la Nota {target}. "
            f"Indirizzato alla Nota {target}."
        )

    return (
        f"1. DECISIONE\n{decision_line}\n\n"
        f"2. MOTIVAZIONE\n"
        f"I criteri normativi sono stati valutati secondo la Nota {nota_id}.\n\n"
        f"3. RACCOMANDAZIONI\n"
        f"Nessuna raccomandazione aggiuntiva.\n\n"
        f"4. DATI MANCANTI\n"
        f"Dati completi.\n\n"
        f"5. FONTI\n"
        f"- nota-{nota_id}.pdf, p. 1\n"
    )


def _case_id(case: dict) -> str:
    return f"{case['id']}"


# ── Rule engine decision check (pure, no orchestrator) ─────────────────────

@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(c) for c in _ALL_CASES])
def test_rule_engine_decision(case: dict, rule_index):
    """
    Real rule engine on real patient data → decision must match gold standard.
    This test runs without any mock.
    """
    inp = case["input"]
    expected = case["expected_rule_engine"]["reimbursement_decision"]

    result = evaluate(
        nota_id=inp["nota_id"],
        drug_id=inp["drug_id"],
        patient_data=inp.get("patient_data", {}),
        clinician_asserted=inp.get("clinician_asserted", {}),
        rule_index=rule_index,
    )

    assert result.reimbursement_decision == expected, (
        f"[{case['id']}] {case['description']}\n"
        f"  Expected: {expected!r}\n"
        f"  Got:      {result.reimbursement_decision!r}"
    )


# ── Full pipeline check (orchestrator + validators, LLM mocked) ────────────

@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(c) for c in _ALL_CASES])
@pytest.mark.asyncio
async def test_pipeline_response_structure(case: dict, rule_index):
    """
    Full orchestrator.explain() with real rule engine result + mocked LLM.
    Verifies CDSSResponse is well-formed and evaluation_result is preserved.
    """
    inp = case["input"]
    expected_decision = case["expected_rule_engine"]["reimbursement_decision"]

    real_result = evaluate(
        nota_id=inp["nota_id"],
        drug_id=inp["drug_id"],
        patient_data=inp.get("patient_data", {}),
        clinician_asserted=inp.get("clinician_asserted", {}),
        rule_index=rule_index,
    )

    route_to = getattr(real_result, "route_to", None)
    explanation = _build_fake_explanation(
        expected_decision, inp["nota_id"], inp["drug_id"], route_to
    )

    orch = _make_orchestrator(rule_index)
    orch._call_rule_engine = AsyncMock(return_value=real_result)
    orch._call_llm = AsyncMock(return_value=(explanation, 500, 100))

    response = await orch.explain(
        inp["nota_id"],
        inp["drug_id"],
        inp.get("patient_data", {}),
        inp.get("clinician_asserted", {}),
    )

    assert isinstance(response, CDSSResponse), (
        f"[{case['id']}] explain() did not return a CDSSResponse"
    )
    assert response.evaluation_result is real_result, (
        f"[{case['id']}] evaluation_result was not preserved in CDSSResponse"
    )
    assert response.evaluation_result.reimbursement_decision == expected_decision


@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(c) for c in _ALL_CASES])
@pytest.mark.asyncio
async def test_pipeline_validation_consistent(case: dict, rule_index):
    """
    Validators must confirm the fake explanation is consistent with the decision
    and not contradictory. This is the core safety invariant.
    """
    inp = case["input"]
    expected_decision = case["expected_rule_engine"]["reimbursement_decision"]

    real_result = evaluate(
        nota_id=inp["nota_id"],
        drug_id=inp["drug_id"],
        patient_data=inp.get("patient_data", {}),
        clinician_asserted=inp.get("clinician_asserted", {}),
        rule_index=rule_index,
    )

    route_to = getattr(real_result, "route_to", None)
    explanation = _build_fake_explanation(
        expected_decision, inp["nota_id"], inp["drug_id"], route_to
    )

    orch = _make_orchestrator(rule_index)
    orch._call_rule_engine = AsyncMock(return_value=real_result)
    orch._call_llm = AsyncMock(return_value=(explanation, 500, 100))

    response = await orch.explain(
        inp["nota_id"],
        inp["drug_id"],
        inp.get("patient_data", {}),
        inp.get("clinician_asserted", {}),
    )

    assert response.validation is not None, (
        f"[{case['id']}] validation flags missing from CDSSResponse"
    )
    assert response.validation.decision_consistent is True, (
        f"[{case['id']}] decision_consistent=False for decision={expected_decision!r}\n"
        f"  Explanation snippet: {explanation[:200]}"
    )
    assert response.validation.decision_contradicted is False, (
        f"[{case['id']}] decision_contradicted=True for decision={expected_decision!r}\n"
        f"  Explanation snippet: {explanation[:200]}"
    )
