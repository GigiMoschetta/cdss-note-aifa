"""
Rule loading + startup validation phases S1-S6.

Phase S1: YAML parsing
Phase S2: Pydantic schema validation
Phase S3: Cross-rule integrity checks
Phase S4: AST inference + required_variables validation
Phase S5: DAG cycle detection (Fix 3.1)
Phase S6: Rule indexing
"""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..models.conditions import (
    BetweenNode,
    BinaryCompNode,
    BoolNode,
    CountGeqNode,
    InNode,
    IsTrueNode,
    LogicalNode,
    NotNode,
    ScoreRangeGTENode,
    VarNode,
)
from ..models.rules import (
    BaseRule,
    ExceptionRule,
    RuleSpec,
)
from .data_dictionary import FIELD_REGISTRY, is_boolean_field

log = logging.getLogger(__name__)


class StartupError(Exception):
    """Raised when rule loading / validation fails at startup."""


# PDF filenames registered in the normative corpus
REGISTERED_PDF_FILES: frozenset[str] = frozenset({
    "Nota_01.pdf",
    "Nota_66.pdf",
    "nota-97.pdf",
    "nota-97-all-1.pdf",
    "nota-97-all-2.pdf",
    "nota-97-all-3.pdf",
    "nota-13.pdf",
})

