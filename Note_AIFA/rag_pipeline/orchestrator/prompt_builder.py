"""
Phase 2 — Hardened Prompt Builder
===================================

Assembles the LLM prompt from the deterministic EvaluationResult + retrieved chunks.

Key safety properties:
1. The [DETERMINISTIC DECISION] section is always rendered FIRST.
   The LLM reads the decision before reading any context.
2. The [NORMATIVE CONTEXT] section is the ONLY allowed source of facts.
   Explicit instructions forbid the LLM from citing anything outside it.
3. The prompt is structured so that the LLM's role is explanation only,
   never re-determination.
4. Free-text values are passed through `_sanitize_text` which neutralises
   prompt-structural markers (`[FONTE …]`, `--- PROVA NORMATIVA ---`, leading
   `# heading`, ASCII delimiter lines) so user-controlled fields cannot
   forge prompt sections. Today's gold cases are synthetic and contain only
   typed enums/numbers, but the helper is in place defensively for any
   future real-data ingestion.
"""
from __future__ import annotations

import re

from aifa_rule_engine.models.results import EvaluationResult  # type: ignore[attr-defined]

from .schemas import RetrievedChunk

# Pre-compiled neutralisers (module-level → cheap on hot path).
_RE_INJ_DELIM = re.compile(r"^\s*-{3,}.*$", flags=re.MULTILINE)
_RE_INJ_HEADING = re.compile(r"^\s*#{1,6}\s", flags=re.MULTILINE)
_RE_INJ_BRACKET_SECTION = re.compile(
    r"\[(?:FONTE|CONTESTO\s+NORMATIVO|DECISIONE\s+DETERMINISTICA|"
    r"ISTRUZIONI\s+DI\s+SISTEMA|COMPITO|REGOLE\s+DECISIVE|DATI\s+MANCANTI|"
    r"RACCOMANDAZIONI\s+CLINICHE|SCORE\s+CLINICO)[^\]]*\]",
    flags=re.IGNORECASE,
)
# Audit V4 2026-05-12: neutralise model-specific control tokens
# (Llama 2 [INST]/<<SYS>>, Llama 3 / ChatML <|system|>/<|user|>/...)
# so user-controlled fields cannot inject role-switching markers.
_RE_INJ_LLM_MARKER = re.compile(
    r"(\[/?(?:INST|SYS)\]|"
    r"<\|(?:system|user|assistant|begin_of_text|end_of_text|"
    r"start_header_id|end_header_id|eot_id|im_start|im_end)\|>|"
    r"<<SYS>>|<</SYS>>)",
    flags=re.IGNORECASE,
)


def _sanitize_text(value: object) -> str:
    """
    Defensive scrub of free-text values before they enter the prompt.

    Drops bracketed section headers, model control tokens, heading markers and
    triple-dash delimiter lines that could otherwise let an attacker forge
    prompt sections via a user-controlled field. Idempotent and cheap.
    """
    s = "" if value is None else str(value)
    s = _RE_INJ_BRACKET_SECTION.sub(" ", s)
    s = _RE_INJ_LLM_MARKER.sub(" ", s)
    s = _RE_INJ_DELIM.sub(" ", s)
    s = _RE_INJ_HEADING.sub(" ", s)
    return s.strip()


def build_prompt(
    result: EvaluationResult,
    chunks: list[RetrievedChunk],
) -> str:
    """
    Build the full prompt string for the LLM.

    Structure:
        [SYSTEM INSTRUCTIONS]
        [DETERMINISTIC DECISION — DO NOT CONTRADICT]
        [DECISIVE RULES]
        [CLINICAL SCORE — CHA2DS2-VASc]   (only for Nota 97)
        [MISSING DATA]
        [CLINICAL GUIDANCE FLAGS]
        [NORMATIVE CONTEXT — USE ONLY THIS TEXT]
        [TASK]
    """
    sections: list[str] = []

    sections.append(_build_system_block())
    sections.append(_build_decision_block(result))
    sections.append(_build_rules_block(result))

    # Bug fix (audit Day 1, finding F4-7/F4-11): score block is meaningful only
    # for Nota 97 (CHA2DS2-VASc is the FANV anticoagulation eligibility score).
    # For Note 01/13/66 it pollutes the prompt with irrelevant clinical context.
    if (
        result.nota_evaluated == "97"
        and "cha2ds2vasc" in result.rag_payload.computed_scores
    ):
        sections.append(_build_score_block(result))

    if result.missing_fields_coverage or result.missing_fields_guidance:
        sections.append(_build_missing_data_block(result))

    if result.clinical_flags:
        sections.append(_build_flags_block(result))

    sections.append(_build_normative_context_block(chunks))
    sections.append(_build_task_block(result))

    return "\n\n".join(sections)


