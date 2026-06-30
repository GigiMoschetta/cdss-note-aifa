"""
Tests for validate_response against realistic LLM output strings.

This file simulates what the LLM actually produces: well-formed outputs for
each decision type, and then all known failure modes.

No LLM calls are made — all explanations are hardcoded strings that represent
realistic outputs from llama3.1:8b, including correct and buggy variants.
"""
from unittest.mock import MagicMock

from rag_pipeline.orchestrator.schemas import NormativeEvidence, RetrievedChunk
from rag_pipeline.orchestrator.validators import validate_response

# ── Helpers ────────────────────────────────────────────────────────────────

def _anchor(pdf_file="nota-97.pdf", page=3):
    a = MagicMock()
    a.pdf_file = pdf_file
    a.page = page
    return a


def _blocking_rule(rule_id="N97_SCOPE_001", pdf_file="nota-97.pdf", page=3):
    br = MagicMock()
    br.rule_id = rule_id
    br.anchor = _anchor(pdf_file, page)
    return br


def _result(decision="RIMBORSABILE", drug="apixaban", blocking=None, route_to=None):
    r = MagicMock()
    r.reimbursement_decision = decision
    r.route_to = route_to
    r.drug_evaluated = drug
    r.rag_payload = MagicMock()
    r.rag_payload.blocking_rules = blocking or []
    r.rag_payload.passed_rules = []
    return r


def _chunk(chunk_id="c1", text="il farmaco apixaban è indicato per FANV",
           pdf_file="nota-97.pdf", page=3):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        pdf_file=pdf_file,
        nota_id="97",
        page=page,
        page_end=page,
        score=0.1,
        retrieval_stage="anchor_guided",
    )


def _evidence(rule_id="N97_SCOPE_001", exact_text="testo normativo specifico",
              role="blocking", missing=False):
    return NormativeEvidence(
        evidence_id="abc123",
        rule_id=rule_id,
        rule_type="EXCL_HARD",
        role=role,
        reason="criterio bloccante",
        pdf_file="nota-97.pdf",
        page=3,
        exact_text=exact_text,
        evidence_missing=missing,
    )


# ── Realistic LLM output fixtures ─────────────────────────────────────────

RIMBORSABILE_GOOD = """\
1. DECISIONE
Il farmaco apixaban è RIMBORSABILE secondo la Nota 97.

2. MOTIVAZIONE
Il paziente soddisfa i criteri richiesti dalla Nota 97. Come indicato nella FONTE 1,
la diagnosi di fibrillazione atriale non valvolare è confermata da ECG, il punteggio
CHA2DS2-VASc del paziente è 3 (soglia ≥2 per i maschi), e la valutazione clinica
è stata eseguita. Tutti i criteri di percorso A sono soddisfatti.

3. RACCOMANDAZIONI
Nessuna raccomandazione aggiuntiva.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
- nota-97.pdf, p. 1
"""

NON_RIMBORSABILE_GOOD = """\
1. DECISIONE
Il farmaco nimesulide è NON_RIMBORSABILE secondo la Nota 66.

2. MOTIVAZIONE
La prescrizione di nimesulide è controindicata in presenza di epatopatia.
Come indicato nella FONTE 1, la regola N66_EXCL_HARD_004 esclude la rimborsabilità.
Il paziente presenta epatopatia documentata, pertanto il farmaco non è rimborsabile.

3. RACCOMANDAZIONI
Valutare farmaci FANS alternativi senza controindicazione epatica.

4. DATI MANCANTI
Dati completi.

5. FONTI
- Nota_66.pdf, p. 4
--- PROVA NORMATIVA ---
Regola: N66_EXCL_HARD_004
snippet_id: abc1234567
Fonte: Nota_66.pdf, p. 4
Testo: "nimesulide controindicata in pazienti con epatopatia..."
--- FINE ---
"""

NON_DETERMINABILE_GOOD = """\
1. DECISIONE
Il farmaco apixaban è NON_DETERMINABILE: dati clinici insufficienti.

2. MOTIVAZIONE
Non è possibile determinare la rimborsabilità perché il sesso del paziente
non è stato comunicato. Come indicato nella FONTE 1, la soglia CHA2DS2-VASc
dipende dal sesso (≥2 per maschi, ≥3 per femmine).

3. RACCOMANDAZIONI
Completare il profilo del paziente con i dati richiesti.

4. DATI MANCANTI
- paziente_sesso: necessario per determinare la soglia CHA2DS2-VASc.

5. FONTI
- nota-97.pdf, p. 2
"""

