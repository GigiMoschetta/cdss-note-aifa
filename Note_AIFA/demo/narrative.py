"""
Narrative builder per la demo: traduce coverage_trace + rag_payload del rule
engine in frasi cliniche complete e auto-esplicative.

Strategia: per ogni rule_id ho una funzione che riceve (facts_used,
patient_data, truth_value, anchor) e restituisce una frase italiana che
descrive cosa il rule engine ha verificato e perché ha dato quel risultato.

Esempio output:
  ✓ Il paziente ha una diagnosi confermata di FANV (ECG e valutazione clinica
    presenti) — requisito di scope della Nota 97.
  ✓ Il punteggio CHA2DS2-VASc del paziente è ≥ 2 — soddisfa il pathway per
    iniziare la terapia anticoagulante.
  ✓ Nessuna emorragia maggiore in atto.
"""
from __future__ import annotations

from typing import Any


# Phase → titolo human
PHASE_TITLES: dict[int, str] = {
    0: "Variabili derivate",
    1: "Ambito (scope)",
    2: "Eccezioni / Routing",
    3: "Esclusioni assolute (controindicazioni)",
    4: "Criteri di inclusione",
    5: "Percorso clinico richiesto",
    6: "Linee guida sul dosaggio",
    7: "Linee guida di preferenza",
    8: "Avvertenze cliniche",
    9: "Risoluzione conflitti dose",
    10: "Decisione finale",
}


# ─────────────────────────────────────────────────────────────────────────────
# Rule humanizers — costruiscono una frase clinica completa
# ─────────────────────────────────────────────────────────────────────────────

def _h_n97_scope(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Diagnosi di FANV confermata: ECG eseguito e valutazione "
                "clinica completata — requisito di ambito della Nota 97 soddisfatto.")
    missing = []
    if not facts.get("diagnosi_fanv"):
        missing.append("diagnosi di FANV")
    if not facts.get("ecg_confermato"):
        missing.append("conferma ECG")
    if not facts.get("valutazione_clinica_eseguita"):
        missing.append("valutazione clinica")
    if missing:
        return ("Mancano i requisiti di ambito della Nota 97: "
                + ", ".join(missing) + ".")
    return "I criteri di ambito della Nota 97 non sono soddisfatti."


def _cha2ds2_vasc(pd: dict) -> tuple[int, int]:
    """Restituisce (score, threshold) per CHA2DS2-VASc."""
    score = 0
    if pd.get("scompenso_cardiaco"):
        score += 1
    if pd.get("ipertensione_arteriosa"):
        score += 1
    age = pd.get("paziente_eta") or 0
    if age >= 75:
        score += 2
    elif age >= 65:
        score += 1
    if pd.get("diabete_mellito"):
        score += 1
    if pd.get("pregresso_ictus_tia_te"):
        score += 2
    if pd.get("vasculopatia"):
        score += 1
    sex = pd.get("paziente_sesso")
    if sex == "F":
        score += 1
    threshold = 3 if sex == "F" else 2
    return score, threshold


def _h_n97_path(facts: dict, pd: dict, tv: str) -> str:
    score, threshold = _cha2ds2_vasc(pd)
    sex_label = "donne" if pd.get("paziente_sesso") == "F" else "uomini"
    if tv == "TRUE":
        return (f"Punteggio CHA2DS2-VASc = **{score}** (soglia ≥ {threshold} per {sex_label}): "
                f"il paziente ha indicazione alla terapia anticoagulante secondo "
                f"il pathway della Nota 97 (Percorso C).")
    return (f"Punteggio CHA2DS2-VASc = **{score}** sotto la soglia ≥ {threshold} per {sex_label}: "
            f"non c'è indicazione alla terapia anticoagulante.")


