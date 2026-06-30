"""
Startup validation tests (Phases S1-S5).

Tests:
- DAG cycle detection raises StartupError
- Valid DAG: no error
- BinaryCompNode type_domain validation fails at load time
- Missing normative_anchor raises ValidationError
- Unknown variable in condition raises StartupError
"""
import os
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aifa_rule_engine.engine.rule_loader import (
    REGISTERED_PDF_FILES,
    StartupError,
    load_rules,
)
from aifa_rule_engine.models.conditions import BinaryCompNode, LiteralNode, VarNode
from aifa_rule_engine.models.rules import NormativeAnchor, ScopeRule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_rules(tmp_path: Path, nota_id: str, rules: list[dict]) -> None:
    nota_dir = tmp_path / f"nota_{nota_id}"
    nota_dir.mkdir(parents=True, exist_ok=True)
    with open(nota_dir / "rules.yaml", "w") as f:
        yaml.dump(rules, f)


def minimal_scope_rule(rule_id: str, nota: str, pdf_file: str = "Nota_01.pdf") -> dict:
    return {
        "rule_id": rule_id,
        "rule_type": "SCOPE",
        "nota": nota,
        "description_it": "test",
        "evaluation_order": 1,
        "normative_anchor": {
            "pdf_file": pdf_file,
            "page": 1,
            "section": "test",
        },
        "condition": {
            "operator": "IS_TRUE",
            "var": "trattamento_cronico_fans",
        },
    }


def route_rule(rule_id: str, nota: str, route_to: str) -> dict:
    return {
        "rule_id": rule_id,
        "rule_type": "EXCEPTION",
        "nota": nota,
        "description_it": "test route",
        "evaluation_order": 2,
        "normative_anchor": {
            "pdf_file": "Nota_01.pdf",
            "page": 2,
            "section": "asterisco",
        },
        "outcome_if_true": "ROUTE",
        "route_to_nota": route_to,
        "condition": {
            "operator": "IS_TRUE",
            "var": "trattamento_cronico_fans",
        },
    }


# ---------------------------------------------------------------------------
# G.5 Startup validation tests
# ---------------------------------------------------------------------------

class TestDagCycleDetection:
    def test_cycle_detected(self, tmp_path: Path):
        """Inject cycle: 01→66→01. Expects StartupError with 'cycle'."""
        write_rules(tmp_path, "01", [
            minimal_scope_rule("N01_SCOPE_001", "01"),
            route_rule("N01_EXCEPT_CYCLE", "01", "66"),
        ])
        write_rules(tmp_path, "66", [
            minimal_scope_rule("N66_SCOPE_001", "66", "Nota_66.pdf"),
            route_rule("N66_EXCEPT_CYCLE", "66", "01"),
        ])
        with pytest.raises(StartupError, match="cycle"):
            load_rules(tmp_path)

    def test_valid_linear_chain(self, tmp_path: Path):
        """Valid chain 01→66: no error."""
        write_rules(tmp_path, "01", [
            minimal_scope_rule("N01_SCOPE_001", "01"),
            route_rule("N01_EXCEPT_001", "01", "66"),
        ])
        write_rules(tmp_path, "66", [
            minimal_scope_rule("N66_SCOPE_001", "66", "Nota_66.pdf"),
        ])
        # Should NOT raise
        index = load_rules(tmp_path)
        assert index is not None
        assert len(index.rules) == 3  # 2 rules for nota_01 + 1 for nota_66


class TestTypeValidationAtStartup:
    def test_gt_on_boolean_fails(self):
        """BinaryCompNode GT on boolean type_domain → ValidationError."""
        with pytest.raises(ValidationError, match="numeric"):
            BinaryCompNode(
                operator="GT",
                left=VarNode(operator="VAR", name="x"),
                right=LiteralNode(operator="LITERAL", value=5),
                type_domain="boolean",
            )

    def test_lt_requires_numeric(self):
        with pytest.raises(ValidationError, match="numeric"):
            BinaryCompNode(
                operator="LT",
                left=VarNode(operator="VAR", name="x"),
                right=LiteralNode(operator="LITERAL", value=5),
                type_domain="string",
            )