ROUTED_GOOD = """\
1. DECISIONE
Il farmaco diclofenac+misoprostolo è INDIRIZZATO ALLA NOTA 66.

2. MOTIVAZIONE
La combinazione diclofenac+misoprostolo non è valutabile secondo la Nota 01.
Il medico deve verificare la prescrizione secondo la Nota 66.

3. RACCOMANDAZIONI
Verificare i criteri della Nota 66 per i farmaci FANS.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-01.pdf, p. 1
"""


# ── Well-formed outputs — all decision types ─────────────────────────────

class TestWellFormedOutputs:

    def test_rimborsabile_consistent(self):
        result = _result("RIMBORSABILE", drug="apixaban")
        flags = validate_response(RIMBORSABILE_GOOD, result, [_chunk()])
        assert flags.decision_consistent is True
        assert flags.decision_contradicted is False

    def test_rimborsabile_no_hallucinations_expected(self):
        result = _result("RIMBORSABILE", drug="apixaban")
        chunks = [_chunk(text="il farmaco apixaban è indicato per FANV. CHA2DS2-VASc calcolato.")]
        flags = validate_response(RIMBORSABILE_GOOD, result, chunks)
        # apixaban is the evaluated drug — exempt. No other known drugs in explanation.
        assert "apixaban" not in flags.suspected_hallucinations

    def test_non_rimborsabile_consistent(self):
        br = _blocking_rule("N66_EXCL_HARD_004", "Nota_66.pdf", 4)
        result = _result("NON_RIMBORSABILE", drug="nimesulide", blocking=[br])
        chunks = [_chunk("c1", "nimesulide controindicata epatopatia", "Nota_66.pdf", 4)]
        flags = validate_response(NON_RIMBORSABILE_GOOD, result, chunks)
        assert flags.decision_consistent is True
        assert flags.decision_contradicted is False

    def test_non_rimborsabile_citation_complete(self):
        br = _blocking_rule("N66_EXCL_HARD_004", "Nota_66.pdf", 4)
        result = _result("NON_RIMBORSABILE", drug="nimesulide", blocking=[br])
        chunks = [_chunk("c1", "nimesulide controindicata", "Nota_66.pdf", 4)]
        flags = validate_response(NON_RIMBORSABILE_GOOD, result, chunks)
        assert flags.citation_complete is True

    def test_non_determinabile_consistent(self):
        result = _result("NON_DETERMINABILE", drug="apixaban")
        flags = validate_response(NON_DETERMINABILE_GOOD, result, [_chunk()])
        assert flags.decision_consistent is True

    def test_routed_consistent(self):
        result = _result(decision=None, drug="diclofenac", route_to="66")
        flags = validate_response(ROUTED_GOOD, result, [])
        assert flags.decision_consistent is True


# ── LLM failure modes ─────────────────────────────────────────────────────

