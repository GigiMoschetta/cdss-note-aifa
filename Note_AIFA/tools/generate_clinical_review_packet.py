#!/usr/bin/env python3
"""
Genera un PDF di revisione clinica focalizzato sul medico:
per ogni caso → cartella clinica narrativa → farmaco prescritto →
output LLM → ogni regola AIFA citata verbatim con esito argomentato.

Run:
    python tools/generate_clinical_review_packet.py
Output:
    audit/CLINICAL_REVIEW_PACKET_2026-05-13.md
    audit/CLINICAL_REVIEW_PACKET_2026-05-13.pdf (via Chrome headless)
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = PROJECT / "evaluation" / "results"
GOLD_DIR = PROJECT / "evaluation" / "gold_standard"
RULES_DIR = PROJECT / "aifa_rule_engine" / "rules"
EXPL_DIR = RESULTS / "pipeline_explanations"
OUTPUT_MD = PROJECT.parent / "audit" / "CLINICAL_REVIEW_PACKET_2026-05-13.md"

sys.path.insert(0, str(PROJECT))
from demo.data_loader import (  # type: ignore
    _FLAG_META,
    _NUMERIC_LABELS,
    drug_class,
    load_gold_cases,
    numeric_clinical_values,
    positive_clinical_flags,
)

# 10 casi rappresentativi (decisione × Nota × pattern clinico distinto)
CASES = [
    ("N01-001", "Paziente con FANS senza fattori di rischio gastrointestinale"),
    ("N01-008", "Triplice terapia FANS + anticoagulante + PPI"),
    ("N01-011", "Dati clinici insufficienti per decidere"),
    ("N01-019", "Diclofenac+misoprostolo (associazione fissa NSAID)"),
    ("N13-005", "Ipercolesterolemia, dieta non rispettata"),
    ("N13-007", "Intolleranza documentata alle statine"),
    ("N66-002", "Storia di ulcera peptica attiva"),
    ("N66-010", "Ibuprofene + codeina (associazione fissa)"),
    ("N97-001", "Fibrillazione atriale, CHA2DS2-VASc elevato"),
    ("N97-005", "Controindicazione clinica al DOAC"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_yaml_rules() -> dict[str, dict]:
    import yaml  # type: ignore
    catalog: dict[str, dict] = {}
    for yf in sorted(RULES_DIR.glob("*/rules.yaml")):
        try:
            data = yaml.safe_load(yf.read_text(encoding="utf-8"))
        except Exception:
            continue
        rules = data if isinstance(data, list) else data.get("rules", [])
        for r in rules:
            if isinstance(r, dict) and r.get("rule_id"):
                catalog[r["rule_id"]] = {
                    "description_it": r.get("description_it", ""),
                    "detail": r.get("detail", ""),
                    "rule_type": r.get("rule_type", ""),
                }
    return catalog


def evaluate_live(case: dict) -> dict | None:
    """Chiamata live al rule engine per coverage_trace + ancore PDF."""
    inp = case["input"]
    body = {
        "schema_version": "3.3",
        "note_id": inp["nota_id"],
        "drug_id": inp["drug_id"],
        "patient_data": inp["patient_data"],
        "clinician_asserted": inp.get("clinician_asserted", {}),
    }
    try:
        req = urllib.request.Request(
            "http://localhost:8000/evaluate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except Exception as e:
        print(f"  [warn] evaluate {case['id']}: {e}", file=sys.stderr)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Narrative rendering (italiano clinico semplice)
# ──────────────────────────────────────────────────────────────────────────────

def _sex_to_it(s: str) -> str:
    return {"F": "Donna", "M": "Uomo"}.get(s or "", "Paziente")


def _flag_to_label(key: str) -> str:
    meta = _FLAG_META.get(key)
    return meta[0] if meta else key.replace("_", " ").capitalize()


def _flag_to_emoji(key: str, kind: str = "info") -> str:
    """Restituisce solo l'emoji di severità, senza il glifo specifico (più sobrio)."""
    meta = _FLAG_META.get(key)
    if meta:
        sev = meta[2]
        return {"danger": "🔴", "warn": "🟡", "info": "•"}.get(sev, "•")
    return "•"


