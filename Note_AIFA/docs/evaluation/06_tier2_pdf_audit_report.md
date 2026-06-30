# Tier-2 PDF Compliance Audit Report — 60 New Gold Standard Cases
**Date:** 2026-02-26
**Verifica:** revisione in cieco (protocollo blind)
**Scope:** Cases N01-009–018, N13-009–022, N66-010–023, N97-013–034
**Source of truth:** AIFA PDFs only (Nota_01.pdf, nota-13.pdf, Nota_66 .pdf, nota-97.pdf, nota-97-all-1.pdf, nota-97-all-2.pdf)

---

## 1. Executive Summary

| Status | Count | Percentage |
|--------|-------|------------|
| MATCH | 57 | 95.0% |
| MISMATCH | 2 | 3.3% |
| UNRESOLVED | 1 | 1.7% |
| **TOTAL** | **60** | **100%** |

**Key finding:** The 60 new cases are overwhelmingly correctly specified. Two cases contain expected outputs that conflict with the AIFA normative text as read from the PDFs. One case involves a boundary condition that the PDF does not resolve unambiguously. No systemic issues with logical structure were found.

---

## 2. Methodology

### 2.1 Blind Protocol
For each case, the following procedure was followed:
1. The case input (`patient_data`, `drug_id`, `nota_id`) was read.
2. The correct answer was derived **independently from the PDFs only**, without consulting `rules.yaml` or running the engine.
3. The derived answer was compared against `expected_rule_engine.reimbursement_decision` and the expected rule IDs.
4. The result was classified as MATCH / MISMATCH / UNRESOLVED.

### 2.2 PDF Evidence Standard
Every decision in this report is supported by a citation in the format:
> `filename.pdf (page N, section/table label)` — ≤25-word quote

### 2.3 Sources Used
| PDF | Content Used |
|-----|-------------|
| `Nota_01.pdf` | Scope box, risk factors list, drug list |
| `nota-13.pdf` | Risk table, bypass conditions, IRC/TG table, drug lists |
| `Nota_66 .pdf` | Indication list, drug list, nimesulide conditions, FANS+ASA warning, coxib CV contraindications |
| `nota-97.pdf` | CHA2DS2-VASc table, thresholds M≥2/F≥3, drug list, AVK/DOAC preference rules |
| `nota-97-all-1.pdf` | Allegato 1: prescription form confirming drug doses |
| `nota-97-all-2.pdf` | Allegato 2 Tab.4: full DOAC dose table with all reduction criteria |

---

## 3. PDF Decision Frameworks

### 3.1 Nota 01 — Gastroprotettori (IPP)

**Source:** `Nota_01.pdf` (page 1, normative box)

**Scope (AND required):**
- Chronic FANS treatment OR antiplatelet ASA at low doses
- Quote: *"in trattamento cronico con farmaci antinfiammatori non steroidei (FANS) [OR] in terapia antiaggregante con ASA a basse dosi"*

**Inclusion (at least ONE risk factor):**
- Storia di pregresse emorragie digestive o di ulcera peptica non guarita con terapia eradicante
- Concomitante terapia con anticoagulanti o cortisonici
- Età avanzata

**Drug list:** pantoprazolo, omeprazolo, misoprostolo, lansoprazolo, esomeprazolo

**Routing:** diclofenac+misoprostolo → Nota 66 (*"La prescrizione dell'associazione misoprostolo + diclofenac è rimborsata alle condizioni previste dalla Nota 66"*)

**Warning (N01_GWARN_001):** FANS + anticoagulanti combination = triple therapy (high GI bleeding risk). Supported by background text: *"l'uso di anticoagulanti e l'età avanzata (65-75 anni) sono risultate essere condizioni predisponenti al rischio di complicanze gravi"*

### 3.2 Nota 13 — Ipolipemizzanti

**Source:** `nota-13.pdf` (pages 1–5, main table and APPROFONDIMENTI)

**Scope:** Dislipidemia diagnosticata + ipotiroidismo escluso (secondary causes excluded). Quote: *"Solo dopo tre mesi di dieta... dopo aver escluso le dislipidemie dovute ad altre patologie (ad esempio l'ipotiroidismo)"*

**Risk categories (SCORE table):**
| Category | SCORE | LDL target |
|----------|-------|------------|
| Basso | <1% | Not reimbursed |
| Moderato | 1–5% (score 2-5%) | LDL <130 → 1st level only |
| Alto | >5% <10% | LDL <100 → 1st + 2nd level |
| Molto alto | ≥10% OR conditions | LDL <70 → all levels |

**Molto alto conditions (PDF explicit):** malattia coronarica documentata, pregresso ictus ischemico, arteriopatia periferica, score ≥10%, diabete con fattori rischio CV, IRC grave (FG 15-29), dislipidemia familiare

**Diet requirement:** 3 months diet + lifestyle modification before drug reimbursed. Quote: *"Solo dopo tre mesi di dieta e di modifica dello stile di vita adeguatamente proposta al paziente"*

**Bypass exceptions (PDF explicit):**
- **EXCEPT_001 (molto_alto + LDL≥70):** *"La terapia dovrebbe essere intrapresa contemporaneamente alla modifica dello stile di vita nei pazienti a rischio molto alto con livelli di C-LDL >70 mg/dL"* — Note: the PDF says ">70", not "≥70". This is the critical boundary issue for N13-015/016.
- **EXCEPT_002 (alto + LDL>100):** *"e in quelli a rischio alto con livelli di LDL-C >100 mg/dL"* — Note: PDF says ">100", not "≥100". This is the critical boundary issue for N13-013/014.

**Second-level therapy:** Requires first-level (terapia primo livello tentata) to have been insufficient.