class TestLlmFailureModes:

    def test_truncated_output_missing_section(self):
        """Output truncated before section 5 → section_completeness=False."""
        truncated = """\
1. DECISIONE
Il farmaco è RIMBORSABILE.

2. MOTIVAZIONE
Criteri soddisfatti.
"""
        result = _result("RIMBORSABILE")
        flags = validate_response(truncated, result, [])
        # FONTI section is absent — citation_complete may be True (no blocking rules)
        # but section completeness would be detected by the evaluate script (not in ValidationFlags)
        # Here we verify that citation checks still work without crashing
        assert flags.decision_consistent is True

    def test_llm_omits_decision_string(self):
        """LLM forgets the exact decision string → decision_consistent=False."""
        no_decision = """\
1. DECISIONE
Il farmaco soddisfa i requisiti normativi.

2. MOTIVAZIONE
I criteri sono stati rispettati.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
"""
        result = _result("RIMBORSABILE")
        flags = validate_response(no_decision, result, [])
        assert flags.decision_consistent is False

    def test_rimborsabile_case_contradicted_by_llm(self):
        """RIMBORSABILE decision but LLM writes NON_RIMBORSABILE → contradicted=True."""
        contradicted = """\
1. DECISIONE
Il farmaco è RIMBORSABILE.

2. MOTIVAZIONE
Tuttavia, il farmaco risulta NON_RIMBORSABILE per questa indicazione.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
"""
        result = _result("RIMBORSABILE")
        flags = validate_response(contradicted, result, [])
        assert flags.decision_contradicted is True

    def test_non_rimborsabile_not_contradicted_by_correct_italian(self):
        """NON_RIMBORSABILE case: 'non è rimborsabile' is correct Italian, not a contradiction."""
        correct_italian = """\
1. DECISIONE
Il farmaco è NON_RIMBORSABILE.

2. MOTIVAZIONE
Il farmaco non è rimborsabile in presenza di epatopatia.
Il paziente non risulta idoneo secondo la normativa vigente.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- Nota_66.pdf, p. 4
"""
        br = _blocking_rule("R1", "Nota_66.pdf", 4)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        flags = validate_response(correct_italian, result, [])
        assert flags.decision_contradicted is False

    def test_hallucinated_drug_flagged(self):
        """LLM mentions a drug not in chunks and not being evaluated → hallucination."""
        hallucinated = """\
1. DECISIONE
Il farmaco è RIMBORSABILE.

2. MOTIVAZIONE
L'omeprazolo è indicato come gastroprotettore secondo la Nota 01.
La prescrizione rispetta i criteri normativi.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
"""
        result = _result("RIMBORSABILE", drug="apixaban")
        # Chunks about apixaban, not omeprazolo
        chunks = [_chunk(text="apixaban indicato per FANV, criteri CHA2DS2-VASc")]
        flags = validate_response(hallucinated, result, chunks)
        assert "omeprazolo" in flags.suspected_hallucinations

    def test_missing_citation_detected(self):
        """Blocking rule anchor not cited in FONTI → citation_complete=False."""
        no_citation = """\
1. DECISIONE
Il farmaco è NON_RIMBORSABILE.

2. MOTIVAZIONE
Criteri non soddisfatti.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-13.pdf, p. 5
"""
        # Use page=8 — "8" does not appear in "nota-13.pdf, p. 5" so no false-positive match
        br = _blocking_rule("N97_SCOPE_001", "nota-97.pdf", 8)
        result = _result("NON_RIMBORSABILE", blocking=[br])
        flags = validate_response(no_citation, result, [])
        assert flags.citation_complete is False
        assert len(flags.missing_citations) >= 1

    def test_ungrounded_citation_advisory(self):
        """LLM cites page 99 which is not in any retrieved chunk → ungrounded_citation."""
        invented_citation = """\
1. DECISIONE
Il farmaco è RIMBORSABILE.

2. MOTIVAZIONE
Come indicato nella FONTE 1, i criteri sono soddisfatti.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 99
"""
        result = _result("RIMBORSABILE")
        chunks = [_chunk(pdf_file="nota-97.pdf", page=3)]  # page 3, not 99
        flags = validate_response(invented_citation, result, chunks)
        assert len(flags.ungrounded_citations) >= 1

    def test_markdown_in_output_no_crash(self):
        """LLM uses markdown (** bold) — validators must not crash."""
        markdown_output = """\
1. DECISIONE
Il farmaco è **RIMBORSABILE**.

2. MOTIVAZIONE
I **criteri** sono soddisfatti secondo la normativa.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
"""
        result = _result("RIMBORSABILE")
        # Should not raise
        flags = validate_response(markdown_output, result, [])
        assert flags is not None
        assert flags.decision_consistent is True

    def test_multiple_blocking_rules_all_cited(self):
        """Two blocking rules, both cited → citation_complete=True."""
        two_citations = """\
1. DECISIONE
Il farmaco è NON_RIMBORSABILE.

2. MOTIVAZIONE
Regola R1 violata (FONTE 1) e regola R2 violata (FONTE 2).

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
- nota-66.pdf, p. 2
"""
        br1 = _blocking_rule("R1", "nota-97.pdf", 3)
        br2 = _blocking_rule("R2", "nota-66.pdf", 2)
        result = _result("NON_RIMBORSABILE", blocking=[br1, br2])
        flags = validate_response(two_citations, result, [])
        assert flags.citation_complete is True

    def test_multiple_blocking_rules_one_missing(self):
        """Two blocking rules, only one cited → citation_complete=False."""
        one_citation = """\
1. DECISIONE
Il farmaco è NON_RIMBORSABILE.

2. MOTIVAZIONE
Regola R1 violata.

3. RACCOMANDAZIONI
Nessuna.

4. DATI MANCANTI
Dati completi.

5. FONTI
- nota-97.pdf, p. 3
"""
        br1 = _blocking_rule("R1", "nota-97.pdf", 3)
        br2 = _blocking_rule("R2", "nota-66.pdf", 2)  # page 2 not cited
        result = _result("NON_RIMBORSABILE", blocking=[br1, br2])
        flags = validate_response(one_citation, result, [])
        assert flags.citation_complete is False