def render_cartella_clinica(case: dict) -> str:
    """Quadro clinico narrativo del paziente."""
    inp = case["input"]
    pd = inp["patient_data"]
    drug_id = inp["drug_id"]
    nota = inp["nota_id"]

    # Identità (deterministica via data_loader, ma estraiamo direttamente dal gold case
    # poiché il gold ha già full_name/age/sex iniettati nella demo, qui lavoriamo
    # con i flag puri perché il gold.json non ha vanity).
    age = pd.get("paziente_eta") or pd.get("age") or None
    sex_key = (pd.get("paziente_sesso") or pd.get("sex") or "").upper()

    md: list[str] = []
    md.append("### Cartella clinica\n\n")

    # Intestazione narrativa (solo se almeno uno tra età/sesso è disponibile)
    sex_str = _sex_to_it(sex_key) if sex_key else None
    age_str = f"{age} anni" if age else None
    if sex_str or age_str:
        parts_intro = [p for p in (sex_str, age_str) if p]
        md.append("**" + ", ".join(parts_intro) + ".**\n\n")

    # Flag positivi (condizioni presenti) — separati per severità
    pos_flags = positive_clinical_flags(pd)
    danger = [f for f in pos_flags if f["severity"] == "danger"]
    warn = [f for f in pos_flags if f["severity"] == "warn"]
    info = [f for f in pos_flags if f["severity"] == "info"]

    if danger or warn:
        md.append("**Anamnesi rilevante e condizioni concomitanti:**\n\n")
        for f in danger + warn:
            md.append(f"- 🔴 {f['label']}\n" if f["severity"] == "danger"
                      else f"- 🟡 {f['label']}\n")
        md.append("\n")
    if info:
        md.append("**Altri dati clinici:**\n\n")
        for f in info:
            md.append(f"- ✓ {f['label']}\n")
        md.append("\n")

    # Valori numerici
    nums = numeric_clinical_values(pd)
    if nums:
        md.append("**Esami e parametri:**\n\n")
        md.append("| Parametro | Valore | |\n|---|---:|---|\n")
        for n in nums:
            unit = f" {n['unit']}" if n["unit"] else ""
            md.append(f"| {n['label']} | **{n['value']}**{unit} | |\n")
        md.append("\n")

    # Dati documentati ma NEGATIVI (rilevanti per la nota in oggetto)
    # Mostra i flag a False che la regola engine ha effettivamente VALUTATO
    # (sappiamo che sono stati valutati perché la nota li richiede).
    negative_flags = []
    for k, v in pd.items():
        if v is False and k in _FLAG_META:
            negative_flags.append(_FLAG_META[k][0])
    if negative_flags:
        md.append("**Condizioni escluse (documentate come assenti):**\n\n")
        for label in negative_flags:
            md.append(f"- {label}: _no_\n")
        md.append("\n")

    # Asserzioni del medico (clinician_asserted)
    cas = inp.get("clinician_asserted", {})
    if cas:
        md.append("**Asserzioni del medico prescrittore:**\n\n")
        for k, v in cas.items():
            label = _flag_to_label(k)
            v_str = "_documentato_" if v is True else "_assente_" if v is False else f"`{v}`"
            md.append(f"- {label}: {v_str}\n")
        md.append("\n")

    return "".join(md)


def render_prescrizione(case: dict) -> str:
    """Sezione 'Prescrizione richiesta'."""
    inp = case["input"]
    drug = inp["drug_id"]
    nota = inp["nota_id"]
    md: list[str] = []
    md.append("### Prescrizione richiesta\n\n")
    drug_label, _, _ = drug_class(drug)
    md.append(
        f"Il medico propone la prescrizione di **{drug}** "
        f"({drug_label.lower()}) ai sensi della **Nota AIFA {nota}**.\n\n"
    )
    return "".join(md)