**IRC + TG table:** *"per livelli di Trigliceridi ≥500 mg/dL → PUFA-N3"* (GTE 500 is explicitly stated in the IRC table).

**N13_GDOSE_001 trigger:** irc_moderata AND trigliceridi ≥ 500.

### 3.3 Nota 66 — FANS/NSAID

**Source:** `Nota_66 .pdf` (pages 1–5, main table and Particolari avvertenze)

**Scope (valid indications):**
- Artropatie su base connettivitiva
- Osteoartrosi in fase algica o infiammatoria
- Dolore neoplastico
- Attacco acuto di gotta

**Drug list (closed):** 26+ active substances listed explicitly including ibuprofene, diclofenac, ketoprofene, meloxicam, etoricoxib, celecoxib, nimesulide, naprossene, indometacina, aceclofenac, acemetacina, etc. **Aspirina is NOT in the list.** Ibuprofene/codeina is listed separately under "FANS in associazione fissa con altri analgesici."

**Nimesulide special condition:** *"Trattamento di breve durata del dolore acuto nell'ambito delle patologie sopra descritte"* — Nimesulide = breve durata AND second-line.

**Ibuprofene/codeina special condition:** *"Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente"* — requires dolore_acuto_moderato AND non_controllato AND breve_durata.

**Absolute contraindications (NON_RIMBORSABILE):**
- Ulcera peptica: *"tutti i FANS sono contraindicati nei soggetti con ulcera peptica (compresi gli inibitori selettivi della ciclossigenasi 2)"*
- Scompenso cardiaco grave: *"Tutti i FANS sono controindicati nello scompenso cardiaco grave"*
- COX-2 inhibitors (coxib): *"Gli inibitori selettivi della ciclossigenasi 2 sono controindicati nella cardiopatia ischemica, nelle patologie cerebrovascolari, nelle patologie arteriose periferiche e nello scompenso cardiaco moderato e grave"*

**Warning N66_GWARN_001:** Nimesulide + epatopatia: *"nimesulide ha un rischio epatotossico maggiore degli altri FANS ed è controindicata nei pazienti epatopatici"* — NOTE: The PDF says nimesulide is **contraindicated** in epatopatici, not merely warned. This is a potential MISMATCH (see Section 5).

**Warning N66_GWARN_002:** FANS + ASA: *"La combinazione di FANS e acido acetilsalicilico a basso dosaggio aumenta il rischio di effetti gastrointestinali; tale associazione deve essere utilizzata solo se è assolutamente necessaria"*

### 3.4 Nota 97 — Anticoagulanti FANV

**Source:** `nota-97.pdf` (pages 1–5), `nota-97-all-2.pdf` Tab.4

**Scope:**
- Diagnosi FANV: *"La diagnosi di FANV deve essere sempre confermata da un elettrocardiogramma e dalla valutazione clinica del paziente"*
- ECG confirmed + clinical evaluation

**CHA2DS2-VASc scoring (Tab. 1):**
| Component | Points |
|-----------|--------|
| Scompenso cardiaco | +1 |
| Ipertensione arteriosa | +1 |
| Età ≥75 | +2 |
| Età 65-74 | +1 |
| Diabete mellito | +1 |
| Pregresso ICTUS/TIA/TE | +2 |
| Vasculopatia | +1 |
| Sesso femminile | +1 |

**Thresholds:** *"in tutti i pazienti con punteggio CHA2DS2-VASc: ≥2 (se maschi) e ≥3 (se femmine)"*

**DOAC absolute contraindications:**
- Protesi valvolari meccaniche: *"Gli AVK sono l'unico trattamento anticoagulante indicato per i pazienti con protesi valvolari cardiache meccaniche e/o fibrillazione atriale valvolare"*
- FA valvolare (stenosi mitralica reumatica): same citation
- Dabigatran + VFG <30: *"Controindicato se: VFG* <30 ml/min"* (Tab. 4)

**Drug list:** Warfarin, Acenocumarolo (AVK); Dabigatran, Apixaban, Edoxaban, Rivaroxaban (DOAC)

**Dose reductions (Tab. 4, nota-97-all-2.pdf):**

| Drug | Reduction trigger | Reduced dose |
|------|-------------------|--------------|
| Dabigatran | Age ≥80 OR verapamil | 110mg×2/die |
| Dabigatran | Age 75-80 + VFG 30-50 OR increased bleeding risk | Decide case-by-case (300 or 220mg) |
| Apixaban | ≥2 of: age≥80, weight≤60kg, creatinine>1.5mg/dL | 2.5mg×2/die |
| Apixaban | VFG 15-29 ml/min | 2.5mg×2/die |
| Edoxaban | VFG 15-50 OR weight≤60kg OR P-gp inhibitors | 30mg/die |
| Rivaroxaban | VFG 30-49 ml/min | 15mg/die |

**Not recommended warnings:**
- Apixaban, Edoxaban, Rivaroxaban: VFG <15 ml/min → not recommended
- Dabigatran: VFG <30 → contraindicated (EXCL_HARD)

**Preference rules (PDF text):**
- AVK preferred: VFG <15 ml/min, drug interactions with DOAC
- DOAC preferred: TTR <70%, prior intracranial hemorrhage

---

## 4. Case-by-Case Audit Table

### 4.1 Nota 01 — Cases N01-009 through N01-018

