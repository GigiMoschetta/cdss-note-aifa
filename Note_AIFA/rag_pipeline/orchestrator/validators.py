"""
Phase 3 — Post-Generation Validators
======================================

Deterministic (zero LLM calls) checks applied after the LLM produces its explanation.

Checks:
1. Decision consistency  — explanation contains the correct decision string
                           and does NOT contain the opposite one.
2. Citation completeness — every blocking_rule anchor's page number appears
                           in the FONTI section of the explanation.
3. Hallucination flag    — drug names or clinical terms present in the explanation
                           but NOT in the retrieved chunks or in the RagPayload.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from aifa_rule_engine.models.results import EvaluationResult  # type: ignore[attr-defined]

from .schemas import RetrievedChunk, ValidationFlags

# ── Decision string sets ───────────────────────────────────────────────────────
_POSITIVE_DECISION_STRINGS = {"RIMBORSABILE"}
_NEGATIVE_DECISION_STRINGS = {"NON_RIMBORSABILE", "NON RIMBORSABILE"}
_UNCERTAIN_STRINGS         = {"NON_DETERMINABILE", "NON DETERMINABILE"}

# Lexical drug-name spotter: a heuristic word-list, NOT a hallucination
# detector in the semantic sense. Detects mentions of drug names whose
# string form is recognized but does not appear in the retrieved chunks.
#
# Renaming (Bug fix RAG-B5): the previous name `_KNOWN_DRUG_TERMS` and
# the metric "hallucination_rate" overstated the capability. This is a
# DRUG-NAME LEXICAL CHECK with these documented limitations:
#   - covers ~55 hardcoded names, drift vs DrugId enum
#   - substring search → upgraded to word-boundary regex (RAG-B3 fix)
#   - cannot detect threshold/criteria hallucinations (e.g. "score ≥3" invented)
#   - cannot detect causal/clinical hallucinations
# The semantic faithfulness metric (M3 — NLI italiano) is the proper tool
# for that. This list complements but does not replace M3.
_KNOWN_DRUG_HEURISTIC = {
    # Nota 97 — Anticoagulanti
    "apixaban", "dabigatran", "rivaroxaban", "edoxaban",
    "warfarin", "acenocumarolo",
    # Nota 01 — PPI / gastroprotettori
    "omeprazolo", "pantoprazolo", "lansoprazolo", "esomeprazolo",
    "rabeprazolo", "misoprostolo",
    # Nota 66 — FANS (lista chiusa PDF + ibuprofene_codeina)
    "diclofenac", "diclofenac_misoprostolo",
    "ibuprofene", "ibuprofene_codeina", "codeina",
    "ketoprofene", "naprossene", "nimesulide", "meloxicam",
    "piroxicam", "indometacina", "celecoxib", "etoricoxib",
    "aceclofenac", "dexibuprofene", "flurbiprofene", "sulindac",
    "tenoxicam", "lornoxicam", "acemetacina", "acido_mefenamico",
    "acido_tiaprofenico", "cinnoxicam", "dexketoprofene",
    "fentiazac", "furprofene", "ketorolac", "oxaprozina",
    "proglumetacina", "amtolmetina_guacile", "nabumetone",
    # Nota 13 — Ipolipemizzanti
    "atorvastatina", "rosuvastatina", "simvastatina",
    "pravastatina", "fluvastatina", "lovastatina",
    "ezetimibe", "ezetimibe_simvastatina",
    "bezafibrato", "fenofibrato", "gemfibrozil",
    "pufa-n3", "pufa_n3",
    # Common Italian drug names that LLM may hallucinate from pretraining
    "paracetamolo", "aspirina", "ranitidina", "famotidina",
    "pitavastatina",  # not in DrugId but commonly mentioned
    "fibrati", "niacina",  # class names
}


def validate_response(
    explanation: str,
    result: EvaluationResult,
    chunks: list[RetrievedChunk],
    normative_evidence: list | None = None,
) -> ValidationFlags:
    """
    Run all post-generation checks and return a ValidationFlags object.

    Parameters:
        explanation         — the raw string output from the LLM
        result              — the EvaluationResult from the Rule Engine
        chunks              — the RetrievedChunks used to build the prompt
        normative_evidence  — NormativeEvidence entries (for justification check)
    """
    explanation_lower = explanation.lower()

    justification_ok = True
    missing_justification: list[str] = []
    if normative_evidence:
        justification_ok, missing_justification = check_justification_snippets(
            explanation, normative_evidence,
        )

    # Advisory: check supporting rules' citations
    missing_supporting = _find_missing_supporting_citations(explanation, result)

    # Advisory: provenance cross-validation (cited pages vs retrieved chunks)
    ungrounded = _find_ungrounded_citations(explanation, result, chunks)

    return ValidationFlags(
        decision_consistent=_check_decision_consistent(explanation, result),
        decision_contradicted=_check_decision_contradicted(explanation, result),
        citation_complete=_check_citation_complete(explanation, result),
        missing_citations=_find_missing_citations(explanation, result),
        suspected_hallucinations=_find_suspected_hallucinations(
            explanation_lower, result, chunks
        ),
        justification_complete=justification_ok,
        missing_justification_rules=missing_justification,
        missing_supporting_citations=missing_supporting,
        ungrounded_citations=ungrounded,
    )


# ── Check 1: Decision consistency ─────────────────────────────────────────────

def _check_decision_consistent(explanation: str, result: EvaluationResult) -> bool:
    """
    Verify that the expected decision string appears somewhere in the explanation.
    Returns True if consistent.
    """
    decision = result.reimbursement_decision
    if decision is None:
        # ROUTED case — check for the route information
        route = result.route_to or ""
        return route in explanation

    return _decision_in_text(decision, explanation)


def _check_decision_contradicted(explanation: str, result: EvaluationResult) -> bool:
    """
    Check whether the OPPOSITE decision appears in the explanation.
    Returns True if the explanation is contradictory (bad).

    Bug fix RAG-B2: extended pattern coverage for negation forms previously
    missed: "potrebbe non essere", "non sarebbe", "non viene rimborsato",
    "non sarà rimborsabile", "non risulterebbe", "il SSN non lo rimborsa",
    plus conditional/subjunctive variants.
    """
    decision = result.reimbursement_decision
    if decision is None:
        return False

    if decision == "RIMBORSABILE":
        for neg in _NEGATIVE_DECISION_STRINGS:
            if neg.lower() in explanation.lower():
                return True
    elif decision == "NON_RIMBORSABILE":
        text_no_non = re.sub(r"NON[_\s]RIMBORSABILE", "", explanation, flags=re.IGNORECASE)
        # Extended negation patterns
        neg_patterns = [
            r"non\s+(?:è|e|risulta|appare|viene|sarà|risulterebbe|sarebbe|verrebbe|verrà)\s+(?:più\s+)?rimborsabile",
            r"potrebbe\s+non\s+essere\s+rimborsabile",
            r"il\s+SSN\s+non\s+(?:lo|la|li|le)\s+rimborsa",
            r"non\s+(?:lo|la|li|le)\s+(?:rimborsa|copre|paga)",
            r"non\s+(?:è|risulta)\s+(?:più\s+)?(?:a\s+)?carico\s+del\s+SSN",
            r"farmaco\s+non\s+rimbors",
        ]
        for pat in neg_patterns:
            text_no_non = re.sub(pat, "", text_no_non, flags=re.IGNORECASE)
        if re.search(r"\bRIMBORSABILE\b", text_no_non, flags=re.IGNORECASE):
            return True
    return False


def _decision_in_text(decision: str, text: str) -> bool:
    variants = {
        decision,
        decision.replace("_", " "),
        decision.replace("_", ""),
    }
    text_upper = text.upper()
    return any(v.upper() in text_upper for v in variants)


# ── Check 2: Citation completeness ────────────────────────────────────────────

def _check_citation_complete(explanation: str, result: EvaluationResult) -> bool:
    return len(_find_missing_citations(explanation, result)) == 0


def _find_missing_citations(
    explanation: str,
    result: EvaluationResult,
) -> list[str]:
    """
    Return list of anchor references (pdf_file + page) from blocking_rules
    that do NOT appear in the FONTI section.

    Bug fix RAG-B1: previous version checked `page not in fonti_section` as
    a substring, which caused false negatives when the page number happened
    to be a substring of an unrelated number (e.g. page="3" matching "13"
    in "Nota_13"). v2 uses regex with word/anchor boundaries:
        - exact filename match (fragile but unambiguous), OR
        - regex pattern  r"p\\.\\s*<page>(?!\\d)"  (strict page boundary)
    """
    import re

    missing: list[str] = []
    fonti_section = _extract_section(explanation, "FONTI") or explanation

    for br in result.rag_payload.blocking_rules:
        pdf = br.anchor.pdf_file
        page = str(br.anchor.page)
        # Boundary-aware page reference detection
        page_re = re.compile(rf"p\.\s*{re.escape(page)}(?!\d)", re.IGNORECASE)
        if pdf not in fonti_section and not page_re.search(fonti_section):
            missing.append(f"{pdf} p.{page}")

    return missing


def _find_missing_supporting_citations(
    explanation: str,
    result: EvaluationResult,
) -> list[str]:
    """
    Return list of anchor references from passed_rules that do NOT appear
    in the FONTI section. Advisory only (not blocking).
    """
    missing: list[str] = []
    fonti_section = _extract_section(explanation, "FONTI") or explanation

    for pr in result.rag_payload.passed_rules:
        anchor_dict = pr.get("anchor", {})
        pdf = anchor_dict.get("pdf_file", "")
        page = str(anchor_dict.get("page", ""))
        if not pdf or not page:
            continue
        if pdf not in fonti_section and f"p.{page}" not in fonti_section and f"p. {page}" not in fonti_section:
            missing.append(f"{pdf} p.{page}")

    return missing


def _find_ungrounded_citations(
    explanation: str,
    result: EvaluationResult,
    chunks: list[RetrievedChunk],
) -> list[str]:
    """
    Find citations in FONTI that reference pages NOT present in retrieved chunks.
    Advisory only — catches cases where the LLM hallucinates a source page.
    Uses parse_fonti() for structured extraction.
    """
    fonti_section = _extract_section(explanation, "FONTI")
    if not fonti_section:
        return []

    # Collect known PDFs from chunks
    known_pdfs = list({c.pdf_file for c in chunks})
    citations = parse_fonti(fonti_section, known_pdfs)

    # Build set of (pdf_file, page) from retrieved chunks
    chunk_pages: set[tuple[str, int]] = set()
    for c in chunks:
        chunk_pages.add((c.pdf_file.lower(), c.page))
        if c.page_end and c.page_end != c.page:
            for p in range(c.page, c.page_end + 1):
                chunk_pages.add((c.pdf_file.lower(), p))

    ungrounded: list[str] = []
    for cit in citations:
        covered = any(
            (cit.pdf_file.lower(), p) in chunk_pages
            for p in range(cit.page_start, cit.page_end + 1)
        )
        if not covered:
            ungrounded.append(f"{cit.pdf_file} p.{cit.page_start}")

    return ungrounded


def _extract_section(text: str, section_title: str) -> str | None:
    """Extract text after a numbered section header (e.g. '5. FONTI')."""
    pattern = rf"\d+\.\s*{re.escape(section_title)}(.*?)(?=\d+\.\s+[A-Z]|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


# ── Check 3: Suspected hallucinations ─────────────────────────────────────────

def _find_suspected_hallucinations(
    explanation_lower: str,
    result: EvaluationResult,
    chunks: list[RetrievedChunk],
) -> list[str]:
    """
    Flag drug names mentioned in the explanation that are not in the retrieved
    chunks (lexical-only heuristic — see _KNOWN_DRUG_HEURISTIC docstring).

    Bug fix RAG-B3: word-boundary regex match (\\b...\\b) instead of substring,
    avoids false positives like 'codeina' matching 'ibuprofene_codeina' as a
    different word, and false negatives like 'apixabàn' (accented) collapsing
    by NFKC normalization.
    """
    import unicodedata
    drug_evaluated = result.drug_evaluated.lower()

    def _norm(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()

    explanation_norm = _norm(explanation_lower)
    chunk_texts_norm = _norm(" ".join(c.text for c in chunks))

    hallucinated: list[str] = []
    for term in _KNOWN_DRUG_HEURISTIC:
        if term == drug_evaluated:
            continue
        term_norm = _norm(term).replace("_", "[ _-]?")
        # Word-boundary match
        word_re = re.compile(rf"\b{term_norm}\b", re.IGNORECASE)
        if word_re.search(explanation_norm) and not word_re.search(chunk_texts_norm):
            hallucinated.append(term)

    return hallucinated


# ── parse_fonti — analytics only (NOT used for validation) ────────────────

@dataclass(frozen=True)
class ParsedCitation:
    """Structured representation of a single citation in the FONTI section."""
    pdf_file: str
    page_start: int
    page_end: int       # same as page_start for single-page refs


def parse_fonti(fonti_text: str, known_pdfs: list[str]) -> list[ParsedCitation]:
    """
    Parse the FONTI section into structured citations.

    Analytics use only — NOT used for validation (deterministic FONTI
    guarantees correctness by construction).
    """
    citations: list[ParsedCitation] = []
    fonti_lower = fonti_text.lower()
    matched_pdfs = [pdf for pdf in known_pdfs if pdf.lower() in fonti_lower]

    range_pat = re.compile(
        r"(?:pagine|pp?\.?|pag\.?)\s*(\d+)\s*[-–]\s*(\d+)", re.IGNORECASE
    )
    single_pat = re.compile(
        r"(?:pagina|pag\.?|pp?\.?)\s*(\d+)(?!\s*[-–]\s*\d)", re.IGNORECASE
    )

    for pdf in matched_pdfs:
        for m in range_pat.finditer(fonti_text):
            citations.append(ParsedCitation(pdf, int(m.group(1)), int(m.group(2))))
        for m in single_pat.finditer(fonti_text):
            pg = int(m.group(1))
            citations.append(ParsedCitation(pdf, pg, pg))

    return citations


def _citation_covers(citations: list[ParsedCitation], pdf: str, page: int) -> bool:
    """Check whether any citation covers the given (pdf, page)."""
    pdf_lower = pdf.lower()
    return any(
        c.pdf_file.lower() == pdf_lower and c.page_start <= page <= c.page_end
        for c in citations
    )


# ── Justification snippet verification ────────────────────────────────────

def _normalize_snippet_text(text: str) -> str:
    """Normalize text for snippet matching: NFC, lowercase, strip punctuation."""
    import unicodedata
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r'[,;:.!?\'"()\[\]{}]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _make_snippet_id(snippet: str) -> str:
    """Deterministic 10-char hex snippet ID from SHA-1 of normalized text."""
    import hashlib
    return hashlib.sha1(_normalize_snippet_text(snippet).encode()).hexdigest()[:10]


# Italian stopwords for content-word check (audit fix 2026-05-06: trigram-only
# match was too permissive — see _check_content_word_present below).
_IT_STOPWORDS_JUSTIFICATION = frozenset({
    "il", "la", "lo", "i", "gli", "le", "un", "una", "uno", "di", "da", "in",
    "con", "per", "su", "sul", "sulla", "sui", "sulle", "fra", "tra", "a", "ad",
    "e", "o", "ma", "se", "che", "chi", "non", "è", "sono", "ha", "hanno",
    "del", "dello", "della", "dei", "degli", "delle", "al", "alla", "alle",
    "agli", "ai", "nel", "nella", "nei", "negli", "nelle", "sopra", "sotto",
    "questo", "questa", "questi", "queste", "quel", "quella", "quei", "quelle",
    "tutto", "tutta", "tutti", "tutte", "stato", "essere", "avere", "fare",
})


def _content_words_ordered(normalized_text: str, min_len: int = 6) -> list[str]:
    """Content words in order, filtered by stopword set and minimum length.

    Order matters: in Italian normative phrasing the *most specific* clinical
    qualifier tends to appear LAST in the clause (e.g. "controindicato nei
    pazienti epatopatici" — "epatopatici" is the discriminating term).
    """
    return [
        w for w in normalized_text.split()
        if len(w) >= min_len and w not in _IT_STOPWORDS_JUSTIFICATION
    ]


def _discriminative_word(snippet_norm: str) -> str | None:
    """Return the rightmost content word as the discriminating term.

    AIFA normative phrasing follows N→specifier order ("pazienti epatopatici",
    "anticoagulante orale", "scompenso cardiaco severo"). The final content
    word usually carries the clinical scope that differentiates one rule from
    another. Returns None if no content word qualifies.
    """
    cw = _content_words_ordered(snippet_norm)
    return cw[-1] if cw else None


def check_justification_snippets(
    explanation: str,
    normative_evidence: list,
) -> tuple[bool, list[str]]:
    """
    Verify that each blocking normative evidence snippet is present
    in the explanation.

    Verification tiers (audit fix 2026-05-06, finding A4-P0-1 / Task #23):
    1. PRIMARY:  snippet_id literal present in explanation → robust justification.
    2. FALLBACK: simultaneously
        - at least one trigram from the evidence appears in the explanation, AND
        - the *discriminative content word* (the last non-stopword ≥6 chars)
          from the evidence appears in the explanation.
       Trigram-only matching is too lax: a generic phrase like "il farmaco è
       controindicato nei pazienti" matches boilerplate but does not prove
       the explanation cites the SPECIFIC clinical scope of the rule. AIFA
       normative phrasing places the discriminative qualifier last
       (e.g. "pazienti EPATOPATICI", "anticoagulante ORALE"), so requiring
       its presence in the explanation reliably catches the failure mode
       where an LLM substitutes the critical term with a generic one
       ("epatopatici" → "patologia"), preserving boilerplate shape but
       hallucinating the clinical scope.

    Returns (all_justified, list_of_missing_rule_ids).
    """
    missing: list[str] = []
    explanation_norm = _normalize_snippet_text(explanation)
    explanation_words = set(explanation_norm.split())

    for ev in normative_evidence:
        if ev.role != "blocking" or ev.evidence_missing:
            continue
        snippet_id = _make_snippet_id(ev.exact_text)
        # PRIMARY: snippet_id present (guaranteed by evidence boxes)
        if snippet_id in explanation:
            continue
        # FALLBACK: trigram match AND discriminative content word present.
        snippet_norm = _normalize_snippet_text(ev.exact_text)
        words = snippet_norm.split()
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        has_trigram = any(tri in explanation_norm for tri in trigrams)
        disc = _discriminative_word(snippet_norm)
        # If the snippet has no discriminative word (very short evidence),
        # fall back to trigram-only — otherwise require both.
        if has_trigram and (disc is None or disc in explanation_words):
            continue
        missing.append(ev.rule_id)

    return len(missing) == 0, missing