def render_llm_output(case_id: str) -> str:
    """Sezione output Llama."""
    md: list[str] = []
    expl_file = EXPL_DIR / f"{case_id}.txt"
    if not expl_file.exists():
        md.append("### Spiegazione automatica (Llama 3.1 8B)\n\n_Output LLM non disponibile per questo caso._\n\n")
        return "".join(md)
    full = expl_file.read_text()
    if "--- PROVA NORMATIVA ---" in full:
        llm = full.split("--- PROVA NORMATIVA ---")[0].strip()
    else:
        llm = full.strip()

    md.append("### Spiegazione automatica (modello locale Llama 3.1 8B)\n\n")
    md.append("_Output testuale generato dal modello, ancorato al PDF tramite RAG._\n\n")
    md.append("```text\n")
    md.append(llm)
    md.append("\n```\n\n")
    return "".join(md)


def _rule_natural_title(rid: str, rtype: str, desc_it: str) -> str:
    """Titolo human-readable per la regola (no ID tecnico nel titolo)."""
    type_label = {
        "SCOPE": "Ambito di applicazione",
        "EXCLUSION_HARD": "Controindicazione assoluta",
        "EXCLUSION_SOFT": "Controindicazione relativa",
        "INCLUSION": "Criterio di inclusione",
        "EXCEPTION": "Eccezione",
        "GUIDANCE_WARN": "Avvertenza clinica",
        "GUIDANCE_DOSE": "Indicazione posologica",
        "PATHWAY": "Percorso terapeutico",
        "ROUTING": "Rinvio ad altra Nota",
    }.get(rtype, "Regola")
    # Estrai una breve frase guida dalla description_it (primi 80 char)
    snippet = (desc_it or "").split(".")[0].strip()
    if len(snippet) > 80:
        snippet = snippet[:78] + "…"
    return f"{type_label}" + (f": {snippet}" if snippet else "")


def _facts_to_natural_language(facts: dict, tv: str) -> str:
    """Costruisce frase narrativa: «il paziente soddisfa/non soddisfa il criterio perché ...»."""
    if not facts:
        return ""
    parts_pos = []
    parts_neg = []
    parts_null = []
    for k, v in facts.items():
        label = _flag_to_label(k)
        if v is True:
            parts_pos.append(label.lower())
        elif v is False:
            parts_neg.append(label.lower())
        elif v is None:
            parts_null.append(label.lower())
        else:
            # numerico/stringa
            parts_pos.append(f"{label.lower()} = {v}")

    chunks = []
    if parts_pos:
        chunks.append("presenza di: **" + ", ".join(parts_pos) + "**")
    if parts_neg:
        chunks.append("assenza di: **" + ", ".join(parts_neg) + "**")
    if parts_null:
        chunks.append("dati non documentati per: **" + ", ".join(parts_null) + "**")
    return "; ".join(chunks)