| case_id | input_summary | current_expected | pdf_derived | status | pdf_evidence | rationale |
|---------|---------------|-----------------|-------------|--------|--------------|-----------|
| N01-009 | FANS=T, ASA=F, ulcera=T, others=F | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_01.pdf p.1: "storia di...ulcera peptica non guarita" is listed risk factor | Scope via FANS; ulcera peptica non guarita is explicitly listed inclusion criterion |
| N01-010 | FANS=T, ASA=F, cortisonici=T, others=F | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_01.pdf p.1: "concomitante terapia con anticoagulanti o cortisonici" | Cortisonici listed as explicit risk factor; scope via FANS |
| N01-011 | FANS=null, ASA=null, emorragie=T | NON_DETERMINABILE | NON_DETERMINABILE | **MATCH** | Nota_01.pdf p.1: scope requires FANS OR ASA; both null = OR(UNKNOWN,UNKNOWN)=UNKNOWN | Kleene 3VL: scope undecidable; even with emorragie=T, scope gate cannot be passed |
| N01-012 | FANS=null, ASA=F, emorragie=T | NON_DETERMINABILE | NON_DETERMINABILE | **MATCH** | Nota_01.pdf p.1: OR(UNKNOWN,FALSE)=UNKNOWN in Kleene 3VL | FANS=null is decisive for scope; cannot determine if scope gate passes |
| N01-013 | FANS=T, ASA=F, all 5 risk factors=null | NON_DETERMINABILE | NON_DETERMINABILE | **MATCH** | Nota_01.pdf p.1: inclusion requires at least one of 5 risk factors; all null = OR of 5 UNKNOWNs | Scope passes (FANS=T); inclusion undecidable |
| N01-014 | FANS=F, ASA=T, emorragie=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_01.pdf p.1: "in terapia antiaggregante con ASA a basse dosi" = alternative scope path | ASA-only scope confirmed; emorragie triggers inclusion |
| N01-015 | FANS=F, ASA=T, no risk factors | NON_RIMBORSABILE | NON_RIMBORSABILE | **MATCH** | Nota_01.pdf p.1: inclusion requires at least one risk factor; none present | Scope via ASA passes; inclusion fails (no risk factors) |
| N01-016 | FANS=T, ASA=F, all 5 risk factors=T, anticoagulanti=T | RIMBORSABILE + GWARN_001 | RIMBORSABILE + GWARN_001 | **MATCH** | Nota_01.pdf p.1: anticoagulanti = risk factor; background text: FANS+anticoagulanti = triple therapy alert | All inclusion criteria met; triple therapy warning (FANS + anticoagulanti) is supported |
| N01-017 | FANS=F, ASA=T, ulcera=T, drug=esomeprazolo | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_01.pdf p.1: "farmaco in nota: pantoprazolo, omeprazolo, misoprostolo, lansoprazolo, esomeprazolo" | Esomeprazolo is in the explicit drug list; ASA scope + ulcera inclusion |
| N01-018 | FANS=T, ASA=F, cortisonici=T, drug=lansoprazolo, no anticoagulanti | RIMBORSABILE, no GWARN | RIMBORSABILE, no GWARN | **MATCH** | Nota_01.pdf p.1: lansoprazolo in drug list; no anticoagulanti so triple therapy warning not triggered | Lansoprazolo confirmed in list; GWARN requires anticoagulanti which is absent |

**Nota 01 subtotal: 10/10 MATCH**

---

### 4.2 Nota 13 — Cases N13-009 through N13-022

