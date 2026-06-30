"""
Phase 2 output schemas — CDSSResponse and RetrievedChunk.

These are the final output types of the full CDSS pipeline:
  Rule Engine → Retriever → Prompt Builder → LLM → CDSSResponse
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# Import the Rule Engine output model so CDSSResponse can embed it
from aifa_rule_engine.models.results import EvaluationResult


class RetrievedChunk(BaseModel):
    """A single chunk retrieved from ChromaDB with its metadata and relevance score.

    v2 schema includes char-offset, line tracking, bounding box and SHA256 for
    granular citation rendering ("p.4 righe 23-27 char 1247-1389 «verbatim»").
    """
    chunk_id: str
    text: str
    pdf_file: str
    nota_id: str
    page: int
    page_end: int
    section: str = ""
    score: float
    retrieval_stage: str
    # v2 granular fields (default 0 / empty for v1 chunks for backward compat)
    char_start: int = 0
    char_end: int = 0
    line_start: int = 0
    line_end: int = 0
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    sha256: str = ""
    is_in_table: bool = False
    table_id: str = ""
    schema_version: str = "v1"


class NormativeEvidence(BaseModel):
    """A regulatory text snippet backing a specific rule decision."""
    evidence_id: str                        # deterministic stable id (12-char hex)
    rule_id: str
    rule_type: str
    role: str                               # "blocking" | "supporting"
    reason: str
    pdf_file: str
    page: int
    section: str = ""
    chunk_ids: list[str] = []
    retrieval_stage: str = ""               # "anchor_guided" | "on_demand_anchor"
    exact_text: str                         # verbatim snippet, max ~1000 chars
    char_range: tuple[int, int] | None = None
    evidence_missing: bool = False
    notes: str = ""


class ValidationFlags(BaseModel):
    """Results of post-generation quality checks (Phase 3)."""
    decision_consistent: bool     # LLM output contains correct decision string
    decision_contradicted: bool   # LLM output contains the WRONG decision string
    citation_complete: bool       # All blocking_rule anchors cited in explanation
    missing_citations: list[str]  # anchor refs not found in explanation (page numbers)
    suspected_hallucinations: list[str]  # terms in explanation not in retrieved chunks
    justification_complete: bool = True  # all blocking evidence snippets present
    missing_justification_rules: list[str] = []  # rule_ids without snippet justification
    # Advisory fields (non-blocking)
    missing_supporting_citations: list[str] = []  # passed_rules anchors not cited
    ungrounded_citations: list[str] = []  # citations referencing pages not in retrieved chunks


class CDSSResponse(BaseModel):
    """
    Final output of the full CDSS pipeline.

    Fields:
        evaluation_result   — the deterministic Rule Engine output (never modified)
        retrieved_chunks    — all chunks used to build the LLM prompt
        retrieval_strategy  — description of how chunks were retrieved
        generated_explanation — LLM output in Italian (structured, grounded)
        explanation_redacted — True if `generated_explanation` was REPLACED with
                              a safety template because validation detected a
                              contradiction with the deterministic decision
                              (audit fix C3, 2026-05-06).
        llm_model           — model identifier used for generation
        prompt_tokens       — prompt token count (for cost tracking)
        completion_tokens   — completion token count
        generation_timestamp — UTC timestamp of LLM call
        validation          — post-generation quality check results
    """
    # ── Rule Engine output (immutable — the authoritative decision) ────────────
    evaluation_result: EvaluationResult

    # ── RAG retrieval ──────────────────────────────────────────────────────────
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    retrieval_strategy: str = "anchor_guided + semantic"

    # ── LLM generation ────────────────────────────────────────────────────────
    generated_explanation: str = ""
    explanation_redacted: bool = False
    llm_model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # ── Quality control ────────────────────────────────────────────────────────
    validation: ValidationFlags | None = None

    # ── Normative evidence (traceability) ──────────────────────────────────────
    normative_evidence: list[NormativeEvidence] = []