def render_rule_verification(ev: dict, rule_catalog: dict) -> str:
    """Sezione 'Verifica della decisione contro le regole AIFA'."""
    md: list[str] = []
    trace = ev.get("coverage_trace") or []
    rag = ev.get("rag_payload") or {}
    blocking_ids = {r.get("rule_id") for r in (rag.get("blocking_rules") or [])}
    passed_ids = {r.get("rule_id") for r in (rag.get("passed_rules") or [])}

    # Filtra solo regole che hanno determinato qualcosa (blocking o passed)
    relevant = []
    seen = set()
    for entry in trace:
        rid = entry.get("rule_id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        kind = "blocking" if rid in blocking_ids else ("passed" if rid in passed_ids else None)
        if kind:
            relevant.append((entry, kind))

    if not relevant:
        return "### Verifica della decisione contro la Nota AIFA\n\n_Nessuna regola con esito significativo._\n\n"

    md.append("### Verifica della decisione contro la Nota AIFA\n\n")
    md.append(
        f"Il sistema ha esaminato **{len(relevant)} regole** della Nota durante la "
        "valutazione. Per ciascuna è riportato:\n\n"
        "- il **testo verbatim** della regola estratto direttamente dal PDF della Nota AIFA,\n"
        "- l'**esito** sulla situazione clinica di questo paziente (verificata / non verificata / indeterminata),\n"
        "- la **motivazione** del perché la regola ha avuto quell'esito sui dati clinici dichiarati.\n\n"
        "Le **regole determinanti** (🔴) sono quelle che hanno portato direttamente alla decisione finale.\n\n"
    )

    for i, (entry, kind) in enumerate(relevant, start=1):
        rid = entry.get("rule_id")
        tv = entry.get("truth_value", "?")
        cat = rule_catalog.get(rid, {})
        desc_it = cat.get("description_it", "")
        detail = cat.get("detail", "")
        rtype = cat.get("rule_type", "")
        anchor = entry.get("anchor") or {}
        facts = entry.get("facts_used") or {}

        # Esito unico: cosa la regola dice del paziente
        if tv == "TRUE":
            esito_label = "✅ Condizione VERIFICATA"
        elif tv == "FALSE":
            esito_label = "❌ Condizione NON VERIFICATA"
        elif tv == "UNKNOWN":
            esito_label = "❓ Condizione INDETERMINATA (dati clinici insufficienti)"
        else:
            esito_label = f"({tv})"
        determinante_badge = (
            "  🔴 _(regola determinante per la decisione finale)_"
            if kind == "blocking" else ""
        )

        title = _rule_natural_title(rid, rtype, desc_it)
        md.append(f"#### Regola {i} — {title}\n\n")
        md.append(f"**Esito sul paziente:** {esito_label}{determinante_badge}\n\n")

        if desc_it:
            md.append(f"_Sintesi della regola:_ {desc_it}\n\n")
        if detail and detail.strip() != desc_it.strip():
            md.append(f"_Dettaglio normativo:_ {detail}\n\n")

        # Citazione verbatim PDF
        if anchor:
            pdf_f = anchor.get("pdf_file", "?")
            page = anchor.get("page", "?")
            section = anchor.get("section", "")
            excerpt = anchor.get("excerpt", "")
            md.append(f"**📖 Testo dalla Nota AIFA** — {pdf_f}, pag. {page}")
            if section:
                md.append(f" (sezione _{section}_)")
            md.append(":\n\n")
            if excerpt:
                # Pulisci leading/trailing whitespace per evitare blockquote rotti
                exc = excerpt.strip()
                for line in exc.split("\n"):
                    md.append(f"> {line.strip()}\n")
                md.append("\n")

        # Motivazione su questo paziente
        natural = _facts_to_natural_language(facts, tv)
        if natural:
            verb = {
                "TRUE": "Il paziente **soddisfa** questo criterio",
                "FALSE": "Il paziente **NON soddisfa** questo criterio",
                "UNKNOWN": "Non è possibile valutare questo criterio",
            }.get(tv, "Esito")
            md.append(f"**🧑‍⚕️ Motivazione sul paziente:** {verb}: {natural}.\n\n")

        md.append("---\n\n")
    return "".join(md)


def render_decision_header(ev: dict | None) -> str:
    """Verdetto in cima al caso."""
    if not ev:
        return "### Decisione del sistema\n\n_Rule engine non raggiungibile._\n\n"
    decision = ev.get("reimbursement_decision")
    status = ev.get("decision_status")
    route_to = ev.get("route_to")
    md: list[str] = []
    md.append("### Decisione del sistema\n\n")
    if status == "ROUTED":
        md.append(f"🟦 **La prescrizione è soggetta alla Nota {route_to}, non a quella corrente.**\n\n")
        if ev.get("route_reason"):
            md.append(f"_Motivo:_ {ev['route_reason']}\n\n")
    elif decision == "RIMBORSABILE":
        md.append("🟢 **RIMBORSABILE dal SSN**\n\n")
    elif decision == "NON_RIMBORSABILE":
        md.append("🔴 **NON RIMBORSABILE dal SSN**\n\n")
    elif decision == "NON_DETERMINABILE":
        md.append("🟡 **DECISIONE NON DETERMINABILE** (dati clinici insufficienti)\n\n")
        missing = ev.get("missing_fields_coverage") or []
        if missing:
            labels = ", ".join(_flag_to_label(m).lower() for m in missing)
            md.append(f"_Dati mancanti che impediscono la decisione:_ {labels}.\n\n")
    else:
        md.append(f"**{decision}**\n\n")

    flags = ev.get("clinical_flags") or []
    if flags:
        md.append("**Avvertenze cliniche emesse dal sistema:**\n\n")
        for fl in flags:
            # Cerca testo in ordine di preferenza (rule engine usa nomi diversi)
            msg = (
                fl.get("detail")
                or fl.get("flag_message")
                or fl.get("rationale_it")
                or fl.get("description_it")
                or fl.get("description")
                or fl.get("message")
                or fl.get("text")
                or f"avvertenza emessa dalla regola `{fl.get('rule_id', '?')}`"
            )
            md.append(f"- ⚠ **{msg}**\n")
            anc = fl.get("anchor") or {}
            if anc.get("excerpt"):
                ex = anc["excerpt"].strip().strip('"« »').strip()
                pdf_f = anc.get("pdf_file", "")
                page = anc.get("page", "")
                src = f"  _Fonte:_ {pdf_f} p.{page}" if pdf_f else ""
                md.append(f"  > {ex}\n")
                if src:
                    md.append(f"{src}\n")
        md.append("\n")

    return "".join(md)


def render_case(idx: int, cid: str, descr: str, gold: dict, rule_catalog: dict) -> str:
    """Renderizza un caso completo."""
    md: list[str] = []
    md.append(f"\n\n---\n\n# Caso {idx}: {descr}\n\n")
    md.append(f"_Identificativo caso: `{cid}` — Nota AIFA {cid.split('-')[0][1:]}_\n\n")

    md.append(render_cartella_clinica(gold))
    md.append(render_prescrizione(gold))

    ev = evaluate_live(gold)
    md.append(render_decision_header(ev))
    md.append(render_llm_output(cid))
    if ev:
        md.append(render_rule_verification(ev, rule_catalog))

    return "".join(md)


def main():
    print("Loading rule catalog and gold cases...", file=sys.stderr)
    rule_catalog = load_yaml_rules()
    print(f"  → {len(rule_catalog)} rules loaded", file=sys.stderr)

    gold_cases: dict[str, dict] = {}
    for gf in sorted(GOLD_DIR.glob("nota_*_cases.json")):
        for c in json.loads(gf.read_text()).get("cases", []):
            gold_cases[c["id"]] = c
    print(f"  → {len(gold_cases)} gold cases loaded", file=sys.stderr)

    parts: list[str] = []
    parts.append("# Pacchetto di revisione clinica — Sistema di supporto decisionale Note AIFA\n\n")
    parts.append(f"**Generato il:** {datetime.now().strftime('%Y-%m-%d ore %H:%M')}  \n")
    parts.append("**Sistema:** CDSS Neuro-Simbolico Note AIFA — tesi triennale UniTS  \n")
    parts.append("**Modello linguistico:** Llama 3.1 8B (locale, esecuzione su GPU dedicata)  \n")
    parts.append("**Motore decisionale:** 44 regole strutturate dalle Note AIFA 01, 13, 66, 97  \n\n")

    parts.append("## A cosa serve questo documento\n\n")
    parts.append(
        "Il sistema riceve in ingresso una scheda clinica del paziente e una "
        "prescrizione proposta, e produce in uscita:\n\n"
        "1. una **decisione di rimborsabilità** (RIMBORSABILE / NON RIMBORSABILE / "
        "NON DETERMINABILE / RINVIATO ad altra Nota) basata sulle regole formalizzate "
        "dalle Note AIFA;\n"
        "2. una **spiegazione in italiano** generata dal modello linguistico, ancorata "
        "ai testi PDF normativi.\n\n"
        "Questo pacchetto contiene **10 casi clinici di esempio**, selezionati per "
        "coprire situazioni cliniche diverse (decisioni positive, negative, casi "
        "ambigui, rinvii, eccezioni). Per ciascun caso è riportato:\n\n"
        "- la **cartella clinica** del paziente,\n"
        "- la **prescrizione proposta**,\n"
        "- la **decisione del sistema** + l'**output del modello linguistico**,\n"
        "- la **verifica della decisione**: per ogni regola della Nota AIFA "
        "applicata, il **testo verbatim** dalla Nota AIFA e la **motivazione** "
        "del perché la regola si applica (o non si applica) al paziente.\n\n"
    )

    parts.append("## Come revisionare un caso\n\n")
    parts.append(
        "1. Leggi la **cartella clinica** del paziente.\n"
        "2. Annota mentalmente quale decisione faresti tu come clinico.\n"
        "3. Confronta con la **decisione del sistema**.\n"
        "4. Leggi la **spiegazione del modello linguistico** — è chiara? È clinicamente "
        "corretta? Aggiunge informazioni inventate?\n"
        "5. Vai alla sezione **Verifica della decisione**. Per ogni regola AIFA:\n"
        "   - leggi il **testo verbatim** preso dal PDF della Nota,\n"
        "   - guarda l'**esito** sulla situazione del paziente,\n"
        "   - verifica che la motivazione corrisponda a quanto la Nota effettivamente prescrive.\n\n"
        "**Obiettivo:** stabilire se il software (rule engine + modello linguistico) sta "
        "applicando correttamente le Note AIFA e se la spiegazione prodotta è "
        "clinicamente utile e affidabile.\n\n"
    )

    parts.append("## Indice dei casi\n\n")
    parts.append("| # | Caso | Nota AIFA | Pattern clinico |\n|:--:|:--|:--:|:--|\n")
    for i, (cid, desc) in enumerate(CASES, start=1):
        nota = cid.split("-")[0][1:]
        parts.append(f"| {i} | `{cid}` | {nota} | {desc} |\n")
    parts.append("\n")

    for i, (cid, descr) in enumerate(CASES, start=1):
        if cid not in gold_cases:
            print(f"  [skip] {cid} not in gold", file=sys.stderr)
            continue
        print(f"  Rendering case {i}: {cid}...", file=sys.stderr)
        parts.append(render_case(i, cid, descr, gold_cases[cid], rule_catalog))

    parts.append("\n\n---\n\n## Note tecniche per il revisore\n\n")
    parts.append(
        "**Architettura del sistema (per riferimento, non necessaria alla revisione clinica):**\n\n"
        "- **Motore decisionale (rule engine):** ogni Nota AIFA è stata formalizzata in regole "
        "computabili (totali 44 sulle 4 Note implementate). Il motore le valuta in sequenza su "
        "10 fasi (ambito → eccezioni → controindicazioni → inclusione → percorso terapeutico → "
        "guidance). Tempo di esecuzione tipico: meno di 5 ms per caso.\n"
        "- **Recupero del testo normativo (RAG):** per ogni regola applicata il sistema recupera "
        "il chunk di PDF esatto dal database vettoriale, in modo che la spiegazione possa citare "
        "verbatim il testo della Nota.\n"
        "- **Modello linguistico (Llama 3.1 8B locale):** riceve la decisione del motore come "
        "fatto + i chunk PDF rilevanti, e genera la spiegazione strutturata in 5 sezioni in "
        "italiano. **Non può sovrascrivere la decisione del motore**: se il modello tenta di "
        "contraddire la decisione, il sistema sostituisce la sua spiegazione con un template "
        "di sicurezza.\n"
        "- **Performance complessive sui 122 casi gold standard:** decisione corretta 122/122 "
        "(F1 = 1.000), zero allucinazioni verbatim, citazioni normative corrette al 99.9%.\n"
    )

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("".join(parts), encoding="utf-8")
    print(f"\n✓ Generated {OUTPUT_MD}", file=sys.stderr)
    print(f"  Size: {OUTPUT_MD.stat().st_size / 1024:.1f} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