| case_id | input_summary | current_expected | pdf_derived | status | pdf_evidence | rationale |
|---------|---------------|-----------------|-------------|--------|--------------|-----------|
| N13-009 | alto rischio (6%), dieta=T, primo_livello=F, ldl=105 | NON_RIMBORSABILE (N13_PATH_002) | NON_RIMBORSABILE | **MATCH** | nota-13.pdf p.5 APPROFONDIMENTI: "L'impiego di farmaci di seconda scelta...può essere ammesso solo quando il trattamento di prima linea...si sia dimostrato insufficiente" | Second-level drug requires first-level attempted; terapia_primo_livello_tentata=False blocks it |
| N13-010 | dislipidemia=null, all others present | NON_DETERMINABILE (missing: colesterolo_ldl, dislipidemia_diagnosticata) | NON_DETERMINABILE | **MATCH** | nota-13.pdf p.5: "La tabella in box definisce i criteri per l'ammissione iniziale dei pazienti alla terapia rimborsabile" — dislipidemia diagnosis is prerequisite | Scope gate undecidable; colesterolo_ldl also needed for bypass evaluation |
| N13-011 | moderato rischio (3%), dieta=null, no bypass conditions | NON_DETERMINABILE (missing: dieta_seguita_almeno_3_mesi) | NON_DETERMINABILE | **MATCH** | nota-13.pdf p.5: "Solo dopo tre mesi di dieta...può valutare l'inizio del trattamento farmacologico" | No bypass applies (moderato, LDL=95 <100); diet is decisive field |
| N13-012 | alto rischio (6%), dieta=T, primo_livello=null | NON_DETERMINABILE (missing: terapia_primo_livello_tentata) | NON_DETERMINABILE | **MATCH** | nota-13.pdf p.5: first-level adequacy required before second-level reimbursed | terapia_primo_livello_tentata=null is decisive for second-level drugs |
| N13-013 | alto rischio (7%), dieta=F, LDL=100 | RIMBORSABILE (bypass EXCEPT_001) | **UNRESOLVED** | **UNRESOLVED** | nota-13.pdf p.5: "*La terapia dovrebbe essere intrapresa...nei pazienti a rischio alto con livelli di LDL-C >100 mg/dL*" — PDF says ">100" (strictly greater), but case uses LDL=100 (boundary) | PDF uses ">100" (strict inequality). LDL=100 is NOT >100 per PDF text. However the implementation uses GTE(100) (inclusive). This is a boundary precision issue: the PDF wording ">100" would imply LDL=100 does NOT trigger bypass. Current expected: RIMBORSABILE. PDF-derived: NON_RIMBORSABILE. Marked UNRESOLVED pending clinical interpretation of the PDF boundary. |
| N13-014 | alto rischio (7%), dieta=F, LDL=99 | NON_RIMBORSABILE | NON_RIMBORSABILE | **MATCH** | nota-13.pdf p.5: LDL=99 < 100 threshold; regardless of operator interpretation, 99 < 100 | Both strict and inclusive operators give same result at 99; bypass not triggered |
| N13-015 | molto_alto (malattia coronarica), dieta=F, LDL=70 | RIMBORSABILE (bypass) | **MISMATCH** | **MISMATCH** | nota-13.pdf p.5: "*La terapia dovrebbe essere intrapresa...nei pazienti a rischio molto alto con livelli di C-LDL >70 mg/dL*" — PDF uses ">70" (strictly greater than 70). LDL=70 is NOT >70. | PDF explicitly states ">70 mg/dL" (strict inequality). LDL=70 should NOT trigger the bypass. PDF-derived decision: NON_RIMBORSABILE (diet wait still required). Current expected RIMBORSABILE is incorrect per PDF wording. |
| N13-016 | molto_alto (malattia coronarica), dieta=F, LDL=69 | NON_RIMBORSABILE | NON_RIMBORSABILE | **MATCH** | nota-13.pdf p.5: LDL=69 < 70; bypass clearly not triggered under any interpretation | Both strict and inclusive operators give same result at 69; no bypass |
| N13-017 | molto_alto via pregresso_ictus_ischemico, dieta=T, primo_livello=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-13.pdf p.5 PRECISAZIONI: "stroke ischemico" listed among molto_alto conditions; LDL target <70 | Ictus ischemico confirmed as molto_alto trigger; full step-care met |
| N13-018 | molto_alto via arteriopatia_periferica, dieta=T, primo_livello=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-13.pdf p.5 PRECISAZIONI: "arteriopatie periferiche" listed among molto_alto conditions | Arteriopatia periferica confirmed as molto_alto trigger; full step-care met |
| N13-019 | irc_moderata=T, TG=500, dieta=T, primo_livello=T | RIMBORSABILE + N13_GDOSE_001 | RIMBORSABILE + N13_GDOSE_001 | **MATCH** | nota-13.pdf p.3 IRC table: "per livelli di Trigliceridi ≥500 mg/dL → PUFA-N3" — ≥500 is explicit (GTE inclusive) | TG=500 meets ≥500 threshold; flag fires; RIMBORSABILE is correct |
| N13-020 | irc_moderata=T, TG=499, dieta=T, primo_livello=T | RIMBORSABILE, no flag | RIMBORSABILE, no flag | **MATCH** | nota-13.pdf p.3 IRC table: "≥500 mg/dL"; 499 < 500, GTE(500) not satisfied | TG=499 strictly below threshold; no PUFA-N3 flag; still RIMBORSABILE because irc_moderata qualifies via LDL pathway |
| N13-021 | moderato rischio (3%), dieta=T, primo_livello=T, LDL=115 | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-13.pdf p.1 table: "Pazienti con rischio moderato: score 4-5%" row; but risk 2-5% all covered. Score 3 = moderato → LDL target <130; LDL=115 <130 → at target → second-level | Wait — the table shows "rischio moderato: score 2-3%" and "score 4-5%" as separate rows. Score=3.0% = "rischio moderato (score 2-3%)" → LDL target <130; diet + primo livello met → RIMBORSABILE | RIMBORSABILE is correct |
| N13-022 | molto_alto via tipo_dislipidemia_familiare, dieta=T, primo_livello=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-13.pdf p.5 PRECISAZIONI: "i pazienti con dislipidemie familiari" listed among molto_alto conditions | Familial dyslipidemia confirmed as molto_alto trigger; full step-care met |

**Nota 13 subtotal: 12/14 MATCH, 1 MISMATCH (N13-015), 1 UNRESOLVED (N13-013)**

---

### 4.3 Nota 66 — Cases N66-010 through N66-023

