"""Audit V4 2026-05-12: _catalog.yaml must declare the exact rule_ids
defined in rules.yaml for the same nota. Drift between the two would
silently desynchronise the engine version metadata."""
from pathlib import Path

import pytest
import yaml

_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


@pytest.mark.parametrize("nota_id", ["01", "13", "66", "97"])
def test_catalog_in_sync_with_rules(nota_id: str) -> None:
    rules_path = _RULES_DIR / f"nota_{nota_id}" / "rules.yaml"
    catalog_path = _RULES_DIR / f"nota_{nota_id}" / "_catalog.yaml"

    rules = yaml.safe_load(rules_path.read_text())
    catalog = yaml.safe_load(catalog_path.read_text())

    rule_ids_from_rules = {r["rule_id"] for r in rules}
    rule_ids_from_catalog = set(catalog.get("rules", []))

    assert rule_ids_from_rules == rule_ids_from_catalog, (
        f"nota_{nota_id}: catalog drift. "
        f"In rules.yaml only: {sorted(rule_ids_from_rules - rule_ids_from_catalog)}; "
        f"in _catalog.yaml only: {sorted(rule_ids_from_catalog - rule_ids_from_rules)}"
    )
