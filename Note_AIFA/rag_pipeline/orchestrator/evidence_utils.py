"""
Helpers for building NormativeEvidence entries from retrieved chunks.

Pure functions — no I/O, no LLM calls, no ChromaDB access.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Global caps (imported by cdss_orchestrator) ───────────────────────────────
_MAX_SNIPPET_CHARS   = 1000
_MAX_EVIDENCES_TOTAL = 20
_MAX_BLOCKING        = 10
_MAX_SUPPORTING      = 10


# ── 1a. Filename normalisation ────────────────────────────────────────────────

def normalize_pdf_filename(name: str) -> str:
    """
    Lowercase, strip surrounding whitespace, collapse internal whitespace,
    remove whitespace immediately before the .pdf extension.

    Examples:
        'Nota_66 .pdf' → 'nota_66.pdf'
        'NOTA_97.PDF'  → 'nota_97.pdf'
        'Nota 97.pdf'  → 'nota 97.pdf'
    """
    name = unicodedata.normalize("NFC", name)
    name = name.strip().lower()
    name = re.sub(r'\s+', ' ', name)          # collapse internal spaces
    name = re.sub(r'\s+\.pdf$', '.pdf', name) # remove space before .pdf
    return name


def pdf_stem(name: str) -> str:
    """Return the normalised filename without the .pdf extension."""
    norm = normalize_pdf_filename(name)
    if norm.endswith(".pdf"):
        return norm[:-4]
    return norm


# ── 1b. Chunk lookup with page-offset tolerance ───────────────────────────────

def find_chunks_for_anchor(
    retrieved_chunks: list,          # list[RetrievedChunk]
    pdf_file: str,
    page: int,
    stage_filter: str | None = "anchor_guided",
) -> tuple[list, str]:               # tuple[list[RetrievedChunk], str]
    """
    Return (matched_chunks, notes_str).

    Matching strategy (in order):
      1. Exact:    normalized(chunk.pdf_file) == normalized(pdf_file) AND chunk.page == page
      2. ±1 offset: try page-1, page+1 (handles 0-based vs 1-based mismatch)
      3. Stem only: normalized stem match (drops .pdf extension) for both filenames

    If stage_filter is set, restrict search to chunks with that retrieval_stage.
    The notes_str describes which strategy matched (useful for the NormativeEvidence.notes field).
    """
    pool = retrieved_chunks
    if stage_filter:
        pool = [c for c in pool if c.retrieval_stage == stage_filter]

    norm_target = normalize_pdf_filename(pdf_file)
    stem_target = pdf_stem(pdf_file)

    # Strategy 1: exact match on both filename and page
    matched = [
        c for c in pool
        if normalize_pdf_filename(c.pdf_file) == norm_target and c.page == page
    ]
    if matched:
        return matched, "exact_match"

    # Strategy 2: ±1 page offset (handles 0-based vs 1-based indexing differences)
    for delta in (-1, +1):
        offset_page = page + delta
        matched = [
            c for c in pool
            if normalize_pdf_filename(c.pdf_file) == norm_target and c.page == offset_page
        ]
        if matched:
            return matched, f"page_offset_{delta:+d}"

    # Strategy 3: stem-only match (drops .pdf; tolerates extension case differences)
    matched = [c for c in pool if pdf_stem(c.pdf_file) == stem_target]
    if matched:
        return matched, "stem_match"

    return [], "no_match"


# ── 1c. Snippet extraction ────────────────────────────────────────────────────

def extract_snippet(
    texts: list[str],
    max_chars: int = _MAX_SNIPPET_CHARS,
) -> tuple[str, tuple[int, int] | None]:
    """
    Join texts (in order), then truncate to max_chars at a sentence/word boundary.

    Returns (snippet, char_range) where char_range is (0, len(snippet)) of the joined text.
    Returns ("", None) if texts is empty or all whitespace.
    """
    if not texts:
        return "", None

    joined = " ".join(t.strip() for t in texts if t.strip())
    if not joined:
        return "", None

    if len(joined) <= max_chars:
        return joined, (0, len(joined))

    # Try to truncate at a sentence boundary (. ! ?)
    truncated = joined[:max_chars]
    last_sentence = max(
        truncated.rfind(". "),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_sentence > max_chars // 2:
        snippet = truncated[:last_sentence + 1]
        return snippet, (0, len(snippet))

    # Fall back to a word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        snippet = truncated[:last_space]
        return snippet, (0, len(snippet))

    # Hard truncation as last resort
    return truncated, (0, len(truncated))


# ── 1d. Deterministic evidence_id ─────────────────────────────────────────────

def make_evidence_id(rule_id: str, pdf_file: str, page: int, role: str) -> str:
    """
    Return a stable 12-char hex ID derived from SHA256 of
    '{role}:{rule_id}:{normalized_pdf_file}:{page}'.
    """
    key = f"{role}:{rule_id}:{normalize_pdf_filename(pdf_file)}:{page}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]