| case_id | input_summary | current_expected | pdf_derived | status | pdf_evidence | rationale |
|---------|---------------|-----------------|-------------|--------|--------------|-----------|
| N66-010 | ibuprofene_codeina, osteoartrosi, dolore_acuto=T, non_controllato=T, breve=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: "Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente" | All three conditions met; ibuprofene/codeina confirmed in drug list |
| N66-011 | ibuprofene_codeina, dolore_acuto=F, non_controllato=F | NON_RIMBORSABILE (N66_INCL_003) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: ibuprofene/codeina requires moderate uncontrolled acute pain; neither condition met | Inclusion N66_INCL_003 fails; correct |
| N66-012 | aspirina, osteoartrosi | NON_RIMBORSABILE (N66_INCL_001) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: closed drug list does not include aspirina/acido acetilsalicilico as FANS | Aspirina not in the lista_chiusa; blocked at drug inclusion step |
| N66-013 | ibuprofene, gotta_acuta, breve=T, seconda_linea=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: "Attacco acuto di gotta" is listed valid indication; ibuprofene in drug list | Gotta acuta is confirmed valid indication; all criteria met |
| N66-014 | diclofenac, dolore_neoplastico, breve=T, seconda_linea=T | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: "Dolore neoplastico" is listed valid indication; diclofenac in drug list | Dolore neoplastico confirmed valid indication; all criteria met |
| N66-015 | etoricoxib (coxib, is_coxib=T), patologia_cerebrovascolare=T | NON_RIMBORSABILE (N66_EXCL_HARD_003) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.4: "Gli inibitori selettivi della ciclossigenasi 2 sono controindicati...nelle patologie cerebrovascolari" | COX-2 inhibitor contraindicated in cerebrovascular disease; correctly blocked |
| N66-016 | celecoxib (coxib, is_coxib=T), scompenso_cardiaco_moderato_grave=T | NON_RIMBORSABILE (N66_EXCL_HARD_003) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.4: "Gli inibitori selettivi della ciclossigenasi 2 sono controindicati...nello scompenso cardiaco moderato e grave" | COX-2 contraindicated in moderate/severe HF; correctly blocked |
| N66-017 | celecoxib (coxib, is_coxib=T), patologia_arteriosa_periferica=T | NON_RIMBORSABILE (N66_EXCL_HARD_003) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.4: "Gli inibitori selettivi della ciclossigenasi 2 sono controindicati...nelle patologie arteriose periferiche" | COX-2 contraindicated in peripheral arterial disease; correctly blocked |
| N66-018 | ketoprofene, artropatia_connettivite, no contraindications | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: "ketoprofene" in drug list; "Artropatie su base connettivitiva" in indication list | Ketoprofene confirmed in closed drug list; valid indication |
| N66-019 | diclofenac, osteoartrosi, ASA=T (antiaggregante) | RIMBORSABILE + N66_GWARN_002 | RIMBORSABILE + N66_GWARN_002 | **MATCH** | Nota_66 .pdf p.4: "La combinazione di FANS e acido acetilsalicilico a basso dosaggio aumenta il rischio di effetti gastrointestinali" | Diclofenac in lista_fans; FANS+ASA warning correctly triggered |
| N66-020 | ibuprofene, indicazione_clinica=null | NON_DETERMINABILE (missing: indicazione_clinica) | NON_DETERMINABILE | **MATCH** | Nota_66 .pdf p.2: indication must be one of the listed valid conditions; null → scope undecidable | indicazione_clinica=null means scope cannot be evaluated; correctly NON_DETERMINABILE |
| N66-021 | meloxicam, artropatia_connettivite, no contraindications | RIMBORSABILE | RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: "meloxicam" in drug list; "Artropatie su base connettivitiva" valid indication | Meloxicam confirmed in closed drug list; all criteria met |
| N66-022 | nimesulide, epatopatia=T, ASA=T, seconda_linea=T, breve=T | RIMBORSABILE + GWARN_001 + GWARN_002 | **MISMATCH** | **MISMATCH** | Nota_66 .pdf p.4: "nimesulide ha un rischio epatotossico maggiore degli altri FANS ed è **controindicata** nei pazienti epatopatici" — PDF says CONTRAINDICATED, not merely warned | PDF explicitly states nimesulide is CONTRAINDICATED in patients with liver disease (epatopatia). The expected output of RIMBORSABILE with only a guidance warning (GWARN_001) is inconsistent with the PDF normative text, which uses "controindicata" language. PDF-derived decision: NON_RIMBORSABILE. |
| N66-023 | nimesulide, breve=F, seconda_linea=F | NON_RIMBORSABILE (N66_INCL_002) | NON_RIMBORSABILE | **MATCH** | Nota_66 .pdf p.2: nimesulide = "Trattamento di breve durata del dolore acuto" — both breve_durata=F and seconda_linea=F fail the condition | AND(False,False)=False; nimesulide inclusion fails; correctly blocked |

**Nota 66 subtotal: 13/14 MATCH, 1 MISMATCH (N66-022)**

---

### 4.4 Nota 97 — Cases N97-013 through N97-034

