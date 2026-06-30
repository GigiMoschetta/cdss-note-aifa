"""
FastAPI application — POST /evaluate endpoint.

Schema version: 3.3
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from .. import ENGINE_VERSION
from ..engine.data_dictionary import FIELD_REGISTRY
from ..engine.drug_normalizer import normalize_drug_id
from ..engine.evaluator import evaluate
from ..engine.rule_loader import RuleIndex, StartupError, load_rules
from ..models.results import EvaluationResult

log = logging.getLogger(__name__)


# ─── API Key authentication (audit fix 2026-05-06, H1) ─────────────────────────
# If AIFA_API_KEY env var is set, requests to /evaluate must include a matching
# X-API-Key header. If unset, the endpoint runs unauthenticated (DEV mode) and
# logs a warning at startup. This is intentional for the thesis triennale demo:
# full OAuth/mTLS is out-of-scope; a shared-secret header is enough to deter
# casual misuse on a LAN-exposed instance.

def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.environ.get("AIFA_API_KEY")
    if expected is None or expected == "":
        # Dev mode: no key configured, allow all.
        return
    if x_api_key != expected:
        # Use 401 (not 403) so clients can negotiate / re-authenticate.
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

ACCEPTED_SCHEMA_VERSIONS = {"3.3"}
KNOWN_NOTA_IDS = {"01", "66", "97", "13"}

# Rules directory: relative to this file → ../../rules
_DEFAULT_RULES_DIR = Path(__file__).parent.parent.parent / "rules"

# Singleton rule index loaded at startup
_rule_index: RuleIndex | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rule_index
    rules_dir = os.environ.get("AIFA_RULES_DIR", str(_DEFAULT_RULES_DIR))
    log.info(f"Loading rules from: {rules_dir}")
    try:
        _rule_index = load_rules(rules_dir)
    except StartupError as exc:
        log.critical(f"Startup failed: {exc}")
        raise
    if not os.environ.get("AIFA_API_KEY"):
        log.warning(
            "AIFA_API_KEY env var is not set — /evaluate is OPEN (DEV mode). "
            "Set AIFA_API_KEY=<secret> before exposing this service."
        )
    yield
    # cleanup (none needed)


app = FastAPI(
    title="AIFA Rule Engine",
    version=ENGINE_VERSION,
    description="Deterministic Rule Engine for AIFA Note (01, 66, 97, 13)",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    schema_version: str
    note_id: str
    drug_id: str
    patient_data: dict[str, Any] = {}
    clinician_asserted: dict[str, Any] = {}

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v not in ACCEPTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version '{v}'. "
                f"Accepted: {sorted(ACCEPTED_SCHEMA_VERSIONS)}"
            )
        return v

    @field_validator("note_id")
    @classmethod
    def validate_note_id(cls, v: str) -> str:
        if v not in KNOWN_NOTA_IDS:
            raise ValueError(
                f"Unknown note_id '{v}'. Known: {sorted(KNOWN_NOTA_IDS)}"
            )
        return v

    @model_validator(mode="after")
    def normalize_drug(self) -> EvaluateRequest:
        try:
            self.drug_id = normalize_drug_id(self.drug_id)
        except ValueError as exc:
            raise ValueError(str(exc))
        return self

    @model_validator(mode="after")
    def whitelist_input_fields(self) -> EvaluateRequest:
        """Audit V4 2026-05-12: reject unknown keys in patient_data and
        clinician_asserted to prevent injection of pre-computed derived
        variables (e.g. cha2ds2vasc_range) that would bypass the engine's
        own computation. Only fields registered in FIELD_REGISTRY are
        accepted; derived/computed scores are filled by compute_derived_variables."""
        allowed = set(FIELD_REGISTRY.keys())
        for src_name, src in (
            ("patient_data", self.patient_data),
            ("clinician_asserted", self.clinician_asserted),
        ):
            extra = sorted(set(src.keys()) - allowed)
            if extra:
                raise ValueError(
                    f"{src_name} contains unrecognised keys: {extra}. "
                    f"Allowed keys are defined in FIELD_REGISTRY "
                    f"(engine/data_dictionary.py)."
                )
        return self


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/evaluate", response_model=EvaluationResult)
async def evaluate_endpoint(
    request: EvaluateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> EvaluationResult:
    _require_api_key(x_api_key)
    if _rule_index is None:
        raise HTTPException(status_code=503, detail="Rule engine not initialized")

    result = evaluate(
        nota_id=request.note_id,
        drug_id=request.drug_id,
        patient_data=request.patient_data,
        clinician_asserted=request.clinician_asserted,
        rule_index=_rule_index,
    )
    return result


@app.get("/health")
async def health() -> dict:
    loaded = _rule_index is not None
    return {
        "status": "ok" if loaded else "initializing",
        "engine_version": ENGINE_VERSION,
        "rules_loaded": len(_rule_index.rules) if _rule_index else 0,
    }
