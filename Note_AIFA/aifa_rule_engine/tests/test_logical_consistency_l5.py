"""Unit tests for the L5 semantic-clinical contradiction patterns added in Fase 5.2."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the evaluation package importable from this test file.
_HERE = Path(__file__).resolve().parents[2]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from evaluation.metrics.logical_consistency import _check_l5_semantic_clinical


class TestL5:
    def test_absolute_contraindication_asserted_with_rimborsabile(self) -> None:
        text = "Il farmaco presenta una controindicazione assoluta in questo paziente."
        violations = _check_l5_semantic_clinical(text, "RIMBORSABILE")
        assert any(v["type"] == "L5_semantic_clinical_contradiction" for v in violations)

    def test_absolute_contraindication_with_non_rimborsabile_is_ok(self) -> None:
        text = "Il farmaco presenta una controindicazione assoluta in questo paziente."
        violations = _check_l5_semantic_clinical(text, "NON_RIMBORSABILE")
        assert violations == []

    def test_non_eligible_with_rimborsabile(self) -> None:
        text = "Il paziente non è eleggibile secondo i criteri."
        violations = _check_l5_semantic_clinical(text, "RIMBORSABILE")
        assert violations and violations[0]["type"] == "L5_semantic_clinical_contradiction"

    def test_criteria_satisfied_with_non_rimborsabile(self) -> None:
        text = "Tutti i criteri sono soddisfatti."
        violations = _check_l5_semantic_clinical(text, "NON_RIMBORSABILE")
        assert violations and violations[0]["type"] == "L5_semantic_clinical_contradiction"

    def test_criteria_not_satisfied_with_rimborsabile(self) -> None:
        text = "I criteri non sono soddisfatti."
        violations = _check_l5_semantic_clinical(text, "RIMBORSABILE")
        assert violations and violations[0]["type"] == "L5_semantic_clinical_contradiction"

    def test_no_decision_returns_empty(self) -> None:
        violations = _check_l5_semantic_clinical("any text", "")
        assert violations == []

    def test_unrelated_text_returns_empty(self) -> None:
        text = "Il farmaco è indicato per FANV; CHA2DS2-VASc=4."
        violations = _check_l5_semantic_clinical(text, "RIMBORSABILE")
        assert violations == []