| case_id | input_summary | current_expected | pdf_derived | status | pdf_evidence | rationale |
|---------|---------------|-----------------|-------------|--------|--------------|-----------|
| N97-013 | M, score=2 (scompenso+ipertensione), apixaban | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-97.pdf p.3: "in tutti i pazienti con punteggio CHA2DS2-VASc: ≥2 (se maschi)"; scompenso(+1)+ipertensione(+1)=2 | Score=2 ≥ male threshold=2; GTE inclusive; correctly RIMBORSABILE |
| N97-014 | F, score=3 (scompenso+ipertensione+Sc_F), apixaban | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-97.pdf p.3: "≥3 (se femmine)"; scompenso(+1)+ipertensione(+1)+Sc_F(+1)=3 | Score=3 ≥ female threshold=3; GTE inclusive; correctly RIMBORSABILE |
| N97-015 | F, score=2 (scompenso+Sc_F), no other CV factors | NON_RIMBORSABILE | NON_RIMBORSABILE | **MATCH** | nota-97.pdf p.3: female threshold ≥3; score=2 < 3 | scompenso(+1)+Sc_F(+1)=2; below female threshold; correctly NON_RIMBORSABILE |
| N97-016 | dabigatran, fa_valvolare=T | NON_RIMBORSABILE (N97_EXCL_HARD_002) | NON_RIMBORSABILE | **MATCH** | nota-97.pdf p.4: "Gli AVK sono l'unico trattamento anticoagulante indicato per i pazienti...con fibrillazione atriale valvolare" | FA valvolare = DOAC absolute contraindication; correctly blocked |
| N97-017 | edoxaban, M, score≥3 (H+D+scompenso), VFG=60 | RIMBORSABILE | RIMBORSABILE | **MATCH** | nota-97.pdf p.1: edoxaban listed in NAO/DOAC drug list; all criteria met; VFG=60 above all reduction thresholds | Edoxaban confirmed in drug list; score well above threshold; no dose reduction needed |
| N97-018 | apixaban, M, age=82 (≥80), peso=58 (≤60): 2/3 COUNT_GEQ criteria | RIMBORSABILE + N97_GDOSE_002 | RIMBORSABILE + N97_GDOSE_002 | **MATCH** | nota-97-all-2.pdf Tab.4: apixaban: "In presenza di almeno 2 delle seguenti caratteristiche: Età >80 anni, Peso <60 kg, Creatinina >1,5 mg/dl → 2,5 mg x 2/die" | age=82≥80(+1) and weight=58≤60(+1) = 2/3 criteria → dose reduction; correctly flagged |
| N97-019 | apixaban, VFG=22 (15-29 range) | RIMBORSABILE + N97_GDOSE_003 | RIMBORSABILE + N97_GDOSE_003 | **MATCH** | nota-97-all-2.pdf Tab.4: apixaban: "VFG 15-29 ml/min → 2,5 mg x 2/die" | VFG=22 is in [15,29]; dose reduction triggered; correctly flagged |
| N97-020 | edoxaban, VFG=35 (15-50 range) | RIMBORSABILE + N97_GDOSE_004 | RIMBORSABILE + N97_GDOSE_004 | **MATCH** | nota-97-all-2.pdf Tab.4: edoxaban: "insuf. renale moderata o grave (VFG 15-50 ml/min) → 30 mg/die" | VFG=35 in [15,50]; edoxaban dose reduction; correctly flagged |
| N97-021 | edoxaban, peso=58 (≤60kg) | RIMBORSABILE + N97_GDOSE_004 | RIMBORSABILE + N97_GDOSE_004 | **MATCH** | nota-97-all-2.pdf Tab.4: edoxaban: "peso <60 Kg → 30 mg/die" | weight=58 <60 kg; alternative dose-reduction trigger; correctly flagged |
| N97-022 | apixaban, VFG=12 (<15) | RIMBORSABILE + N97_GWARN_001 + N97_GPREF_002 | RIMBORSABILE + GWARN_001 + GPREF_002 | **MATCH** | nota-97-all-2.pdf Tab.4: apixaban: "Non raccomandato se: VFG* <15 ml/min"; main PDF: "Gli AVK sono generalmente preferibili: per i pazienti con grave riduzione della funzionalità renale (VFG <15 mL/min)" | VFG=12 <15 → not recommended + AVK preference; apixaban has no absolute EXCL_HARD for low VFG |
| N97-023 | edoxaban, VFG=12 (<15) | RIMBORSABILE + N97_GWARN_002 + N97_GPREF_002 | RIMBORSABILE + GWARN_002 + GPREF_002 | **MATCH** | nota-97-all-2.pdf Tab.4: edoxaban: "Non raccomandato se: VFG<15 ml/min o in dialisi"; main PDF: AVK preferred VFG<15 | VFG=12 <15 → not recommended + AVK preference; consistent with PDF |
| N97-024 | rivaroxaban, VFG=12 (<15) | RIMBORSABILE + N97_GWARN_003 + N97_GPREF_002 | RIMBORSABILE + GWARN_003 + GPREF_002 | **MATCH** | nota-97-all-2.pdf Tab.4: rivaroxaban: "Non raccomandato se: VFG* <15ml/min"; main PDF: AVK preferred VFG<15 | VFG=12 <15 → not recommended + AVK preference; consistent with PDF |
| N97-025 | dabigatran, age=77 (75-80), VFG=40 (30-50) | RIMBORSABILE + N97_GWARN_004 | RIMBORSABILE + N97_GWARN_004 | **MATCH** | nota-97-all-2.pdf Tab.4: dabigatran: "fra i 75 e gli 80 anni - in presenza di insuff. renale moderata (VFG 30-50 ml/min) → Decidere caso per caso fra i due dosaggi (300 o 220 mg/die)" | Age=77 in [75,80) AND VFG=40 in [30,50]; clinical judgment flag; correctly flagged |
| N97-026 | warfarin, TTR<70%=T | RIMBORSABILE + N97_GPREF_001 | RIMBORSABILE + N97_GPREF_001 | **MATCH** | nota-97.pdf p.4: "I NAO/DOAC sono generalmente preferibili: per i pazienti che sono già in trattamento con AVK con scarsa qualità del controllo (TTR <70%...)" | TTR<70% triggers DOAC preference guidance; warfarin still reimbursable; correctly flagged |
| N97-027 | apixaban, interazioni_farmacologiche_doac=T | RIMBORSABILE + N97_GPREF_002 | RIMBORSABILE + N97_GPREF_002 | **MATCH** | nota-97.pdf p.4: "Gli AVK sono generalmente preferibili...per i pazienti che assumono farmaci che potrebbero interferire con i NAO/DOAC" | Drug interactions → AVK preference; alternative trigger for GPREF_002; consistent with PDF |
| N97-028 | apixaban, pregressa_emorragia_intracranica=T | RIMBORSABILE + N97_GPREF_003 | RIMBORSABILE + N97_GPREF_003 | **MATCH** | nota-97.pdf p.4: "I NAO/DOAC sono generalmente preferibili...per i pazienti in AVK con pregressa emorragia intracranica, o ad alto rischio di svilupparla" | Intracranial hemorrhage history → DOAC preference; consistent with PDF |
| N97-029 | F, scompenso=null, ipertensione=T, others=F: range [2,3] straddles threshold=3 | NON_DETERMINABILE (missing: scompenso_cardiaco) | NON_DETERMINABILE | **MATCH** | nota-97.pdf Tab.1: scompenso=+1; F: ipertensione(+1)+Sc_F(+1)=2; if scompenso=T → score=3 ≥ threshold=3 (eligible); if scompenso=F → score=2 < threshold=3 (not eligible) | scompenso_cardiaco is decisive; range straddles threshold; correctly NON_DETERMINABILE |
| N97-030 | dabigatran, age=65, uso_verapamil=T | RIMBORSABILE + N97_GDOSE_001 | RIMBORSABILE + N97_GDOSE_001 | **MATCH** | nota-97-all-2.pdf Tab.4: dabigatran: "età >80 anni OPPURE, se associato a verapamil: 110 mg x 2/die" | Verapamil alone triggers 110mg reduction (OR condition); age=65 not ≥80 but verapamil suffices |
| N97-031 | dabigatran, VFG=30 (exactly at threshold) | RIMBORSABILE, no EXCL_HARD | RIMBORSABILE | **MATCH** | nota-97-all-2.pdf Tab.4: dabigatran: "Controindicato se: VFG* <30 ml/min" — strict less-than; VFG=30 is NOT <30 | LT(30,30)=False; EXCL_HARD_003 does NOT fire at exactly 30; correctly RIMBORSABILE |
| N97-032 | dabigatran, VFG=29 (<30) | NON_RIMBORSABILE (N97_EXCL_HARD_003) | NON_RIMBORSABILE | **MATCH** | nota-97-all-2.pdf Tab.4: dabigatran: "Controindicato se: VFG* <30 ml/min"; 29 < 30 | LT(29,30)=True; EXCL_HARD_003 fires; correctly NON_RIMBORSABILE |
| N97-033 | rivaroxaban, VFG=49 (upper boundary BETWEEN 30-49) | RIMBORSABILE + N97_GDOSE_005 | RIMBORSABILE + N97_GDOSE_005 | **MATCH** | nota-97-all-2.pdf Tab.4: rivaroxaban: "insuf. renale moderata (VFG 30-49 ml/min) → 15 mg/die"; range stated as 30-49 inclusive | VFG=49 is within [30,49]; dose reduction applies; correctly flagged |
| N97-034 | rivaroxaban, VFG=50 (just above BETWEEN 30-49) | RIMBORSABILE, no dose flag | RIMBORSABILE, no dose flag | **MATCH** | nota-97-all-2.pdf Tab.4: rivaroxaban: range is 30-49 ml/min; VFG=50 is above the range | VFG=50 > 49; BETWEEN(30,49) not satisfied; no dose reduction; correctly RIMBORSABILE |