# ── Section builders ──────────────────────────────────────────────────────────

def _build_system_block() -> str:
    return (
        "[ISTRUZIONI DI SISTEMA]\n"
        "Sei un assistente di farmacologia clinica specializzato nel sistema di rimborso "
        "farmaceutico italiano (SSN/Note AIFA). Il tuo compito è ESCLUSIVAMENTE spiegare "
        "una decisione già presa da un sistema deterministico. DEVI:\n"
        "1. Non contraddire MAI la DECISIONE DETERMINISTICA riportata di seguito.\n"
        "2. Citare ESCLUSIVAMENTE fatti presenti nel CONTESTO NORMATIVO fornito.\n"
        "3. Per ogni affermazione citare la fonte esatta (nome file e numero di pagina).\n"
        "4. Se il contesto non contiene un'informazione necessaria, scrivere: "
        "   \"Informazione non disponibile nel testo normativo.\"\n"
        "5. Rispondere sempre in italiano.\n"
        "6. Non inventare dati clinici, soglie, o criteri normativi."
    )


def _build_decision_block(result: EvaluationResult) -> str:
    decision_str = result.reimbursement_decision or f"STATO: {result.decision_status}"
    route_info = ""
    if result.route_to:
        route_info = (
            f"\nRimandata a: Nota {_sanitize_text(result.route_to)} "
            f"— {_sanitize_text(result.route_reason or '')}"
        )

    return (
        "[DECISIONE DETERMINISTICA — NON CONTRADDIRE QUESTA SEZIONE]\n"
        f"Farmaco valutato : {_sanitize_text(result.drug_evaluated)}\n"
        f"Nota AIFA        : {_sanitize_text(result.nota_evaluated)}\n"
        f"Decisione        : {_sanitize_text(decision_str)}\n"
        f"Stato            : {_sanitize_text(result.decision_status)}"
        + route_info
    )


def _build_rules_block(result: EvaluationResult) -> str:
    payload = result.rag_payload
    lines: list[str] = ["[REGOLE DECISIVE]"]

    if payload.blocking_rules:
        lines.append("Regole che hanno determinato/bloccato la copertura:")
        for br in payload.blocking_rules:
            # Use rule_evaluated_as (raw result) for correct explanation
            raw = br.rule_evaluated_as
            # Audit fix V3-M5 (2026-05-06): sanitize br.rule_id, rule_type, reason
            # and the anchor fields (pdf_file, section) for consistency with
            # _build_flags_block:200, which already sanitizes the equivalent
            # fields. Trust model is uniform across both blocks now.
            section_part = (
                f" — {_sanitize_text(br.anchor.section)}" if br.anchor.section else ""
            )
            lines.append(
                f"  • [{_sanitize_text(br.rule_id)}] tipo={_sanitize_text(br.rule_type)} "
                f"valutata={raw} → {_sanitize_text(br.reason)}\n"
                f"    Fonte: {_sanitize_text(br.anchor.pdf_file)} p.{br.anchor.page}"
                + section_part
            )

    if payload.passed_rules:
        lines.append("Regole superate (contesto):")
        for pr in payload.passed_rules:
            anchor = pr.get("anchor", {})
            lines.append(
                f"  • [{_sanitize_text(pr['rule_id'])}] — "
                f"{_sanitize_text(anchor.get('pdf_file',''))} p.{anchor.get('page','')}"
            )

    return "\n".join(lines)


def _build_score_block(result: EvaluationResult) -> str:
    sr = result.rag_payload.computed_scores["cha2ds2vasc"]
    thr = str(sr.threshold) if sr.threshold is not None else "N/D (sesso non noto)"
    missing = ", ".join(sr.missing_components) if sr.missing_components else "nessuno"
    return (
        "[SCORE CLINICO — CHA2DS2-VASc]\n"
        f"Range calcolato  : [{sr.min_score}, {sr.max_score}]\n"
        f"Soglia (sesso)   : ≥{thr}\n"
        f"Eleggibile       : {sr.eligible}\n"
        f"Componenti mancanti: {missing}\n"
        f"Fonte            : {sr.anchor.pdf_file} p.{sr.anchor.page} — {sr.anchor.section}"
    )


def _build_missing_data_block(result: EvaluationResult) -> str:
    lines: list[str] = ["[DATI MANCANTI]"]
    if result.missing_fields_coverage:
        lines.append(
            "Campi assenti DECISIVI (potrebbero cambiare la copertura se forniti):\n  "
            + ", ".join(result.missing_fields_coverage)
        )
    if result.missing_fields_guidance:
        lines.append(
            "Campi assenti per la GUIDA CLINICA (posologia/avvertenze incomplete):\n  "
            + ", ".join(result.missing_fields_guidance)
        )
    return "\n".join(lines)


