"""
Phase 2 — CDSSOrchestrator
============================

The central pipeline class. Given a patient case, it:
1. Calls the Rule Engine (POST /evaluate or direct Python import)
2. Retrieves relevant regulatory text from ChromaDB (two-stage)
3. Assembles the hardened LLM prompt
4. Calls the LLM (OpenAI or Ollama)
5. Runs post-generation validation
6. Returns a CDSSResponse

Usage (direct Python import — no HTTP):
    from aifa_rule_engine.engine.evaluator import evaluate
    from aifa_rule_engine.engine.rule_loader import load_rules

    rule_index = load_rules("aifa_rule_engine/rules")
    orchestrator = CDSSOrchestrator.from_env(rule_index=rule_index)
    response = await orchestrator.explain(
        nota_id="97", drug_id="apixaban",
        patient_data={...}, clinician_asserted={...}
    )

Usage (via HTTP — Rule Engine running as separate service):
    orchestrator = CDSSOrchestrator.from_env()
    response = await orchestrator.explain(...)
"""
from __future__ import annotations

import hashlib
import logging
import os
import re as _re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from .evidence_utils import (
    _MAX_BLOCKING,
    _MAX_EVIDENCES_TOTAL,
    _MAX_SUPPORTING,
    extract_snippet,
    find_chunks_for_anchor,
    make_evidence_id,
    normalize_pdf_filename,  # also used by _select_chunk_for_anchor for filename normalisation
)
from .prompt_builder import build_prompt
from .retriever import ChromaRetriever, build_retriever
from .schemas import CDSSResponse, NormativeEvidence, RetrievedChunk
from .validators import validate_response

log = logging.getLogger(__name__)


# ── Module-level pre-compiled regex (hot paths in FONTI rewrite + snippet ID) ─
_RE_PUNCT = _re.compile(r'[,;:.!?\'"()\[\]{}]')
_RE_WS = _re.compile(r'\s+')
_RE_PDF_TRAIL_SPACE = _re.compile(r"\s+\.pdf$")
_RE_FONTI_HEADER = _re.compile(r"5\.\s*FONTI\b", flags=_re.IGNORECASE)
_RE_STOP_NUMBERED = _re.compile(r"\n\s*\d+\.\s+[A-Za-zÀ-ÿ]")
_RE_STOP_PROVA = _re.compile(r"\n\s*---\s*PROVA")
_RE_STOP_DATI = _re.compile(r"\n\s*---\s*DATI\s*MANCANTI")


# ── Snippet ID helpers (deterministic, used by evidence boxes + validator) ──

def _normalize_snippet_text(text: str) -> str:
    """Normalize text for snippet ID computation: NFC, lowercase, strip punctuation."""
    text = unicodedata.normalize("NFC", text).lower()
    text = _RE_PUNCT.sub("", text)
    text = _RE_WS.sub(" ", text).strip()
    return text


def _make_snippet_id(snippet: str) -> str:
    """Deterministic 10-char hex snippet ID from SHA-1 of normalized text."""
    return hashlib.sha1(_normalize_snippet_text(snippet).encode()).hexdigest()[:10]


_SELECTOR_STOPWORDS = frozenset({
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "del", "della",
    "dello", "dei", "degli", "delle", "di", "a", "da", "in", "su", "con", "per",
    "tra", "fra", "ed", "e", "o", "che", "cui", "non", "si", "se", "anche",
    "come", "ma", "al", "allo", "alla", "ai", "agli", "alle", "nel", "nello",
    "nella", "nei", "negli", "nelle", "è", "sono", "essere", "stato", "deve",
    "devono", "dovrà", "può", "possono", "ha", "hanno", "questo", "questa",
    "questi", "queste", "ciò", "ad", "sul", "sulla", "sui", "sulle",
})