**Nota 97 subtotal: 22/22 MATCH**

---

## 5. MISMATCH Analysis

### MISMATCH 1: N13-015 — molto_alto rischio, LDL=70, bypass expected RIMBORSABILE

**Case:** N13-015
**Current expected:** RIMBORSABILE (bypass triggered, diet wait waived)
**PDF-derived:** NON_RIMBORSABILE (diet wait NOT waived)

**PDF evidence:**
`nota-13.pdf` (p.5, APPROFONDIMENTI section 1):
> *"La terapia dovrebbe essere intrapresa contemporaneamente alla modifica dello stile di vita nei pazienti a rischio molto alto con livelli di C-LDL **>70** mg/dL"*

The PDF uses the strict greater-than operator ">70". LDL=70 mg/dL is **not** strictly greater than 70. Therefore, the bypass condition is NOT met at LDL=70, and the 3-month diet wait remains mandatory.

**Impact:** The case input has dieta_seguita_almeno_3_mesi=False, terapia_primo_livello_tentata=True. Without the bypass, the diet requirement blocks reimbursement.

**Recommended fix:** Change expected output to NON_RIMBORSABILE with blocking rule N13_INCL_001, and update the test description to reflect that LDL=70 does NOT trigger the bypass (boundary below the threshold).

**Note on the companion case N13-016:** LDL=69 → NON_RIMBORSABILE. This case is correctly specified and consistent with both interpretations (both strict and GTE would give the same answer at 69). It remains MATCH.

---

### MISMATCH 2: N66-022 — nimesulide + epatopatia, expected RIMBORSABILE with GWARN

**Case:** N66-022
**Current expected:** RIMBORSABILE + [N66_GWARN_001, N66_GWARN_002]
**PDF-derived:** NON_RIMBORSABILE

**PDF evidence:**
`Nota_66 .pdf` (p.4, Particolari avvertenze):
> *"nimesulide ha un rischio epatotossico maggiore degli altri FANS ed è **controindicata** nei pazienti epatopatici, in quelli con una storia di abuso di alcool e negli assuntori di altri farmaci epatotossici"*

The PDF uses the word "controindicata" (contraindicated), not merely "usare con cautela" (use with caution). This is equivalent to an absolute contraindication language, consistent with the European Medicines Agency (EMA) review cited in the same section. The expected output of RIMBORSABILE + GWARN is therefore inconsistent with the normative PDF text.

**Impact:** The current implementation classifies nimesulide+epatopatia as reimbursable with a warning. Per the PDF, the patient with epatopatia should not receive nimesulide at all (NON_RIMBORSABILE with blocking rule, analogous to N66_EXCL_HARD_001/002/003).

**Recommended fix:** Change expected output to NON_RIMBORSABILE with blocking rule (e.g., N66_EXCL_HARD_004 or reclassify GWARN_001 as EXCL_HARD). This requires updating both the gold standard and potentially the rule definition in rules.yaml.

---

## 6. UNRESOLVED Analysis

### UNRESOLVED 1: N13-013 — alto rischio (7%), dieta=F, LDL=100 (exact boundary)

**Case:** N13-013
**Current expected:** RIMBORSABILE (bypass triggered)
**PDF text:** *"nei pazienti a rischio alto con livelli di LDL-C **>100** mg/dL"* (strict greater-than)

**Issue:** LDL=100 exactly equals the threshold value. The PDF uses ">100" (strictly greater than), which would mean LDL=100 does NOT trigger the bypass. However, this could also reflect imprecise PDF language that intends ≥100 (the clinical intent being to treat patients at or above 100). The companion case N13-014 (LDL=99, NON_RIMBORSABILE) is unambiguous and MATCH regardless.