class TestMissingAnchor:
    def test_rule_without_anchor_fails(self):
        """Rule dict missing normative_anchor → ValidationError."""
        bad_rule = {
            "rule_id": "TEST_001",
            "rule_type": "SCOPE",
            "nota": "01",
            "description_it": "no anchor",
            "evaluation_order": 1,
            # normative_anchor deliberately omitted
            "condition": {
                "operator": "IS_TRUE",
                "var": "trattamento_cronico_fans",
            },
        }
        from pydantic import TypeAdapter

        from aifa_rule_engine.models.rules import RuleSpec
        ta = TypeAdapter(RuleSpec)
        with pytest.raises(ValidationError, match="normative_anchor"):
            ta.validate_python(bad_rule)


class TestUnknownVariable:
    def test_unknown_variable_raises(self, tmp_path: Path):
        """Rule referencing a variable not in DataDictionary → StartupError."""
        write_rules(tmp_path, "01", [
            {
                "rule_id": "N01_SCOPE_BAD",
                "rule_type": "SCOPE",
                "nota": "01",
                "description_it": "bad var",
                "evaluation_order": 1,
                "normative_anchor": {
                    "pdf_file": "Nota_01.pdf",
                    "page": 1,
                    "section": "test",
                },
                "condition": {
                    "operator": "IS_TRUE",
                    "var": "this_variable_does_not_exist_anywhere",
                },
            }
        ])
        with pytest.raises(StartupError, match="unknown variable"):
            load_rules(tmp_path)


class TestDuplicateRuleIds:
    def test_duplicate_rule_id_fails(self, tmp_path: Path):
        """Two rules with same rule_id → StartupError."""
        write_rules(tmp_path, "01", [
            minimal_scope_rule("N01_SCOPE_001", "01"),
            minimal_scope_rule("N01_SCOPE_001", "01"),  # duplicate
        ])
        with pytest.raises(StartupError):
            load_rules(tmp_path)


class TestEvaluationOrderUnique:
    """Audit fix 2026-05-06 (H2): evaluation_order must be unique within
    each (nota, rule_type) bucket — otherwise sort order falls back to glob,
    producing silent non-determinism in evaluation phase ordering."""

    def test_duplicate_evaluation_order_within_nota_type_fails(self, tmp_path: Path):
        r1 = minimal_scope_rule("N01_SCOPE_001", "01")
        r2 = minimal_scope_rule("N01_SCOPE_002", "01")
        # Same evaluation_order on two SCOPE rules of nota 01 — must fail.
        r1["evaluation_order"] = 1
        r2["evaluation_order"] = 1
        write_rules(tmp_path, "01", [r1, r2])
        with pytest.raises(StartupError, match="Duplicate evaluation_order"):
            load_rules(tmp_path)

    def test_unique_evaluation_order_passes(self, tmp_path: Path):
        r1 = minimal_scope_rule("N01_SCOPE_001", "01")
        r2 = minimal_scope_rule("N01_SCOPE_002", "01")
        r1["evaluation_order"] = 1
        r2["evaluation_order"] = 2
        write_rules(tmp_path, "01", [r1, r2])
        # Should NOT raise
        index = load_rules(tmp_path)
        assert len(index.rules) == 2


class TestActualRulesLoad:
    def test_production_rules_load_successfully(self):
        """The production YAML rules must load without errors."""
        rules_dir = Path(__file__).parent.parent / "rules"
        if not rules_dir.exists():
            pytest.skip("Production rules directory not found")
        index = load_rules(rules_dir)
        assert len(index.rules) > 0

    def test_nota_97_rules_count(self):
        """Nota 97 should have at least 15 rules (scope+excl+pathway+guidance)."""
        rules_dir = Path(__file__).parent.parent / "rules"
        if not rules_dir.exists():
            pytest.skip("Production rules directory not found")
        index = load_rules(rules_dir)
        nota_97 = index.rules_for_nota("97")
        assert len(nota_97) >= 15
