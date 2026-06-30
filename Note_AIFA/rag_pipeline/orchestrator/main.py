"""
Phase 2 — Orchestrator FastAPI Service
========================================

Exposes POST /explain — the single public endpoint of the CDSS pipeline.

Receives a patient case → returns CDSSResponse (decision + explanation + sources).

Startup:
    The CDSSOrchestrator is initialized in the FastAPI lifespan.
    If AIFA_RULES_DIR is set, the Rule Engine is loaded directly (no HTTP).
    Otherwise it calls the Rule Engine via RULE_ENGINE_URL.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .cdss_orchestrator import CDSSOrchestrator
from .schemas import CDSSResponse

log = logging.getLogger(__name__)

_orchestrator: CDSSOrchestrator | None = None


def _require_api_key(x_api_key: str | None) -> None:
    """API key gate (audit fix 2026-05-06, H1). Open if AIFA_API_KEY is unset."""
    expected = os.environ.get("AIFA_API_KEY")
    if expected is None or expected == "":
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    log.info("Initializing CDSSOrchestrator...")

    # Try to load the Rule Engine directly (avoids HTTP round-trip latency)
    rules_dir = os.getenv("AIFA_RULES_DIR")
    rule_index = None
    if rules_dir and Path(rules_dir).is_dir():
        try:
            from aifa_rule_engine.engine.rule_loader import load_rules  # type: ignore
            rule_index = load_rules(rules_dir)
            log.info("Rule Engine loaded directly from %s", rules_dir)
        except Exception as exc:
            log.warning("Direct Rule Engine load failed (%s) — falling back to HTTP", exc)

    _orchestrator = CDSSOrchestrator.from_env(rule_index=rule_index)
    log.info("CDSSOrchestrator ready. LLM: %s/%s", _orchestrator.llm_backend, _orchestrator.llm_model)
    yield


app = FastAPI(
    title="AIFA CDSS — Orchestrator",
    version="0.1.0",
    description="Phase 2: RAG + LLM explanation pipeline for AIFA Note reimbursement decisions",
    lifespan=lifespan,
)


# ── Request schema ────────────────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    """Input to the orchestrator endpoint — mirrors POST /evaluate + schema_version."""
    schema_version: str = "3.3"
    note_id: str                          # "97" | "01" | "13" | "66"
    drug_id: str
    patient_data: dict[str, Any] = {}
    clinician_asserted: dict[str, Any] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/explain", response_model=CDSSResponse)
async def explain_endpoint(
    request: ExplainRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> CDSSResponse:
    """
    Full CDSS pipeline:
    1. Evaluate reimbursement (Rule Engine)
    2. Retrieve regulatory text (ChromaDB)
    3. Generate explanation (LLM)
    4. Validate output (post-generation checks)
    """
    _require_api_key(x_api_key)
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        return await _orchestrator.explain(
            nota_id=request.note_id,
            drug_id=request.drug_id,
            patient_data=request.patient_data,
            clinician_asserted=request.clinician_asserted,
        )
    except Exception as exc:
        # Audit fix 2026-05-06: avoid leaking patient_data via str(exc) in 5xx
        # responses. Log the full traceback server-side, return a generic
        # detail to the client.
        log.exception("Orchestrator error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Internal orchestrator error (see server logs).",
        ) from exc


@app.get("/health")
async def health() -> dict:
    loaded = _orchestrator is not None
    return {
        "status": "ok" if loaded else "initializing",
        "version": "0.1.0",
        "llm_backend": _orchestrator.llm_backend if _orchestrator else None,
        "llm_model":   _orchestrator.llm_model   if _orchestrator else None,
    }