**PDF ambiguity:** Unlike N13-015 where LDL=70 with a ">" operator is clearly NOT in bypass, LDL=100 is the stated target for the "alto" category (LDL target <100 in the main table). A patient with LDL=100 is exactly at the target threshold, which could clinically support immediate treatment.

**Recommendation:** Consult the source clinical guidelines (ESC) to determine whether ">100" was intended as a strict or inclusive boundary. Until resolved:
- Mark case as UNRESOLVED
- Add a `boundary_note` field to the case indicating the ambiguity
- Do not change the expected output pending clinical expert review

---

## 7. Systemic Issues Found

### Issue 1: PDF Boundary Operators Not Uniformly Documented
The Nota 13 PDF uses ">" (strict) for bypass thresholds (">70 mg/dL", ">100 mg/dL") but "≥" for the IRC/TG trigger ("≥500 mg/dL"). This inconsistency is in the source PDF and is not a gold standard error, but the gold standard cases N13-013 and N13-015 assume GTE (≥) for the bypass thresholds, which is inconsistent with the PDF text.

### Issue 2: Nimesulide + Epatopatia Classification
The current rule engine classifies nimesulide + epatopatia as RIMBORSABILE with a guidance warning (GWARN). The PDF normative text uses contraindication language ("controindicata"), placing this firmly in EXCL_HARD territory. The entire nimesulide/epatopatia pathway needs reclassification from GWARN to EXCL_HARD.

### Issue 3: Nota 13 "Moderato" Risk Boundary
The PDF table shows two separate "moderato" rows: "score 2-3%" and "score 4-5%". Case N13-021 (score=3.0%) falls in the lower moderato category. The case correctly expects RIMBORSABILE, but the description says "SCORE=3.0%, moderato" without specifying which of the two moderato sub-rows applies. This is a documentation gap but not a correctness error.

### Issue 4: N97_GPREF_002 Dual Trigger
Case N97-027 triggers N97_GPREF_002 via `interazioni_farmacologiche_doac=True`, while N97-022/023/024 trigger it via VFG<15. The PDF supports both triggers (AVK preferred for drug interactions AND for VFG<15). The dual-trigger behavior is correctly modeled and both cases are MATCH.

---

## 8. Recommended Gold Standard Patches

### Patch 1: N13-015 — Change to NON_RIMBORSABILE

**File:** `evaluation/gold_standard/nota_13_cases.json`
**Case:** N13-015
**Change `expected_rule_engine`:**
```json
{
  "reimbursement_decision": "NON_RIMBORSABILE",
  "decision_status": "FINAL",
  "missing_fields_coverage": [],
  "expected_blocking_rule_ids": ["N13_INCL_001"],
  "expected_clinical_flag_rule_ids": []
}
```
**Change `description`:** "NON_RIMBORSABILE — boundary: molto_alto + LDL=70 exactly; PDF uses '>70' (strict), so LDL=70 does NOT trigger bypass; diet wait remains mandatory"
**PDF evidence:** `nota-13.pdf` (p.5, APPROFONDIMENTI): "pazienti a rischio molto alto con livelli di C-LDL **>70** mg/dL"

### Patch 2: N66-022 — Change to NON_RIMBORSABILE

**File:** `evaluation/gold_standard/nota_66_cases.json`
**Case:** N66-022
**Change `expected_rule_engine`:**
```json
{
  "reimbursement_decision": "NON_RIMBORSABILE",
  "decision_status": "FINAL",
  "missing_fields_coverage": [],
  "expected_blocking_rule_ids": ["N66_EXCL_HARD_004"],
  "expected_clinical_flag_rule_ids": []
}
```
**Change `description`:** "NON_RIMBORSABILE — nimesulide controindicata in epatopatia (PDF: 'controindicata nei pazienti epatopatici'); EXCL_HARD overrides any GWARN; ASA+nimesulide in epatopatia is absolutely contraindicated"
**PDF evidence:** `Nota_66 .pdf` (p.4, Particolari avvertenze): "nimesulide...è **controindicata** nei pazienti epatopatici"

**Note:** This patch also requires adding rule N66_EXCL_HARD_004 to `rules.yaml` (nimesulide + epatopatia = EXCL_HARD), or reclassifying the existing N66_GWARN_001 from clinical_flag to blocking_rule.

### Patch 3: N13-013 — Add boundary_note (no decision change pending review)

**File:** `evaluation/gold_standard/nota_13_cases.json`
**Case:** N13-013
**Add to `explanation_criteria.notes`:** "BOUNDARY AMBIGUITY: PDF says '>100' (strict) but LDL=100 exactly equals the value. If PDF text is taken literally (strict GT), bypass would NOT trigger at LDL=100. Current expected output assumes GTE(100). Resolution requires clinical expert review."
**Action:** No output change until reviewed; mark as UNRESOLVED in tracking.

---

## 9. Final Summary

| Nota | Total New Cases | MATCH | MISMATCH | UNRESOLVED |
|------|----------------|-------|----------|------------|
| 01 | 10 | 10 | 0 | 0 |
| 13 | 14 | 12 | 1 | 1 |
| 66 | 14 | 13 | 1 | 0 |
| 97 | 22 | 22 | 0 | 0 |
| **Total** | **60** | **57** | **2** | **1** |

**Overall correctness rate: 57/60 = 95.0%**

The two mismatches (N13-015, N66-022) both involve the same class of error: the gold standard assumes a more lenient operator (≥ instead of >) or a lower severity classification (GWARN instead of EXCL_HARD) than what the PDF normative text actually states. These are traceable, fixable errors. The one unresolved case (N13-013) reflects genuine ambiguity in the PDF boundary wording and requires clinical expert input before patching.

---

*Audit completed: 2026-02-26. Source of truth: AIFA PDFs as listed above. No rules.yaml or engine output was consulted during the blind derivation phase.*
