"""
Pytest fixtures shared across test modules.
"""
from pathlib import Path

import pytest

from aifa_rule_engine.engine.evaluator import evaluate
from aifa_rule_engine.engine.rule_loader import RuleIndex, load_rules

RULES_DIR = Path(__file__).parent.parent / "rules"


@pytest.fixture(scope="session")
def rule_index() -> RuleIndex:
    """Load production rules once per session."""
    return load_rules(RULES_DIR)


def run(
    nota_id: str,
    drug_id: str,
    patient_data: dict,
    rule_index: RuleIndex,
    clinician_asserted: dict | None = None,
):
    """Helper: run evaluation and return EvaluationResult."""
    return evaluate(
        nota_id=nota_id,
        drug_id=drug_id,
        patient_data=patient_data,
        clinician_asserted=clinician_asserted or {},
        rule_index=rule_index,
    )