def _keyword_overlap_ratio(excerpt: str, chunk_text: str) -> float:
    """Fraction of content words of `excerpt` present in `chunk_text`.

    Used as a tie-breaker by `_select_chunk_for_anchor` when the rule's YAML
    excerpt is a paraphrase rather than verbatim PDF text (≈22 of 44 rules).
    """
    import re as _re_local
    words = _re_local.findall(r"\w+", excerpt.lower())
    content = [w for w in words if w not in _SELECTOR_STOPWORDS and len(w) > 3]
    if not content:
        return 0.0
    chunk_lower = chunk_text.lower()
    hits = sum(1 for w in content if w in chunk_lower)
    return hits / len(content)


def _select_chunk_for_anchor(
    chunks: list,                # list[RetrievedChunk]
    pdf_file: str,
    anchor_page: int,
    rule_excerpt: str = "",
):
    """Pick the chunk that best matches a rule's PDF anchor.

    M2/CCS fix (2026-04-30): the previous "first-wins per (pdf, page)" lookup
    sometimes selected a chunk that lived on the same page but in a different
    char range than the rule's verbatim excerpt → the cited evidence box
    pointed to the right page but the wrong sub-region (gap of 600-1600 chars).

    Ranking (lexicographic tuple — higher is better):
      tier:
        4 — single-page chunk on anchor_page that contains excerpt verbatim
        3 — multi-page chunk covering anchor_page that contains excerpt
        2 — single-page chunk on anchor_page (verbatim absent)
        1 — multi-page chunk covering anchor_page (verbatim absent)
      overlap (tie-breaker):
        fraction of excerpt content-words present in chunk text — handles the
        case where the YAML excerpt is a PARAPHRASE of the PDF (the audit
        flags 22 of 44 rules as PARAPHRASE_DOCUMENTED).

    PDF filename matching is normalised via evidence_utils.normalize_pdf_filename
    to handle the 'Nota_66.pdf' vs 'Nota_66 .pdf' (trailing-space) variants.
    Returns the best chunk or None.
    """
    if not chunks:
        return None

    pdf_target = normalize_pdf_filename(pdf_file)
    norm_excerpt = ""
    if rule_excerpt:
        import re as _re_local
        norm_excerpt = _re_local.sub(r"\s+", " ", rule_excerpt.strip().lower())

    candidates = []
    for c in chunks:
        if normalize_pdf_filename(c.pdf_file) != pdf_target:
            continue
        page_end = c.page_end if c.page_end else c.page
        if not (c.page <= anchor_page <= page_end):
            continue
        single_page = (c.page == page_end)
        excerpt_in_chunk = False
        if norm_excerpt:
            import re as _re_local
            chunk_norm = _re_local.sub(r"\s+", " ", c.text.lower())
            excerpt_in_chunk = norm_excerpt in chunk_norm
        overlap = _keyword_overlap_ratio(rule_excerpt, c.text) if rule_excerpt else 0.0
        if single_page and excerpt_in_chunk:
            tier = 4
        elif (not single_page) and excerpt_in_chunk:
            tier = 3
        elif single_page:
            tier = 2
        else:
            tier = 1
        candidates.append(((tier, overlap), c))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