def _build_flags_block(result: EvaluationResult) -> str:
    lines: list[str] = ["[RACCOMANDAZIONI CLINICHE]"]
    for flag in result.clinical_flags:
        info = " [solo informativo]" if flag.informational_only else ""
        lines.append(
            f"  • [{_sanitize_text(flag.rule_id)}] {_sanitize_text(flag.flag_type)}{info}\n"
            f"    {_sanitize_text(flag.detail)}\n"
            f"    Fonte: {_sanitize_text(flag.anchor.pdf_file)} p.{flag.anchor.page}"
        )
    return "\n".join(lines)


def _build_normative_context_block(chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = [
        "[CONTESTO NORMATIVO — USA ESCLUSIVAMENTE QUESTO TESTO COME FONTE]",
        "Le fonti sono numerate. Cita SEMPRE il numero della fonte quando fai "
        "un'affermazione.\n",
    ]
    for i, chunk in enumerate(chunks, start=1):
        stage_label = "guida-ancorata" if chunk.retrieval_stage == "anchor_guided" else "semantica"
        section_info = f" — {chunk.section}" if chunk.section else ""
        lines.append(
            f"--- FONTE {i}: {chunk.pdf_file} p.{chunk.page}{section_info} "
            f"[{stage_label}] ---\n"
            f"{chunk.text}\n"
            f"--- FINE FONTE {i} ---"
        )
    return "\n".join(lines)


def _build_task_block(result: EvaluationResult) -> str:
    if result.reimbursement_decision is not None:
        decision_str = result.reimbursement_decision
    elif result.route_to:
        decision_str = f"INDIRIZZATO ALLA NOTA {result.route_to}"
    else:
        decision_str = "NON_DETERMINABILE"
    # Conditional instruction: if CHA2DS2-VASc score is relevant (Nota 97 only),
    # the LLM must cite it. See bug fix F4-7/F4-11 in build_prompt above.
    score_instruction = ""
    if (
        result.nota_evaluated == "97"
        and "cha2ds2vasc" in result.rag_payload.computed_scores
    ):
        sr = result.rag_payload.computed_scores["cha2ds2vasc"]
        score_instruction = (
            f"   OBBLIGATORIO: cita il punteggio CHA2DS2-VASc (range [{sr.min_score},{sr.max_score}]) "
            f"e la soglia ({sr.threshold}) nella MOTIVAZIONE.\n"
        )
    return (
        "[COMPITO]\n"
        "Genera una spiegazione clinica strutturata seguendo ESATTAMENTE il formato "
        "sottostante. NON usare markdown (nessun **, *, #). Usa SOLO titoli numerati "
        "esattamente come mostrato. Devi completare TUTTE e 5 le sezioni.\n\n"
        "1. DECISIONE\n"
        f"   Il farmaco è: {decision_str}\n"
        f"   Dichiara che il farmaco è {decision_str} secondo la Nota AIFA valutata.\n\n"
        "2. MOTIVAZIONE\n"
        "   Spiega il perché citando le FONTI NORMATIVE per numero "
        "   (es: 'come indicato nella FONTE 1...'). Cita le fonti più rilevanti "
        "   in modo sintetico.\n"
        + score_instruction
        + "\n"
        "3. RACCOMANDAZIONI\n"
        "   Elenca le raccomandazioni di posologia/preferenza/avvertenza se presenti. "
        "   Se nessuna, scrivi 'Nessuna raccomandazione aggiuntiva.'\n\n"
        "4. DATI MANCANTI\n"
        "   Elenca i campi mancanti e il loro impatto clinico. "
        "   Se nessuno, scrivi 'Dati completi.'\n\n"
        "5. FONTI\n"
        "   Lista tutte le fonti citate con nome file e numero di pagina.\n\n"
        "REGOLE ASSOLUTE:\n"
        "- I titoli delle sezioni sono ESATTAMENTE: '1. DECISIONE', '2. MOTIVAZIONE', "
        "'3. RACCOMANDAZIONI', '4. DATI MANCANTI', '5. FONTI'\n"
        "- NON usare **, *, #, grassetto, corsivo o qualsiasi markup\n"
        "- NON aggiungere informazioni non presenti nelle FONTI\n"
        "- DEVI completare tutte e 5 le sezioni prima di fermarti\n"
        f"- La sezione 1 DEVE contenere la stringa esatta: {decision_str}"
    )