KNOWN_NOTA_IDS: frozenset[str] = frozenset({"01", "66", "97", "13"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RuleIndex:
    """Pre-built, validated rule index used at request time."""

    def __init__(
        self,
        rules: list[BaseRule],
        by_nota: dict[str, list[BaseRule]],
        catalog_versions: dict[str, str],
    ) -> None:
        self.rules = rules
        self.by_nota = by_nota
        self.catalog_versions = catalog_versions
        self._by_id: dict[str, BaseRule] = {r.rule_id: r for r in rules}

    def get_by_id(self, rule_id: str) -> BaseRule | None:
        return self._by_id.get(rule_id)

    def rules_for_nota(self, nota_id: str) -> list[BaseRule]:
        return self.by_nota.get(nota_id, [])

    def catalog_version(self, nota_id: str) -> str:
        return self.catalog_versions.get(nota_id, "unknown")


def load_rules(rules_dir: str | Path) -> RuleIndex:
    """Entry point: run all startup phases S1-S6 and return a validated RuleIndex.

    Raises StartupError on any validation failure (fail-fast).
    """
    rules_path = Path(rules_dir)

    # S1: YAML parsing
    raw_rules, catalog_versions = _phase_s1_parse(rules_path)

    # S2: Pydantic validation
    validated = _phase_s2_validate(raw_rules)

    # S3: Cross-rule integrity
    _phase_s3_integrity(validated)

    # S4: AST inference + required_variables check
    _phase_s4_infer_variables(validated)

    # S5: DAG cycle detection
    _phase_s5_dag_validation(validated)

    # S6: Indexing
    index = _phase_s6_index(validated, catalog_versions)

    rule_count = len(validated)
    nota_count = len(index.by_nota)
    log.info(
        f"Startup validation complete. {rule_count} rules loaded across {nota_count} notas."
    )
    return index


# ---------------------------------------------------------------------------
# Phase S1 — YAML parsing
# ---------------------------------------------------------------------------

def _phase_s1_parse(
    rules_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Glob all YAML files under rules_path/{nota_id}/*.yaml and parse them."""
    raw_rules: list[dict[str, Any]] = []
    catalog_versions: dict[str, str] = {}

    if not rules_path.exists():
        raise StartupError(f"Rules directory not found: {rules_path}")

    for nota_dir in sorted(rules_path.iterdir()):
        if not nota_dir.is_dir():
            continue
        nota_id = nota_dir.name.replace("nota_", "").replace("nota", "")
        # Try to read catalog version from a header file
        header_file = nota_dir / "_catalog.yaml"
        if header_file.exists():
            with open(header_file) as f:
                header = yaml.safe_load(f) or {}
            catalog_versions[nota_id] = header.get("version", "unknown")

        for yaml_file in sorted(nota_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            try:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise StartupError(f"YAML parse error in {yaml_file}: {exc}")

            if content is None:
                continue
            if isinstance(content, list):
                raw_rules.extend(content)
            elif isinstance(content, dict):
                raw_rules.append(content)
            else:
                raise StartupError(
                    f"Unexpected YAML structure in {yaml_file}: {type(content)}"
                )

    return raw_rules, catalog_versions


# ---------------------------------------------------------------------------
# Phase S2 — Pydantic validation
# ---------------------------------------------------------------------------

def _phase_s2_validate(raw_rules: list[dict[str, Any]]) -> list[BaseRule]:
    validated: list[BaseRule] = []
    for raw in raw_rules:
        rule_id = raw.get("rule_id", "<unknown>")
        try:
            rule = _parse_rule_spec(raw)
            validated.append(rule)
        except ValidationError as exc:
            raise StartupError(f"Schema validation failed for rule '{rule_id}': {exc}")
        except Exception as exc:
            raise StartupError(
                f"Unexpected error validating rule '{rule_id}': {exc}"
            )
    return validated


def _parse_rule_spec(raw: dict[str, Any]) -> BaseRule:
    """Validate a single raw dict against the RuleSpec discriminated union."""
    from pydantic import TypeAdapter
    ta: Any = TypeAdapter(RuleSpec)
    return ta.validate_python(raw)


# ---------------------------------------------------------------------------
# Phase S3 — Cross-rule integrity
# ---------------------------------------------------------------------------

def _phase_s3_integrity(rules: list[BaseRule]) -> None:
    rule_ids = [r.rule_id for r in rules]

    # Unique IDs
    seen: set[str] = set()
    for rid in rule_ids:
        if rid in seen:
            raise StartupError(f"Duplicate rule_id: '{rid}'")
        seen.add(rid)

    id_set = frozenset(seen)

    rules_using_requires_passed: list[str] = []
    for rule in rules:
        # requires_passed references must resolve
        for dep in rule.requires_passed:
            if dep not in id_set:
                raise StartupError(
                    f"Rule '{rule.rule_id}' requires_passed references "
                    f"unknown rule_id '{dep}'"
                )
        if rule.requires_passed:
            rules_using_requires_passed.append(rule.rule_id)
        # bypasses references must resolve
        for bypass in rule.bypasses:
            if bypass not in id_set:
                raise StartupError(
                    f"Rule '{rule.rule_id}' bypasses references "
                    f"unknown rule_id '{bypass}'"
                )
        # normative_anchor pdf_file must be registered
        pdf = rule.normative_anchor.pdf_file
        if pdf not in REGISTERED_PDF_FILES:
            raise StartupError(
                f"Rule '{rule.rule_id}' normative_anchor.pdf_file '{pdf}' "
                f"is not in the registered PDF corpus. "
                f"Known: {sorted(REGISTERED_PDF_FILES)}"
            )

    if rules_using_requires_passed:
        # `requires_passed` is documentation-only. Inform the maintainer that
        # the field will not affect runtime evaluation; they must rely on
        # `evaluation_order` (or the rule_type phase) for hard ordering.
        log.warning(
            "requires_passed is documentation-only (NOT enforced at runtime). "
            "Rules with non-empty requires_passed: %s. "
            "Use evaluation_order for hard ordering.",
            sorted(rules_using_requires_passed),
        )

    # Audit fix 2026-05-06 (H2): evaluation_order must be unique within each
    # nota and rule_type combo — otherwise sorting collapses to filesystem-glob
    # order, producing silent non-determinism in evaluation. Default 0 is
    # therefore allowed only on a single rule per (nota, type) bucket.
    by_nota_type: dict[tuple[str, str], list[BaseRule]] = {}
    for rule in rules:
        by_nota_type.setdefault((rule.nota, rule.rule_type), []).append(rule)
    for (nota, rule_type), bucket in by_nota_type.items():
        orders = [r.evaluation_order for r in bucket]
        seen_orders: dict[int, str] = {}
        for r in bucket:
            if r.evaluation_order in seen_orders:
                raise StartupError(
                    f"Duplicate evaluation_order={r.evaluation_order} in "
                    f"nota={nota}, rule_type={rule_type}: "
                    f"rules '{seen_orders[r.evaluation_order]}' and '{r.rule_id}'. "
                    "Each rule needs a distinct evaluation_order to guarantee "
                    "deterministic phase ordering."
                )
            seen_orders[r.evaluation_order] = r.rule_id


# ---------------------------------------------------------------------------
# Phase S4 — AST inference + required_variables validation
# ---------------------------------------------------------------------------

def _phase_s4_infer_variables(rules: list[BaseRule]) -> None:
    for rule in rules:
        inferred = _infer_variables(rule.condition)

        # Validate IS_TRUE is only used on boolean fields
        _validate_is_true_domains(rule.condition, rule.rule_id)

        if rule.required_variables:
            yaml_set = frozenset(rule.required_variables)
            if yaml_set != inferred:
                log.warning(
                    f"Rule '{rule.rule_id}': required_variables mismatch. "
                    f"YAML={sorted(yaml_set)} vs inferred={sorted(inferred)}"
                )

        # Check that all inferred variables are in the data dictionary
        for var in inferred:
            if var not in FIELD_REGISTRY:
                raise StartupError(
                    f"Rule '{rule.rule_id}': unknown variable '{var}' "
                    f"(not in DataDictionary)"
                )

        # Promote inferred set to a real Pydantic field on the rule. This
        # replaces the previous `object.__setattr__(rule, "_inferred_variables")`
        # private-attribute pattern with a typed, validated field that
        # `_gather_facts` can rely on without `getattr` fallbacks.
        rule.inferred_variables = inferred


def _infer_variables(node: BoolNode) -> frozenset[str]:
    """Walk the AST and collect all variable references."""
    if isinstance(node, IsTrueNode):
        return frozenset({node.var})
    if isinstance(node, NotNode):
        return _infer_variables(node.operand)
    if isinstance(node, LogicalNode):
        result: frozenset[str] = frozenset()
        for op in node.operands:
            result = result | _infer_variables(op)
        return result
    if isinstance(node, BinaryCompNode):
        return _infer_value_variables(node.left) | _infer_value_variables(node.right)
    if isinstance(node, BetweenNode):
        return frozenset({node.var})
    if isinstance(node, InNode):
        return frozenset({node.var})
    if isinstance(node, CountGeqNode):
        result = frozenset()
        for cond in node.conditions:
            result = result | _infer_variables(cond)
        return result
    if isinstance(node, ScoreRangeGTENode):
        return frozenset({node.score_range_var, node.threshold_var})
    return frozenset()


def _infer_value_variables(node: Any) -> frozenset[str]:
    from ..models.conditions import LiteralNode
    if isinstance(node, VarNode):
        return frozenset({node.name})
    if isinstance(node, LiteralNode):
        return frozenset()
    return frozenset()


def _validate_is_true_domains(node: BoolNode, rule_id: str) -> None:
    """Ensure IS_TRUE is only applied to boolean-typed fields."""
    if isinstance(node, IsTrueNode):
        if not is_boolean_field(node.var):
            # If not in boolean fields but also not in the registry at all,
            # that will be caught by the variable check. If in registry but wrong type,
            # we must raise here.
            from .data_dictionary import FIELD_REGISTRY
            field_type = FIELD_REGISTRY.get(node.var)
            if field_type is not None and field_type != "boolean":
                raise StartupError(
                    f"Rule '{rule_id}': IS_TRUE applied to non-boolean field "
                    f"'{node.var}' (type={field_type}). "
                    "IS_TRUE is only valid for boolean-typed fields."
                )
        return
    if isinstance(node, NotNode):
        _validate_is_true_domains(node.operand, rule_id)
    elif isinstance(node, LogicalNode):
        for op in node.operands:
            _validate_is_true_domains(op, rule_id)
    elif isinstance(node, CountGeqNode):
        for cond in node.conditions:
            _validate_is_true_domains(cond, rule_id)


# ---------------------------------------------------------------------------
# Phase S5 — DAG cycle detection
# ---------------------------------------------------------------------------

def _phase_s5_dag_validation(rules: list[BaseRule]) -> None:
    """Build routing graph and detect cycles via DFS.

    Nodes: nota_id strings
    Edges: route_to_nota links in ExceptionRule
    """
    # Build adjacency list
    graph: dict[str, list[str]] = defaultdict(list)
    for nota in KNOWN_NOTA_IDS:
        graph[nota] = []

    for rule in rules:
        if isinstance(rule, ExceptionRule) and rule.route_to_nota:
            src = rule.nota
            dst = rule.route_to_nota
            if dst not in graph[src]:
                graph[src].append(dst)

    # DFS cycle detection
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycle_path: list[str] = []

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        cycle_path.append(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                if dfs(neighbour):
                    return True
            elif neighbour in rec_stack:
                cycle_path.append(neighbour)
                return True

        rec_stack.discard(node)
        cycle_path.pop()
        return False

    for node in list(graph.keys()):
        if node not in visited:
            if dfs(node):
                raise StartupError(
                    f"Routing cycle detected: {' → '.join(cycle_path)}"
                )


# ---------------------------------------------------------------------------
# Phase S6 — Indexing
# ---------------------------------------------------------------------------

def _phase_s6_index(
    rules: list[BaseRule],
    catalog_versions: dict[str, str],
) -> RuleIndex:
    by_nota: dict[str, list[BaseRule]] = defaultdict(list)
    for rule in rules:
        by_nota[rule.nota].append(rule)

    # Sort each nota's rules by evaluation_order
    for nota_id in by_nota:
        by_nota[nota_id].sort(key=lambda r: r.evaluation_order)

    return RuleIndex(
        rules=rules,
        by_nota=dict(by_nota),
        catalog_versions=catalog_versions,
    )