class CDSSOrchestrator:
    """
    Async orchestrator for the full CDSS pipeline.

    Attributes:
        retriever       ChromaRetriever instance
        llm_backend     "openai" | "ollama"
        llm_model       model name (e.g. "gpt-4o-mini" or "llama3.1:8b")
        rule_index      RuleIndex if using direct Python import (optional)
        rule_engine_url URL of the Rule Engine REST API (used if rule_index is None)
    """

    def __init__(
        self,
        retriever: ChromaRetriever,
        llm_backend: str,
        llm_model: str,
        rule_index: Any | None = None,
        rule_engine_url: str = "http://localhost:8000",
    ) -> None:
        from .llm_backends import LLMBackend, build_backend
        self.retriever = retriever
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.rule_index = rule_index
        self.rule_engine_url = rule_engine_url
        # Strategy pattern (refactor RE-M5): the orchestrator holds an
        # LLMBackend strategy instead of branching on `llm_backend` strings
        # at every call site. `_call_llm` simply delegates to it.
        self._llm: LLMBackend = build_backend(llm_backend, llm_model)

    @classmethod
    def from_env(cls, rule_index: Any | None = None) -> CDSSOrchestrator:
        """
        Build an orchestrator from environment variables.

        Required env vars:
            EMBEDDING_MODEL       — sentence-transformers model name
            CHROMA_DB_DIR         — path to ChromaDB persistent storage
            RULE_ENGINE_URL       — URL of the Rule Engine (if not using direct import)

        LLM backend (choose one):
            OPENAI_API_KEY        — enables OpenAI backend
            OLLAMA_BASE_URL       — enables Ollama backend (default: http://localhost:11434)
        """
        retriever = build_retriever()

        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            llm_backend = "openai"
            llm_model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        else:
            llm_backend = "ollama"
            llm_model   = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

        return cls(
            retriever=retriever,
            llm_backend=llm_backend,
            llm_model=llm_model,
            rule_index=rule_index,
            rule_engine_url=os.getenv("RULE_ENGINE_URL", "http://localhost:8000"),
        )

    # ── Main entry point ───────────────────────────────────────────────────────

    async def explain(
        self,
        nota_id: str,
        drug_id: str,
        patient_data: dict[str, Any],
        clinician_asserted: dict[str, Any] | None = None,
    ) -> CDSSResponse:
        """
        Run the full pipeline: evaluate → retrieve → prompt → generate → validate.
        Returns a CDSSResponse with all intermediate and final outputs.
        """
        clinician_asserted = clinician_asserted or {}

        # ── Step 1: Rule Engine ────────────────────────────────────────────────
        log.info("Step 1: Calling Rule Engine (nota=%s, drug=%s)", nota_id, drug_id)
        evaluation_result = await self._call_rule_engine(
            nota_id=nota_id,
            drug_id=drug_id,
            patient_data=patient_data,
            clinician_asserted=clinician_asserted,
        )

        # ── Step 2: Two-stage retrieval ────────────────────────────────────────
        log.info("Step 2: Running two-stage retrieval")
        chunks = self.retriever.retrieve(evaluation_result)

        # ── Step 2b: Build normative evidence (traceability) ──────────────────
        normative_evidence = self._build_normative_evidence(evaluation_result, chunks)

        # ── Step 3: Prompt assembly ────────────────────────────────────────────
        log.info("Step 3: Assembling prompt (%d chunks)", len(chunks))
        prompt = build_prompt(evaluation_result, chunks)

        # ── Step 4: LLM generation ─────────────────────────────────────────────
        log.info("Step 4: Calling LLM (%s via %s)", self.llm_model, self.llm_backend)
        explanation, prompt_tokens, completion_tokens = await self._call_llm(prompt)

        # ── Step 4b: Deterministic FONTI post-compose ──────────────────────────
        explanation = self._compose_deterministic_fonti(
            explanation, normative_evidence, chunks,
        )

        # ── Step 4c: Append evidence boxes (justification verification) ──────
        explanation = self._append_evidence_boxes(
            explanation, normative_evidence, evaluation_result, chunks=chunks,
        )

        # ── Step 5: Post-generation validation ────────────────────────────────
        log.info("Step 5: Validating generated explanation")
        validation = validate_response(
            explanation, evaluation_result, chunks, normative_evidence,
        )

        # ── Step 5b: Decision-contradicted hardening (audit fix C3, 2026-05-06) ─
        # If the LLM produced a textual decision that contradicts the
        # deterministic Rule Engine output, REDACT the explanation: replace it
        # with a safe template that makes the deterministic decision the only
        # source of truth shown to the clinician. Logging-only (the previous
        # behaviour) was insufficient — UIs that displayed `generated_explanation`
        # could still expose the contradictory text to clinical users.
        explanation_redacted = False
        if validation.decision_contradicted:
            decision_str = evaluation_result.reimbursement_decision or "NON_DETERMINABILE"
            log.warning(
                "VALIDATION ALERT: LLM explanation contradicts deterministic decision "
                "(decision=%s) — REDACTING explanation",
                decision_str,
            )
            explanation = (
                f"DECISIONE: {decision_str}\n\n"
                "[Spiegazione automatica indisponibile per contraddizione interna validata. "
                "La decisione sopra è prodotta dal motore deterministico e non può essere "
                "modificata dal modello linguistico. Consultare le evidenze normative allegate "
                "per la giustificazione clinica.]"
            )
            explanation_redacted = True
        if validation.suspected_hallucinations:
            log.warning(
                "VALIDATION ALERT: Suspected hallucinated drug terms: %s",
                validation.suspected_hallucinations,
            )

        return CDSSResponse(
            evaluation_result=evaluation_result,
            retrieved_chunks=chunks,
            retrieval_strategy="anchor_guided + semantic",
            generated_explanation=explanation,
            explanation_redacted=explanation_redacted,
            llm_model=f"{self.llm_backend}/{self.llm_model}",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            generation_timestamp=datetime.now(UTC),
            validation=validation,
            normative_evidence=normative_evidence,
        )

    # ── Normative evidence builder ─────────────────────────────────────────────

    def _build_normative_evidence(
        self,
        result: Any,              # EvaluationResult
        chunks: list[RetrievedChunk],
    ) -> list[NormativeEvidence]:
        """
        Build NormativeEvidence entries from anchor metadata and retrieved chunks.

        For each blocking rule and supporting (passed) rule, finds the chunks that
        back the rule's anchor (pdf_file, page) using find_chunks_for_anchor, then
        extracts a verbatim snippet.  Entries are deduplicated by (pdf_file, page).
        """
        entries: list[NormativeEvidence] = []
        seen_page_keys: set[tuple[str, int]] = set()

        # ── Blocking rules (role="blocking") ──────────────────────────────────
        for br in result.rag_payload.blocking_rules:
            page_key = (normalize_pdf_filename(br.anchor.pdf_file), br.anchor.page)
            if page_key in seen_page_keys:
                continue
            seen_page_keys.add(page_key)

            matched, notes = find_chunks_for_anchor(
                chunks, br.anchor.pdf_file, br.anchor.page
            )
            ev_id = make_evidence_id(br.rule_id, br.anchor.pdf_file, br.anchor.page, "blocking")

            if matched:
                snippet, char_range = extract_snippet([c.text for c in matched])
                entries.append(NormativeEvidence(
                    evidence_id     = ev_id,
                    rule_id         = br.rule_id,
                    rule_type       = br.rule_type,
                    role            = "blocking",
                    reason          = br.reason,
                    pdf_file        = br.anchor.pdf_file,
                    page            = br.anchor.page,
                    section         = br.anchor.section or "",
                    chunk_ids       = [c.chunk_id for c in matched],
                    retrieval_stage = matched[0].retrieval_stage,
                    exact_text      = snippet,
                    char_range      = char_range,
                    evidence_missing = False,
                    notes           = notes,
                ))
            else:
                log.warning(
                    "normative_evidence: no chunks found for blocking rule %s "
                    "anchor %s p.%d",
                    br.rule_id, br.anchor.pdf_file, br.anchor.page,
                )
                entries.append(NormativeEvidence(
                    evidence_id      = ev_id,
                    rule_id          = br.rule_id,
                    rule_type        = br.rule_type,
                    role             = "blocking",
                    reason           = br.reason,
                    pdf_file         = br.anchor.pdf_file,
                    page             = br.anchor.page,
                    section          = br.anchor.section or "",
                    chunk_ids        = [],
                    retrieval_stage  = "",
                    exact_text       = "",
                    char_range       = None,
                    evidence_missing = True,
                    notes            = notes,
                ))

        # ── Supporting rules (role="supporting") ──────────────────────────────
        for pr in result.rag_payload.passed_rules:
            anchor_dict = pr.get("anchor", {})
            pdf_file = anchor_dict.get("pdf_file", "")
            page     = anchor_dict.get("page", 0)
            if not pdf_file or not page:
                continue

            page_key = (normalize_pdf_filename(pdf_file), page)
            if page_key in seen_page_keys:
                continue
            seen_page_keys.add(page_key)

            matched, notes = find_chunks_for_anchor(chunks, pdf_file, page)
            rule_id = pr.get("rule_id", "")
            ev_id = make_evidence_id(rule_id, pdf_file, page, "supporting")

            if matched:
                snippet, char_range = extract_snippet([c.text for c in matched])
                entries.append(NormativeEvidence(
                    evidence_id     = ev_id,
                    rule_id         = rule_id,
                    rule_type       = "",
                    role            = "supporting",
                    reason          = "",
                    pdf_file        = pdf_file,
                    page            = page,
                    section         = anchor_dict.get("section", ""),
                    chunk_ids       = [c.chunk_id for c in matched],
                    retrieval_stage = matched[0].retrieval_stage,
                    exact_text      = snippet,
                    char_range      = char_range,
                    evidence_missing = False,
                    notes           = notes,
                ))
            else:
                log.warning(
                    "normative_evidence: no chunks found for supporting rule %s "
                    "anchor %s p.%d",
                    rule_id, pdf_file, page,
                )
                entries.append(NormativeEvidence(
                    evidence_id      = ev_id,
                    rule_id          = rule_id,
                    rule_type        = "",
                    role             = "supporting",
                    reason           = "",
                    pdf_file         = pdf_file,
                    page             = page,
                    section          = anchor_dict.get("section", ""),
                    chunk_ids        = [],
                    retrieval_stage  = "",
                    exact_text       = "",
                    char_range       = None,
                    evidence_missing = True,
                    notes            = notes,
                ))

        # ── Apply global caps ──────────────────────────────────────────────────
        blocking   = [e for e in entries if e.role == "blocking"][:_MAX_BLOCKING]
        supporting = [e for e in entries if e.role == "supporting"][:_MAX_SUPPORTING]
        return (blocking + supporting)[:_MAX_EVIDENCES_TOTAL]

    # ── Deterministic FONTI post-compose ─────────────────────────────────────

    def _compose_deterministic_fonti(
        self,
        explanation: str,
        normative_evidence: list[NormativeEvidence],
        chunks: list[RetrievedChunk],
    ) -> str:
        """
        Replace the LLM's FONTI section with a deterministic one (v2 granular).

        Output format per source:
            - <pdf>, p. <page>, righe <line_start>-<line_end> (char <cs>-<ce>) [sha:abcdef]

        Granularity rendered only when v2 chunk metadata is available
        (line_start>0, sha256 set). Falls back to v1 (pdf+page) otherwise.

        Bug fix RAG-B4: regex non-greedy + lookahead for next section header,
        avoids "DOTALL .* eats everything" when '5. FONTI' appears earlier.
        """
        def _display_filename(name: str) -> str:
            return _RE_PDF_TRAIL_SPACE.sub(".pdf", name.strip())

        # Build a (pdf, page) → granular-info map from chunks for use when
        # NormativeEvidence has only pdf+page.
        pdf_page_lookup: dict[tuple[str, int], RetrievedChunk] = {}
        for c in chunks:
            key = (_display_filename(c.pdf_file), c.page)
            if key not in pdf_page_lookup:
                pdf_page_lookup[key] = c

        def _format_source(display: str, page: int, line_s: int = 0, line_e: int = 0,
                           cs: int = 0, ce: int = 0, sha: str = "") -> str:
            parts = [f"{display}, p. {page}"]
            # Render granular line/char only if consistent (single-page chunk).
            # Multi-page chunks have line_start in page A, line_end in page B → invalid order.
            if line_s > 0 and line_e >= line_s and ce > cs:
                if line_s == line_e:
                    parts.append(f"riga {line_s}")
                else:
                    parts.append(f"righe {line_s}-{line_e}")
                parts.append(f"char {cs}-{ce}")
            if sha:
                parts.append(f"sha:{sha[:10]}")
            return "- " + ", ".join(parts)

        fonti_lines = ["5. FONTI"]
        seen: set[tuple[str, int]] = set()
        for ev in normative_evidence:
            if ev.evidence_missing:
                continue
            display = _display_filename(ev.pdf_file)
            key = (display, ev.page)
            if key in seen:
                continue
            seen.add(key)
            chunk = pdf_page_lookup.get(key)
            if chunk and chunk.line_start > 0:
                fonti_lines.append(_format_source(
                    display, ev.page,
                    line_s=chunk.line_start, line_e=chunk.line_end,
                    cs=chunk.char_start, ce=chunk.char_end,
                    sha=chunk.sha256,
                ))
            else:
                fonti_lines.append(_format_source(display, ev.page))

        for c in chunks:
            display = _display_filename(c.pdf_file)
            key = (display, c.page)
            if key in seen:
                continue
            seen.add(key)
            if c.line_start > 0:
                fonti_lines.append(_format_source(
                    display, c.page,
                    line_s=c.line_start, line_e=c.line_end,
                    cs=c.char_start, ce=c.char_end,
                    sha=c.sha256,
                ))
            else:
                fonti_lines.append(_format_source(display, c.page))

        fonti_block = "\n".join(fonti_lines)

        # Bug fix RAG-B4: locate '5. FONTI' explicitly, then find next stop
        # marker by scanning forward (more robust than complex regex with
        # case-sensitive lookahead). Patterns pre-compiled at module top.
        start_match = _RE_FONTI_HEADER.search(explanation)
        if start_match:
            start = start_match.start()
            # Find earliest next-section marker AFTER the '5. FONTI' header
            tail = explanation[start_match.end():]
            stop_indices = []
            for pat in (_RE_STOP_NUMBERED, _RE_STOP_PROVA, _RE_STOP_DATI):
                m = pat.search(tail)
                if m:
                    stop_indices.append(start_match.end() + m.start())
            if stop_indices:
                end = min(stop_indices)
                explanation = explanation[:start] + fonti_block + explanation[end:]
            else:
                # No subsequent section: replace from 5. FONTI to EOF
                explanation = explanation[:start] + fonti_block
        else:
            explanation += "\n\n" + fonti_block

        return explanation

    # ── Evidence boxes (justification verification) ───────────────────────────

    def _append_evidence_boxes(
        self,
        explanation: str,
        normative_evidence: list[NormativeEvidence],
        evaluation_result: Any,
        chunks: list[RetrievedChunk] | None = None,
    ) -> str:
        """
        Append structured evidence boxes per blocking rule for verifiable
        snippet-based justification (v2 — granular + human-readable).

        Output format per blocking rule:
            --- PROVA NORMATIVA ---
            Regola: N97_EXCL_HARD_001
              Descrizione: Protesi valvolari meccaniche: i DOAC sono controindicati.
              Razionale: I DOAC non sono approvati per pazienti con protesi...
              Impatto: NON_RIMBORSABILE per DOAC in presenza di protesi meccaniche.
            Fonte: nota-97.pdf, p. 4, righe 23-27 (char 1247-1389)
            Testo verbatim: «DOAC controindicati in presenza di protesi valvolari meccaniche»
            SHA256 chunk: 4f8a91...
            Verificato: SI / NO  (testo presente nel PDF a posizione dichiarata)
        """
        # Map rule_id → rule object (for description_it / structured_motivation
        # AND excerpt-aware chunk selection — M2/CCS fix 2026-04-30)
        rule_lookup: dict[str, Any] = {}
        if self.rule_index is not None:
            try:
                for r in self.rule_index.rules:
                    rule_lookup[r.rule_id] = r
            except Exception:
                pass

        # Build a rule_id → anchor.excerpt map from the payload itself.
        # This is independent of self.rule_index (which is None when the
        # orchestrator runs as an HTTP service, behind FastAPI). M2/CCS fix:
        # without this fallback the selector below has no excerpt to match
        # against and degenerates back to first-wins per (pdf, page).
        rule_excerpt_lookup: dict[str, str] = {}
        try:
            for br in evaluation_result.rag_payload.blocking_rules:
                if br.anchor and getattr(br.anchor, "excerpt", None):
                    rule_excerpt_lookup[br.rule_id] = br.anchor.excerpt
        except Exception:
            pass
        try:
            for pr in evaluation_result.rag_payload.passed_rules:
                rid = pr.get("rule_id")
                anchor = pr.get("anchor", {}) if isinstance(pr, dict) else {}
                excerpt = anchor.get("excerpt") if isinstance(anchor, dict) else None
                if rid and excerpt:
                    rule_excerpt_lookup.setdefault(rid, excerpt)
        except Exception:
            pass

        boxes: list[str] = []
        for ev in normative_evidence:
            if ev.role != "blocking" or ev.evidence_missing:
                continue
            snippet_id = _make_snippet_id(ev.exact_text)
            verbatim = ev.exact_text.strip()

            # Pick the chunk that actually contains the rule's verbatim excerpt
            # (instead of the legacy "first chunk on this page" lookup).
            rule_obj_for_chunk = rule_lookup.get(ev.rule_id)
            rule_excerpt_for_match = rule_excerpt_lookup.get(ev.rule_id, "")
            if not rule_excerpt_for_match and rule_obj_for_chunk is not None:
                anchor = getattr(rule_obj_for_chunk, "normative_anchor", None)
                if anchor is not None:
                    rule_excerpt_for_match = getattr(anchor, "excerpt", "") or ""
            chunk = _select_chunk_for_anchor(
                chunks or [],
                pdf_file=ev.pdf_file,
                anchor_page=ev.page,
                rule_excerpt=rule_excerpt_for_match,
            )

            # Source line — granular if v2 chunk available with line/char tracking.
            # Single-page chunks have unambiguous (char_start, char_end) within
            # the page; for multi-page chunks the char range crosses page
            # boundaries → render only page (no char span) to avoid M2 mis-scoring.
            granular_ok = (
                chunk is not None
                and chunk.line_start > 0
                and chunk.line_end >= chunk.line_start
                and chunk.char_end > chunk.char_start
                and chunk.page == chunk.page_end  # single-page chunk only
            )
            if granular_ok:
                if chunk.line_start == chunk.line_end:
                    line_str = f"riga {chunk.line_start}"
                else:
                    line_str = f"righe {chunk.line_start}-{chunk.line_end}"
                source_line = (
                    f"Fonte: {ev.pdf_file}, p. {ev.page}, {line_str}"
                    f" (char {chunk.char_start}-{chunk.char_end})"
                )
                sha_line = f"SHA256 chunk: {chunk.sha256[:16]}"
            elif chunk and chunk.sha256:
                source_line = f"Fonte: {ev.pdf_file}, p. {ev.page}"
                sha_line = f"SHA256 chunk: {chunk.sha256[:16]}"
            else:
                source_line = f"Fonte: {ev.pdf_file}, p. {ev.page}"
                sha_line = "SHA256 chunk: n/a"

            # Verifica verbatim → testo presente nel chunk?
            verified = "NO"
            if chunk and verbatim:
                # Audit fix 2026-05-06 (W3): normalise unicode dashes (em U+2014,
                # en U+2013, hyphen-minus U+002D) and apply NFKC before
                # comparison. PDF extraction may use em-dash where YAML
                # excerpts use ASCII hyphen, producing spurious "Verificato: NO".
                import unicodedata as _u
                def _norm_dashes(s: str) -> str:
                    s = _u.normalize("NFKC", s)
                    return s.replace("—", "-").replace("–", "-").replace("−", "-")
                v_norm = _norm_dashes(verbatim).lower()
                c_norm = _norm_dashes(chunk.text).lower()
                if v_norm in c_norm:
                    verified = "SI"
                else:
                    # Fuzzy fallback (allow whitespace variants) — pre-compiled
                    norm_v = _RE_WS.sub(" ", v_norm).strip()
                    norm_c = _RE_WS.sub(" ", c_norm).strip()
                    if norm_v in norm_c:
                        verified = "SI"

            # Human-readable rule context from YAML
            rule_obj = rule_lookup.get(ev.rule_id)
            descr_lines = []
            if rule_obj is not None:
                descr_it = getattr(rule_obj, "description_it", "") or ""
                struct_mot = getattr(rule_obj, "structured_motivation", None)
                rationale_it = getattr(struct_mot, "rationale_it", "") if struct_mot else ""
                clinical_impact = getattr(struct_mot, "clinical_impact", "") if struct_mot else ""
                if descr_it:
                    descr_lines.append(f"  Descrizione: {descr_it}")
                if rationale_it:
                    descr_lines.append(f"  Razionale: {rationale_it}")
                if clinical_impact:
                    descr_lines.append(f"  Impatto: {clinical_impact}")

            box = [
                "",
                "--- PROVA NORMATIVA ---",
                f"Regola: {ev.rule_id}",
            ]
            box.extend(descr_lines)
            box.extend([
                f"snippet_id: {snippet_id}",
                source_line,
                f'Testo verbatim: «{verbatim}»',
                sha_line,
                f"Verificato: {verified}",
                "--- FINE ---",
            ])
            boxes.append("\n".join(box))

        # Handle NOT_DETERMINABILE: list missing fields for UNKNOWN blocking rules
        if evaluation_result.reimbursement_decision == "NON_DETERMINABILE":
            missing_fields = evaluation_result.missing_fields_coverage or []
            for br in evaluation_result.rag_payload.blocking_rules:
                if br.rule_evaluated_as == "UNKNOWN" and missing_fields:
                    fields = ", ".join(missing_fields)
                    boxes.append(
                        f"\n--- DATI MANCANTI ---\n"
                        f"Regola: {br.rule_id}\n"
                        f"Campi mancanti: {fields}\n"
                        f"--- FINE DATI MANCANTI ---"
                    )

        if boxes:
            explanation += "\n\n" + "\n".join(boxes)

        return explanation

    # ── Rule Engine call ───────────────────────────────────────────────────────

    async def _call_rule_engine(
        self,
        nota_id: str,
        drug_id: str,
        patient_data: dict[str, Any],
        clinician_asserted: dict[str, Any],
    ):
        """
        Call the Rule Engine.
        Uses direct Python import if rule_index is available (faster, no HTTP overhead).
        Falls back to HTTP if running as a separate service.
        """
        if self.rule_index is not None:
            # ── Direct import (preferred in single-process setups) ─────────────
            from aifa_rule_engine.engine.evaluator import evaluate  # type: ignore
            return evaluate(
                nota_id=nota_id,
                drug_id=drug_id,
                patient_data=patient_data,
                clinician_asserted=clinician_asserted,
                rule_index=self.rule_index,
            )
        else:
            # ── HTTP call (service-to-service in Docker) ───────────────────────
            import httpx
            payload = {
                "schema_version": "3.3",
                "note_id": nota_id,
                "drug_id": drug_id,
                "patient_data": patient_data,
                "clinician_asserted": clinician_asserted,
            }
            # Audit fix V3-H2 (2026-05-06): forward X-API-Key end-to-end so the
            # orchestrator → rule_engine call honours the same authentication
            # gate as the orchestrator's own /explain endpoint. Open-if-unset is
            # respected: when AIFA_API_KEY is empty the rule engine accepts the
            # call (dev-mode), matching the existing _require_api_key contract.
            api_key = os.getenv("AIFA_API_KEY", "")
            headers = {"X-API-Key": api_key} if api_key else {}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.rule_engine_url}/evaluate",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()

            from aifa_rule_engine.models.results import EvaluationResult  # type: ignore
            return EvaluationResult.model_validate(resp.json())

    # ── LLM call ──────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> tuple[str, int, int]:
        """
        Call the configured LLM backend (Strategy pattern).
        Returns (explanation_text, prompt_tokens, completion_tokens).

        The provider-specific code lives in `llm_backends.py` so that
        switching providers (or mocking one in tests) does not require
        touching the orchestrator.
        """
        return await self._llm.complete(prompt)