def _h_excl_emorragia(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuna emorragia maggiore in atto — controindicazione assoluta esclusa."
    return "⚠️ Emorragia maggiore in atto: controindicazione assoluta agli anticoagulanti."


def _h_excl_diatesi(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuna diatesi emorragica congenita."
    return "⚠️ Diatesi emorragica congenita presente — controindicazione."


def _h_excl_gravidanza(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Paziente non in gravidanza."
    return "⚠️ Gravidanza in corso — anticoagulanti orali controindicati."


def _h_excl_ipersensib(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuna ipersensibilità nota al farmaco proposto."
    return "⚠️ Ipersensibilità nota al farmaco — controindicazione."


def _h_excl_valv(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Assenti FA valvolare e protesi valvolari meccaniche."
    return ("⚠️ Presenza di FA valvolare o protesi meccanica: i DOAC sono "
            "controindicati in questi casi.")


def _h_excl_vfg(facts: dict, pd: dict, tv: str) -> str:
    vfg = pd.get("vfg_cockroft_gault")
    if tv == "FALSE":
        return f"Funzione renale adeguata (VFG = {vfg} mL/min) — nessuna controindicazione."
    return (f"⚠️ Funzione renale insufficiente (VFG = {vfg} mL/min) — il farmaco "
            f"non è raccomandato sotto la soglia minima.")


def _h_excl_peso(facts: dict, pd: dict, tv: str) -> str:
    peso = pd.get("paziente_peso_kg")
    if tv == "FALSE":
        return f"Peso corporeo nel range di sicurezza ({peso} kg)."
    return f"⚠️ Peso fuori range raccomandato ({peso} kg) — adeguare la dose."


def _h_n01_scope(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        bits = []
        if pd.get("trattamento_cronico_fans"):
            bits.append("trattamento cronico con FANS")
        if pd.get("terapia_antiaggregante_asa"):
            bits.append("ASA antiaggregante")
        ctx = " + ".join(bits) if bits else "trattamento di riferimento"
        return f"Paziente in {ctx}: requisito di ambito della Nota 01 soddisfatto."
    return ("Il paziente non è in trattamento cronico con FANS né in terapia "
            "antiaggregante con ASA — la Nota 01 non si applica.")


def _h_n01_incl(facts: dict, pd: dict, tv: str) -> str:
    risk_factors = []
    rf_keys = {
        "pregresse_emorragie_digestive": "pregresse emorragie digestive",
        "ulcera_peptica_non_guarita": "ulcera peptica non guarita",
        "terapia_concomitante_anticoagulanti": "anticoagulanti concomitanti",
        "terapia_concomitante_cortisonici": "cortisonici concomitanti",
        "eta_avanzata": "età avanzata",
    }
    for k, lbl in rf_keys.items():
        if pd.get(k):
            risk_factors.append(lbl)
    if tv == "TRUE":
        rf = ", ".join(risk_factors) if risk_factors else "fattore di rischio gastrointestinale"
        return (f"Almeno un fattore di rischio gastrointestinale presente "
                f"({rf}) — criterio di inclusione soddisfatto.")
    return ("Nessun fattore di rischio gastrointestinale presente: "
            "il gastroprotettore non è prescrivibile a carico del SSN.")


def _h_n01_routing(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Il farmaco diclofenac+misoprostolo è una combinazione FANS+gastroprotettore "
                "ed è valutato secondo i criteri della Nota 66, non della Nota 01.")
    return "Nessuna eccezione di routing applicabile."


def _h_n01_triple(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Triple therapy in atto (FANS + anticoagulante): rischio emorragico aumentato. "
                "Considerare attentamente l'indicazione.")
    return "Nessuna triple therapy: niente avviso clinico aggiuntivo."


def _h_n13_scope(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Dislipidemia diagnosticata, ipotiroidismo escluso, dieta seguita "
                "almeno 3 mesi: requisiti di ambito della Nota 13 soddisfatti.")
    missing = []
    if not pd.get("dislipidemia_diagnosticata"):
        missing.append("diagnosi di dislipidemia")
    if not pd.get("ipotiroidismo_escluso"):
        missing.append("esclusione ipotiroidismo")
    if not pd.get("dieta_seguita_almeno_3_mesi"):
        missing.append("dieta seguita ≥ 3 mesi")
    if missing:
        return "Mancano: " + ", ".join(missing) + " — la Nota 13 non si applica."
    return "I criteri di ambito della Nota 13 non sono soddisfatti."


def _h_n13_incl(facts: dict, pd: dict, tv: str) -> str:
    risk = pd.get("rischio_cv_score_pct")
    ldl = pd.get("ldl_mg_dl")
    if tv == "TRUE":
        bits = []
        if risk is not None:
            bits.append(f"rischio CV {risk}%")
        if ldl is not None:
            bits.append(f"LDL {ldl} mg/dL")
        ctx = " · ".join(bits) if bits else "profilo lipidico documentato"
        return f"Profilo lipidico ammissibile ({ctx}) — criterio di inclusione soddisfatto."
    return "Profilo lipidico non rientra nei criteri di inclusione della Nota 13."


def _h_n13_path(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Tentativo documentato di terapia di primo livello (statina di base) "
                "prima di passare al farmaco proposto: pathway soddisfatto.")
    return ("Manca la documentazione del tentativo di terapia di primo livello — "
            "richiesto per accedere ai farmaci di seconda linea.")


def _h_n13_except1(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return "Eccezione: LDL non controllato + alto rischio cardiovascolare consente bypass del pathway."
    return "Nessuna eccezione di bypass per LDL/rischio applicabile."


def _h_n13_except2(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return "Eccezione: intolleranza documentata alle statine consente bypass."
    return "Nessuna intolleranza alle statine documentata."


def _h_n66_scope(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return "Indicazione FANS appropriata — ambito Nota 66 soddisfatto."
    return "Indicazione FANS fuori ambito Nota 66."


def _h_n66_incl(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return "Il farmaco proposto è in lista chiusa Nota 66 (FANS rimborsabili)."
    return "⚠️ Il farmaco proposto NON è in lista chiusa Nota 66 — non rimborsabile."


def _h_n66_excl_ulcera(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuna ulcera peptica non guarita."
    return "⚠️ Ulcera peptica non guarita — controindicazione ai FANS."


def _h_n66_excl_scompenso(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuno scompenso cardiaco grave."
    return "⚠️ Scompenso cardiaco grave — i FANS sono controindicati."


def _h_n66_excl_coxib(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Profilo CV compatibile con uso di coxib."
    return "⚠️ Coxib (COX-2 selettivo) controindicati per rischio CV elevato."


def _h_n66_excl_nimesulide(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nimesulide utilizzabile in seconda linea (limiti epatici rispettati)."
    return ("⚠️ Nimesulide controindicata per epatotossicità "
            "(epatopatia, abuso alcool o farmaci epatotossici concomitanti).")


def _h_n66_excl_allergia(facts: dict, pd: dict, tv: str) -> str:
    if tv == "FALSE":
        return "Nessuna allergia nota ai FANS."
    return "⚠️ Allergia ai FANS documentata — controindicazione."


def _h_n66_warn_triple(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return ("Triple therapy (FANS + ASA antiaggregante): rischio emorragico cumulativo "
                "elevato. Adottare gastroprotezione.")
    return "Nessuna triple therapy."


def _h_n66_warn_epato(facts: dict, pd: dict, tv: str) -> str:
    if tv == "TRUE":
        return "Epatopatia attiva: monitorare la funzione epatica durante la terapia."
    return "Funzione epatica nei limiti."


# Mappa rule_id → humanizer
RULE_HUMANIZER: dict[str, callable] = {
    "N97_SCOPE_001": _h_n97_scope,
    "N97_PATH_001": _h_n97_path,
    "N97_EXCL_HARD_ALL2_EMORRAGIA": _h_excl_emorragia,
    "N97_EXCL_HARD_ALL2_DIATESI": _h_excl_diatesi,
    "N97_EXCL_HARD_ALL2_GRAVIDANZA": _h_excl_gravidanza,
    "N97_EXCL_HARD_ALL2_IPERSENSIBILITA": _h_excl_ipersensib,
    "N97_EXCL_HARD_ALL2_VALV": _h_excl_valv,
    "N97_EXCL_HARD_VFG_BASSA": _h_excl_vfg,
    "N97_EXCL_HARD_PESO_BASSO": _h_excl_peso,
    "N01_SCOPE_001": _h_n01_scope,
    "N01_INCL_001": _h_n01_incl,
    "N01_EXCEPT_001": _h_n01_routing,
    "N01_GWARN_001": _h_n01_triple,
    "N13_SCOPE_001": _h_n13_scope,
    "N13_INCL_001": _h_n13_incl,
    "N13_PATH_001": _h_n13_path,
    "N13_EXCEPT_001": _h_n13_except1,
    "N13_EXCEPT_002": _h_n13_except2,
    "N66_SCOPE_001": _h_n66_scope,
    "N66_INCL_001": _h_n66_incl,
    "N66_INCL_002": _h_n66_incl,
    "N66_INCL_003": _h_n66_incl,
    "N66_EXCL_HARD_ULCERA": _h_n66_excl_ulcera,
    "N66_EXCL_HARD_SCOMPENSO": _h_n66_excl_scompenso,
    "N66_EXCL_HARD_COXIB_CV": _h_n66_excl_coxib,
    "N66_EXCL_HARD_NIMESULIDE": _h_n66_excl_nimesulide,
    "N66_EXCL_HARD_ALLERGIA": _h_n66_excl_allergia,
    "N66_GWARN_001": _h_n66_warn_triple,
    "N66_GWARN_002": _h_n66_warn_epato,
}


def humanize_factor(rule_id: str, facts: dict, pd: dict, tv: str, anchor: dict | None = None) -> str:
    """Restituisce una frase clinica completa per la regola applicata."""
    fn = RULE_HUMANIZER.get(rule_id)
    if fn is not None:
        try:
            return fn(facts or {}, pd, tv)
        except Exception:
            pass
    # Fallback: prova ad usare l'excerpt PDF
    if anchor and anchor.get("excerpt"):
        ex = anchor["excerpt"].strip().strip('"')
        return f"Verifica della regola: « {ex} » → esito {tv}."
    return f"Regola `{rule_id}` valutata = **{tv}**."


def synthesize_decision_summary(eval_result: dict, drug_id: str, nota_id: str,
                                  patient_full_name: str) -> dict[str, Any]:
    """Restituisce headline + narrative + key_factors + ..."""
    decision = eval_result.get("reimbursement_decision")
    status = eval_result.get("decision_status")
    route_to = eval_result.get("route_to") or eval_result.get("route_to_nota")
    rag = eval_result.get("rag_payload") or {}
    blocking = rag.get("blocking_rules") or []
    passed = rag.get("passed_rules") or []
    flags = eval_result.get("clinical_flags") or []
    missing = eval_result.get("missing_fields_coverage") or []
    trace = eval_result.get("coverage_trace") or []

    # Patient data dal trace (per humanizers)
    pd: dict = {}
    for entry in trace:
        for k, v in (entry.get("facts_used") or {}).items():
            pd[k] = v

    # Headline + narrative
    if status == "ROUTED":
        headline = f"Il farmaco è soggetto alla **Nota {route_to}**, non alla Nota {nota_id}."
        narrative = ("Il rule engine ha rilevato che la prescrizione di questo farmaco "
                     f"deve essere valutata secondo i criteri della Nota {route_to}. "
                     "La valutazione corrente viene quindi rinviata.")
    elif decision == "RIMBORSABILE":
        headline = (f"La prescrizione di **{drug_id}** per "
                    f"{patient_full_name} è **rimborsabile** dal SSN.")
        n_passed = len(passed)
        narrative = (f"Tutti i requisiti della Nota {nota_id} sono soddisfatti: "
                     f"{n_passed} regole determinanti sono state verificate con esito positivo. ")
        if flags:
            narrative += (f"Sono stati emessi {len(flags)} flag clinici di guida — "
                          "vanno considerati nella prescrizione ma non bloccano la rimborsabilità.")
    elif decision == "NON_RIMBORSABILE":
        headline = (f"La prescrizione di **{drug_id}** per "
                    f"{patient_full_name} **non è rimborsabile** dal SSN.")
        if blocking:
            n = len(blocking)
            narrative = (f"Il rule engine ha individuato {n} regola{'e' if n != 1 else ''} "
                         f"che imped{'ono' if n != 1 else 'isce'} la rimborsabilità "
                         f"(vedi sotto i fattori determinanti).")
        else:
            narrative = "Una regola fail-fast ha bloccato la prescrizione."
    elif decision == "NON_DETERMINABILE":
        headline = (f"Non è possibile determinare la rimborsabilità di "
                    f"**{drug_id}** per {patient_full_name}.")
        if missing:
            ms = ", ".join(f"`{m}`" for m in missing[:6])
            narrative = (f"Mancano dati clinici essenziali per applicare la Nota: "
                         f"{ms}{'…' if len(missing) > 6 else ''}. "
                         "Una volta forniti, il sistema può completare la valutazione.")
        else:
            narrative = "Una o più regole hanno restituito UNKNOWN per dati incompleti."
    else:
        headline = f"Decisione: {decision}"
        narrative = ""

    # Key factors: humanize ogni rule (passed + blocking)
    key_factors: list[dict] = []
    seen_rules: set[str] = set()
    for entry in trace:
        rid = entry.get("rule_id", "")
        if not rid or rid in seen_rules:
            continue
        seen_rules.add(rid)
        tv = entry.get("truth_value", "?")
        outcome = entry.get("outcome", "")
        anchor = entry.get("anchor") or {}
        sentence = humanize_factor(rid, entry.get("facts_used") or {}, pd, tv, anchor)
        is_blocking = any(r.get("rule_id") == rid for r in blocking)
        is_passed = any(r.get("rule_id") == rid for r in passed)
        # Determina "kind" e icona
        if is_blocking:
            kind = "blocking"
            if status == "ROUTED":
                icon = "↪️"
            elif tv == "UNKNOWN":
                icon = "❓"
            else:
                icon = "❌" if "EXCL" in rid else "🚫"
        else:
            kind = "passed"
            icon = "✓"
        key_factors.append({
            "rule_id": rid,
            "sentence": sentence,
            "icon": icon,
            "kind": kind,
            "phase": entry.get("phase", -1),
            "anchor_pdf": anchor.get("pdf_file", ""),
            "anchor_page": anchor.get("page", ""),
            "anchor_section": anchor.get("section", ""),
            "anchor_excerpt": anchor.get("excerpt", ""),
            "tv": tv,
        })

    # Phase summary (per i dettagli tecnici)
    by_phase: dict[int, list[dict]] = {}
    for e in trace:
        by_phase.setdefault(e.get("phase", -1), []).append(e)
    phase_summary = []
    for ph in sorted(by_phase):
        rules = by_phase[ph]
        phase_summary.append({
            "phase": ph,
            "title": PHASE_TITLES.get(ph, f"Fase {ph}"),
            "n_rules": len(rules),
            "n_true": sum(1 for r in rules if r.get("truth_value") == "TRUE"),
            "n_false": sum(1 for r in rules if r.get("truth_value") == "FALSE"),
            "n_unknown": sum(1 for r in rules if r.get("truth_value") == "UNKNOWN"),
            "rules": rules,
        })

    return {
        "headline": headline,
        "narrative": narrative,
        "key_factors": key_factors,
        "missing_fields": missing,
        "clinical_flags": flags,
        "route_to": route_to,
        "phase_summary": phase_summary,
    }


def evidence_for_decision(eval_result: dict, only_blocking: bool = False) -> list[dict]:
    """Restituisce le evidenze normative verbatim per giustificare la decisione."""
    rag = eval_result.get("rag_payload") or {}
    blocking = rag.get("blocking_rules") or []
    passed = rag.get("passed_rules") or []
    rules_to_use = blocking if only_blocking else (list(blocking) + list(passed))
    seen: set[tuple[str, int]] = set()
    out: list[dict] = []
    for r in rules_to_use:
        anchor = r.get("anchor") or {}
        pdf = anchor.get("pdf_file", "")
        page = anchor.get("page", 0)
        if not pdf or not anchor.get("excerpt"):
            continue
        key = (pdf, page)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "rule_id": r.get("rule_id", "?"),
            "pdf_file": pdf,
            "page": page,
            "section": anchor.get("section", ""),
            "excerpt": anchor.get("excerpt", ""),
            "kind": "blocking" if r in blocking else "passed",
        })
    return out
