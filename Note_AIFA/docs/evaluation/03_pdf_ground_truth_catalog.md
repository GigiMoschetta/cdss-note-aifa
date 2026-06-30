# PDF Ground Truth Catalog — Note AIFA 01 and 66

**Source PDFs:**
- `Nota_01.pdf` (published: 13 December 2009, AIFA website)
- `Nota_66 .pdf` (Determina AIFA G.U. n°197 del 24 agosto 2012; modified G.U. n°246 del 22 ottobre 2018)

**Extraction date:** 2026-02-25
**Estrazione:** lettura diretta del PDF (tutte le pagine)

---

## NOTA 01

### Header

**Farmaco in nota (verbatim, page 2):**
> pantoprazolo, omeprazolo, misoprostolo, lansoprazolo, esomeprazolo

---

### A) SCOPE

**rule_id:** N01_SCOPE_001
**Page:** 2 — Main normative box

**Verbatim (Italian):**
> "La prescrizione a carico del SSN è limitata:
> - **alla prevenzione delle complicanze gravi del tratto gastrointestinale superiore**
>   - in trattamento cronico con farmaci antinfiammatori non steroidei (FANS)
>   - in terapia antiaggregante con ASA a basse dosi"

**Summary:** SSN prescription of pantoprazole, omeprazole, misoprostol, lansoprazole, esomeprazole is limited to prevention of serious complications of the upper gastrointestinal tract (GI), in the context of either (a) chronic NSAID therapy, or (b) low-dose ASA antiplatelet therapy.

---

### B) INCLUSION CRITERIA

All criteria must be satisfied: the patient must be in one of the two qualifying treatments (NSAID chronic OR low-dose ASA), AND must have at least one of the listed risk conditions.

#### B.1 — Qualifying treatment arm 1

**rule_id:** N01_INCL_001
**Page:** 2 — Main normative box

**Verbatim:**
> "in trattamento cronico con farmaci antinfiammatori non steroidei (FANS)"

**Condition:** Chronic treatment with NSAIDs (FANS).

---

#### B.2 — Qualifying treatment arm 2

**rule_id:** N01_INCL_002
**Page:** 2 — Main normative box

**Verbatim:**
> "in terapia antiaggregante con ASA a basse dosi"

**Condition:** Antiplatelet therapy with low-dose ASA (aspirin).

---

#### B.3 — Risk condition 1: prior bleeding or unhealed peptic ulcer

**rule_id:** N01_INCL_003
**Page:** 2 — Main normative box, "condizioni di rischio"

**Verbatim:**
> "storia di pregresse emorragie digestive o di ulcera peptica non guarita con terapia eradicante"

**Condition:** History of previous digestive haemorrhages OR peptic ulcer not healed with eradication therapy.

---

#### B.4 — Risk condition 2: concomitant anticoagulant or corticosteroid therapy

**rule_id:** N01_INCL_004
**Page:** 2 — Main normative box, "condizioni di rischio"

**Verbatim:**
> "concomitante terapia con anticoagulanti o cortisonici"

**Condition:** Concomitant therapy with anticoagulants OR corticosteroids.

---

#### B.5 — Risk condition 3: advanced age

**rule_id:** N01_INCL_005
**Page:** 2 — Main normative box, "condizioni di rischio"

**Verbatim:**
> "età avanzata."

**Condition:** Advanced age.

**Contextual clarification (Background section, page 2, verbatim):**
> "Sulla base di studi clinici randomizzati e osservazionali anche l'uso di anticoagulanti e l'età avanzata (65-75 anni) sono risultate essere condizioni predisponenti al rischio di complicanze gravi del tratto gastrointestinale superiore. Pertanto tali condizioni devono essere considerate fattori suggestivi di popolazioni a maggior rischio ma non raccomandazioni tassative per trattare, ad esempio, tutti gli anziani o tutti coloro che assumono anticoagulanti."

**Implementation note:** "Advanced age" is contextually defined as 65–75 years. It is a suggestive, not mandatory, factor; it does not justify blanket treatment of all elderly patients.

---

### C) HARD EXCLUSIONS (Controindicazioni assolute)

Nota 01 does not enumerate explicit absolute contraindications that block reimbursement. However the following regulatory restrictions are stated:

#### C.1 — H2-antagonists excluded from reimbursement under this Note

**rule_id:** N01_EXCL_001
**Page:** 3 — "Particolari avvertenze" section

**Verbatim:**
> "Gli H2-inibitori non sono stati inclusi tra i farmaci indicati per la prevenzione e il trattamento del danno gastrointestinale da FANS perché in dosi standard non riducono significativamente l'incidenza delle ulcere gastriche, che sono le più frequenti fra quelle da FANS anche se hanno efficacia pressoché uguale a quella del misoprostolo sulle ulcere duodenali."

**Effect:** H2 antagonists (H2-blockers) are NOT eligible for reimbursement under Nota 01.

---

#### C.2 — Gastroprotected/buffered ASA preparations excluded

**rule_id:** N01_EXCL_002
**Page:** 3 — "Particolari avvertenze" section

**Verbatim:**
> "Non è invece appropriato l'uso di preparazioni 'gastroprotette' o tamponate di ASA, che hanno un rischio emorragico non differente da quello dell'ASA standard."

**Effect:** Gastroprotected or buffered ASA formulations are NOT appropriate (and therefore not reimbursable under this Note for the purpose of gastroprotection).

---

### D) EXCEPTIONS / ROUTING

#### D.1 — Misoprostol + diclofenac association: route to Nota 66

**rule_id:** N01_ROUTE_001
**Page:** 2 — footnote immediately below the normative box

**Verbatim:**
> "* La prescrizione dell'associazione misoprostolo + diclofenac è rimborsata alle condizioni previste dalla Nota 66."

**Effect:** When the prescribed drug is the fixed-dose combination misoprostol + diclofenac, the applicable Note is Nota 66 (not Nota 01). This is an explicit routing rule.

---

#### D.2 — ASA + clopidogrel dual therapy: misoprostol preferred over PPI

**rule_id:** N01_ROUTE_002
**Page:** 2 — Background section

**Verbatim:**
> "I pazienti in trattamento combinato, ASA e clopidogrel, per i quali è sconsigliata la somministrazione di un inibitore della pompa protonica, possono effettuare la prevenzione delle complicanze gravi del tratto intestinale superiore con l'assunzione di misoprostolo. In ogni caso debbono essere rispettate le condizioni di rischio nel box sopra riportato."

**Effect:** For patients on combined ASA + clopidogrel therapy, PPIs are discouraged; misoprostol should be used instead (if risk conditions are met). This is a clinical routing / drug-selection rule, not an absolute contraindication to reimbursement.

---

#### D.3 — H. pylori eradication as alternative to PPI (ASA users)

**rule_id:** N01_ROUTE_003
**Pages:** 2–3 — "Particolari avvertenze" section

**Verbatim (page 2–3):**
> "L'importanza dell'infezione da H.pylori nella strategia di prevenzione del sanguinamento gastrico causato dai Fans tradizionali e dall'ASA a basso dosaggio è dimostrato da uno studio recente che ha rilevato come nei pazienti con infezione da H.pylori e una storia di sanguinamento gastrico, l'eradicazione dell'infezione da H.pylori risulti equivalente all'omeprazolo nel prevenire una recidiva del sanguinamento gastrico nei pazienti che assumono ASA a basse dosi (probabilità di recidiva del sanguinamento a sei mesi 1,9% con eradicazione e 0,9% con omeprazolo)."

> "Nei pazienti con storia di sanguinamento gastrico, e che devono continuare una profilassi secondaria con ASA a basse dosi, l'eradicazione dell'infezione probabilmente si pone perciò come strategia profilattica più conveniente della somministrazione di un inibitore di pompa."

**Effect:** In H. pylori-positive patients with history of GI bleeding on low-dose ASA, H. pylori eradication should be considered as the primary prophylactic strategy (preferred over PPI). This is guidance-level routing, not a hard block.

---

### E) GUIDANCE / DOSING

#### E.1 — Misoprostol dose and tolerability

**rule_id:** N01_GUID_001
**Page:** 2 — "Evidenze disponibili / Misoprostolo"

**Verbatim:**
> "Il misoprostolo somministrato alla dose di 800 mg ha però una tollerabilità scarsa (dispepsia, dolore addominale, diarrea) e nello studio mucosa i pazienti che sospendevano il trattamento per disturbi gastrointestinali erano più numerosi fra quelli trattati con misoprostolo più FANS (27,4%) che fra quelli trattati con FANS più placebo (20,1% p<0,001)."

**Note:** Poor tolerability of misoprostol 800 mg; relevant for therapy selection.

---

#### E.2 — Blanket gastroprotection not justified in low-risk ASA users

**rule_id:** N01_GUID_002
**Page:** 3 — "Particolari avvertenze"

**Verbatim:**
> "Una metanalisi recente ha dimostrato che il rischio emorragico da ASA impiegato come antiaggregante è assai basso (una emorragia ogni 117 pazienti trattati con 50-162 mg/die di ASA per una durata media di 28 mesi). Pertanto, una gastroprotezione farmacologica generalizzata non è giustificata."

**Note:** Generalised pharmacological gastroprotection is NOT justified. Only risk-stratified patients qualify.

---

#### E.3 — H2-blockers may be used for therapy of ulcers (not prevention) if NSAIDs are stopped

**rule_id:** N01_GUID_003
**Page:** 3 — "Particolari avvertenze"

**Verbatim:**
> "Una revisione non sistematica del danno gastrointestinale da FANS non raccomanda gli H2-inibitori per la prevenzione dei danni gastrointestinali da FANS; li ammette per la terapia delle ulcere previa sospensione dei FANS, ma non se si seguitano i FANS."

**Note:** H2-blockers may be used therapeutically for NSAID-induced ulcers only if NSAIDs are discontinued. They do not qualify for prevention under Nota 01.

---

#### E.4 — COXIB data not applicable

**rule_id:** N01_GUID_004
**Page:** 3 — "Particolari avvertenze"

**Verbatim:**
> "I dati clinici citati non possono essere applicati ai COXIB."

**Note:** The cited clinical data for NSAID GI damage do not apply to COX-2 selective inhibitors (COXIB).

---

#### E.5 — Omeprazole + diclofenac equivalent to celecoxib for recurrent GI bleeding prevention

**rule_id:** N01_GUID_005
**Page:** 3 — "Particolari avvertenze"

**Verbatim:**
> "Va segnalato come in uno studio in pazienti con storia di sanguinamento gastrico recente, il trattamento per sei mesi con omeprazolo più diclofenac si sia dimostrato egualmente efficace rispetto al celecoxib nel prevenire la ricorrenza del sanguinamento gastrico."

**Note:** Non-binding guidance; relevant to clinical decision-making between COXIB and NSAID + PPI combinations.

---

### F) TABLES

Nota 01 contains no formatted tables. The normative criteria are presented as a bulleted list within a box (page 2). There are no tabular data structures in this document.

---

### G) DRUG LIST — Nota 01

#### G.1 — Drugs covered by Nota 01 (SSN-reimbursable under this Note)

| Drug (generic) | Class | Rule ID |
|---|---|---|
| Pantoprazolo (pantoprazole) | PPI — Proton Pump Inhibitor | N01_DRUG_001 |
| Omeprazolo (omeprazole) | PPI — Proton Pump Inhibitor | N01_DRUG_002 |
| Lansoprazolo (lansoprazole) | PPI — Proton Pump Inhibitor | N01_DRUG_003 |
| Esomeprazolo (esomeprazole) | PPI — Proton Pump Inhibitor | N01_DRUG_004 |
| Misoprostolo (misoprostol) | Prostaglandin analogue | N01_DRUG_005 |

#### G.2 — Drugs mentioned but NOT eligible under Nota 01

| Drug (generic) | Class | Reason for exclusion | Rule ID |
|---|---|---|---|
| Ranitidina (ranitidine) | H2-antagonist | H2-blockers excluded from reimbursement (N01_EXCL_001) | N01_DRUG_006 |
| H2-antagonists (class) | H2-antagonist | Standard doses do not reduce gastric ulcer incidence from NSAIDs | N01_DRUG_007 |
| ASA (aspirin) gastroenterica/tamponate | Gastroprotected/buffered ASA | Haemorrhagic risk not different from standard ASA; excluded (N01_EXCL_002) | N01_DRUG_008 |

#### G.3 — Drug combinations mentioned

| Combination | Rule reference |
|---|---|
| Misoprostolo + diclofenac (fixed dose) | Routed to Nota 66 (N01_ROUTE_001) |
| ASA + clopidogrel (dual antiplatelet) | Misoprostol preferred; PPI discouraged (N01_ROUTE_002) |
| Omeprazolo + diclofenac | Equivalent to celecoxib for recurrent bleeding prevention (N01_GUID_005) |

#### G.4 — Drugs mentioned in evidence/background (no reimbursement status change)

| Drug | Context |
|---|---|
| Celecoxib (COXIB) | Comparator in studies; COXIB data not applicable per N01_GUID_004 |
| Naprossene (naproxen) | Comparator in evidence |
| Clopidogrel | Mentioned in routing rule N01_ROUTE_002 |
| Diclofenac | Mentioned as NSAID requiring gastroprotection |
| H. pylori eradication agents (generic) | Mentioned as alternative strategy |

---

---

## NOTA 66

### Header

**Farmaco in nota (verbatim, page 2):**
> "Tenoxicam, Sulindac, Proglumetacina, Piroxicam, Oxaprozina, Nimesulide, Naprossene, Nabumetone, Meloxicam, Lornoxicam, Ketoprofene, Indometacina, Ibuprofene, Furprofene, Flurbiprofene, Fentiazac, Etoricoxib, Diclofenac + Misoprostolo, Diclofenac, Dexibuprofene, Codeina e ibuprofene, Cinnoxicam, Celecoxib, Amtolmetina, Acido tiaprofenico, Acido mefenamico, Acetametacina, Aceclofenac"

**Legislative references:**
- Determina AIFA: G.U. n°197, 24 agosto 2012
- Modifica alla Nota 66: G.U. n°246, 22 ottobre 2018

---

### A) SCOPE

**rule_id:** N66_SCOPE_001
**Page:** 2 — Introductory normative statement

**Verbatim:**
> "La prescrizione dei farmaci antinfiammatori non steroidei a carico del SSN è limitata alle seguenti condizioni patologiche:"

**Summary:** SSN prescription of NSAIDs (FANS) is limited to specific pathological conditions enumerated in two separate tables (Table 1: standard NSAID monotherapy; Table 2: NSAID fixed-dose combinations with other analgesics).

---

### B) INCLUSION CRITERIA

Nota 66 is organised in two distinct reimbursement tracks, each with its own inclusion criteria.

---

#### TRACK 1 — Standard NSAID monotherapy

**rule_id:** N66_INCL_001
**Page:** 2 — Table 1, left column "Limitatamente alle seguenti indicazioni"

**Verbatim inclusion indications for the full NSAID list (except nimesulide):**
> "- Artropatie su base connettivitica;
> - Osteoartrosi in fase algica o infiammatoria;
> - Dolore neoplastico;
> - Attacco acuto di gotta."

These four conditions apply to ALL NSAIDs in the standard list (aceclofenac through tenoxicam), EXCEPT nimesulide which has a restricted separate sub-row.

---

#### TRACK 1b — Nimesulide (restricted indication within Track 1)

**rule_id:** N66_INCL_002
**Page:** 2 — Table 1, sub-row for Nimesulide

**Verbatim:**
> "- Trattamento di breve durata del dolore acuto nell'ambito delle patologie sopra descritte"
> Drug: **Nimesulide**

**Critical implementation detail (from "Particolari avvertenze", page 4, verbatim):**
> "In sintesi nimesulide va prescritta esclusivamente per il trattamento di seconda linea ed è indicata soltanto nel trattamento del dolore acuto."

**Effect:** Nimesulide is reimbursable ONLY for short-duration acute pain treatment within the four conditions above (connective tissue arthropathies, osteoarthritis in algic/inflammatory phase, neoplastic pain, acute gout attack), AND only as second-line treatment, AND only for acute pain (NOT for chronic/osteoarthritis long-term use).

---

#### TRACK 2 — NSAID fixed-dose combination with other analgesics (Ibuprofene/Codeina)

**rule_id:** N66_INCL_003
**Page:** 2 — Table 2 "FANS IN ASSOCIAZIONE FISSA CON ALTRI ANALGESICI", left column

**Verbatim:**
> "Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente."
> Drug: **Ibuprofene/Codeina**

**Eligibility conditions (Background section, page 3, verbatim):**
> "La combinazione a dose fissa a base di ibuprofene/codeina viene ammessa alla rimborsabilità limitatamente al trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente."
> "La combinazione ibuprofene/codeina è indicata nel trattamento sintomatico del dolore da lieve a moderato negli adulti se non adeguatamente alleviato dagli altri antidolorifici quali paracetamolo o ibuprofene."

**Key condition:** Inadequate control with other analgesics taken individually (e.g. paracetamol or ibuprofen alone) is a prerequisite.

---

#### TRACK 2 — Dosing specification for Ibuprofene/Codeina

**rule_id:** N66_INCL_004
**Page:** 3 — "Evidenze disponibili / FANS in combinazione fissa con altri analgesici"

**Verbatim:**
> "Il dosaggio autorizzato nella popolazione adulta è di 1 compressa ogni 4-6 ore, con una dose massima giornaliera di 6 compresse (2.400 mg ibuprofene/180 mg codeina fosfato emidrato) nelle 24 ore."

**Thresholds:**
- Dosing interval: 1 tablet every 4–6 hours
- Maximum daily dose: 6 tablets = 2,400 mg ibuprofen / 180 mg codeine phosphate hemihydrate per 24 hours

---

### C) HARD EXCLUSIONS (Controindicazioni assolute)

#### C.1 — All NSAIDs: contraindicated in severe heart failure

**rule_id:** N66_EXCL_001
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Tutti i FANS sono controindicati nello scompenso cardiaco grave."

**Effect:** ALL NSAIDs (all drugs in Nota 66) are contraindicated (and therefore not reimbursable) in patients with severe heart failure.

---

#### C.2 — Selective COX-2 inhibitors: contraindicated in ischaemic heart disease, cerebrovascular disease, peripheral arterial disease, moderate-to-severe heart failure

**rule_id:** N66_EXCL_002
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Gli inibitori selettivi della ciclossigenasi 2 sono controindicati nella cardiopatia ischemica, nelle patologie cerebrovascolari, nelle patologie arteriose periferiche e nello scompenso cardiaco moderato e grave."

**Drugs affected:** Celecoxib, etoricoxib (COX-2 selective inhibitors in the list).

---

#### C.3 — All NSAIDs: contraindicated in patients with allergy to aspirin or any other NSAID

**rule_id:** N66_EXCL_003
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "nelle patologie allergiche (sono controindicati nei soggetti con anamnesi positiva per allergia ad aspirina o a un altro FANS, inclusi coloro in cui un episodio di asma, angioedema, orticaria o rinite sia stato scatenato dall'assunzione di aspirina o di un altro FANS)"

---

#### C.4 — All NSAIDs: contraindicated in active peptic ulcer

**rule_id:** N66_EXCL_004
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "ricordare che tutti i FANS sono controindicati nei soggetti con ulcera peptica (compresi gli inibitori selettivi della ciclossigenasi 2)"

Also:
> "Il Committee on Safety of Medicines britannico avverte che i FANS non devono essere somministrati a soggetti con ulcera peptica attiva o pregressa e che gli inibitori selettivi della ciclossigenasi 2 sono controindicati in caso di ulcera peptica attiva."

**Effect:** All NSAIDs are contraindicated in peptic ulcer. COX-2 inhibitors specifically contraindicated in ACTIVE peptic ulcer.

---

#### C.5 — Nimesulide: contraindicated in hepatic disease, alcohol abuse history, concomitant hepatotoxic drugs

**rule_id:** N66_EXCL_005
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Vari FANS possono avere un effetto epatotossico. In particolare nimesulide ha un rischio epatotossico maggiore degli altri FANS ed è controindicata nei pazienti epatopatici, in quelli con una storia di abuso di alcool e negli assuntori di altri farmaci epatotossici."

**Effect:** Nimesulide is specifically contraindicated in: (a) hepatic disease, (b) history of alcohol abuse, (c) patients taking other hepatotoxic drugs.

---

#### C.6 — Selective COX-2 inhibitors: contraindicated in active peptic ulcer (explicit)

**rule_id:** N66_EXCL_006
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "gli inibitori selettivi della ciclossigenasi 2 sono controindicati in caso di ulcera peptica attiva"

**Note:** This is a subset of N66_EXCL_004 but stated separately for COX-2 inhibitors specifically.

---

#### C.7 — Nimesulide: NOT reimbursable for chronic osteoarthritis (long-term use)

**rule_id:** N66_EXCL_007
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "nimesulide per uso sistemico non sia più impiegato nel trattamento dell'osteoartrosi dolorosa che, essendo una condizione cronica, accresce il rischio che sia assunto a lungo termine, con un conseguente aumento del rischio di danno epatico."

**Effect:** Nimesulide must not be used for painful osteoarthritis (a chronic condition) — even though osteoarthritis in algic/inflammatory phase is one of the general indications. This creates a specific exclusion: nimesulide is excluded from the osteoarthritis indication.

---

### D) EXCEPTIONS / ROUTING

#### D.1 — Selective COX-2 inhibitors: preferred only when very high GI risk

**rule_id:** N66_ROUTE_001
**Page:** 4 — Sicurezza section

**Verbatim:**
> "Alla luce dei dubbi sul profilo di sicurezza cardiovascolare, gli inibitori selettivi della ciclossigenasi 2 dovrebbero essere preferiti ai FANS non selettivi solo se vi è un'indicazione specifica (per esempio in caso di rischio molto elevato di ulcera, perforazione o sanguinamento gastrointestinale) e comunque soltanto dopo un'attenta valutazione del rischio cardiovascolare."

**Effect:** COX-2 inhibitors should be selected over non-selective NSAIDs ONLY when there is a specific indication (very high risk of ulcer, perforation or GI bleeding), AND only after careful cardiovascular risk assessment.

---

#### D.2 — Ibuprofene/Codeina: prerequisite of inadequate response to monotherapy

**rule_id:** N66_ROUTE_002
**Page:** 2 — Table 2; Page 3 — "Evidenze disponibili"

**Verbatim:**
> "Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente."

**Effect:** The fixed-dose combination ibuprofene/codeina is only reimbursable after failure of monotherapy analgesics (paracetamol or ibuprofen alone). This is an explicit step-therapy prerequisite.

---

#### D.3 — Diclofenac + Misoprostolo (association): governed by Nota 66 (referenced also by Nota 01)

**rule_id:** N66_ROUTE_003
**Page:** 2 — Table 1, drug list (diclofenac + misoprostolo listed as eligible drug)

**Cross-reference:** Nota 01, page 2, footnote (N01_ROUTE_001) confirms that this combination's reimbursement is governed by Nota 66.

**Effect:** The fixed-dose combination diclofenac + misoprostol is reimbursable under Nota 66 (same indications as other NSAIDs in Table 1).

---

### E) GUIDANCE / DOSING

#### E.1 — WHO analgesic pain ladder (non-binding, informational)

**rule_id:** N66_GUID_001
**Page:** 3 — Background / "Evidenze disponibili"

**Verbatim:**
> "Dolore lieve (valutazione del dolore secondo scala visuo-analogica (VAS) da 1-4): è suggerito trattamento con FANS o paracetamolo ± adiuvanti;
> Dolore di grado lieve-moderato (VAS 5-6): è suggerito trattamento con oppioidi deboli ± FANS o paracetamolo ± adiuvanti;
> Dolore grave o da moderato a grave (VAS 7-10): è suggerito trattamento con oppioidi forti ± FANS o paracetamolo ± adiuvanti."

**Note:** WHO VAS pain scale guidance (0=no pain, 10=unbearable pain). Not a hard rule but referenced as framework for treatment selection.

---

#### E.2 — Use minimum effective dose for minimum duration (general)

**rule_id:** N66_GUID_002
**Page:** 4 — Sicurezza section

**Verbatim:**
> "Le diverse raccomandazioni emanate a tal proposito dalle agenzie regolatorie, quali EMA e FDA, possono sinteticamente riassumersi nella raccomandazione generale di utilizzare i FANS o gli inibitori selettivi della ciclossigenasi 2, nel trattamento sintomatico, alla dose minima efficace e per il periodo più breve possibile; si raccomanda, inoltre, nel caso di trattamento a lungo termine, di considerarne periodicamente la necessità."

---

#### E.3 — Cardiovascular risk profile of individual NSAIDs

**rule_id:** N66_GUID_003
**Page:** 4 — Sicurezza section

**Verbatim:**
> "Il diclofenac e l'etoricoxib aumentano il rischio trombotico, mentre il naprossene è associato a un rischio inferiore. Dosi elevate di ibuprofene (2,4 g al giorno) possono determinare un lieve aumento di rischi trombotici, mentre dosi basse del farmaco (1,2 g al giorno o meno) non aumentano il rischio di infarto miocardico."

**Implementation note:**
- Diclofenac: higher thrombotic risk
- Etoricoxib: higher thrombotic risk
- Naproxen: lower thrombotic risk
- Ibuprofen >=2.4 g/day: mild increase in thrombotic risk
- Ibuprofen <=1.2 g/day: no increase in MI risk

---

#### E.4 — Caution in elderly (serious and potentially fatal side effects)

**rule_id:** N66_GUID_004
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "I FANS devono essere utilizzati con cautela negli anziani (rischi di gravi effetti collaterali anche mortali)"

---

#### E.5 — Caution during pregnancy, breastfeeding, coagulation disorders

**rule_id:** N66_GUID_005
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "durante la gravidanza, l'allattamento e nei difetti della coagulazione."

---

#### E.6 — Caution in renal insufficiency

**rule_id:** N66_GUID_006
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Nei soggetti con insufficienza renale, i FANS devono essere utilizzati con cautela, in quanto possono peggiorare la funzionalità renale; è necessario somministrare la dose minima possibile e controllare la funzionalità renale."

---

#### E.7 — Caution: selective COX-2 inhibitors in cardiac history, LV dysfunction, hypertension, oedema, cardiovascular risk factors

**rule_id:** N66_GUID_007
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Gli inibitori selettivi della ciclossigenasi 2 devono essere usati con cautela nei pazienti con storia di insufficienza cardiaca, disfunzioni del ventricolo sinistro o ipertensione, così come in caso di edema per cause diverse e quando vi sono fattori di rischio cardiovascolare."

---

#### E.8 — NSAID + low-dose ASA combination increases GI risk

**rule_id:** N66_GUID_008
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "La combinazione di FANS e acido acetilsalicilico a basso dosaggio aumenta il rischio di effetti gastrointestinali; tale associazione deve essere utilizzata solo se è assolutamente necessaria e il paziente è monitorato."

---

#### E.9 — Ibuprofen and diclofenac may reduce antiplatelet effect of low-dose ASA

**rule_id:** N66_GUID_009
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Dati preliminari farebbero ipotizzare una riduzione dell'effetto antiaggregante dell'ASA a basso dosaggio con alcuni FANS (ibuprofene e diclofenac), ma i tempi di somministrazione sono critici. Quest'azione di inibizione non parrebbe essere esercitata dal naprossene."

---

#### E.10 — Piroxicam and ketorolac: higher gastrolesive risk; EMA has limited their use

**rule_id:** N66_GUID_010
**Page:** 4 — Sicurezza section

**Verbatim:**
> "Piroxicam e ketorolac hanno dimostrato un maggior rischio gastrolesivo, per cui l'EMA ne ha limitato l'uso (v. RCP dei due prodotti)."

---

#### E.11 — Nimesulide: second-line only, acute pain only (CHMP decision)

**rule_id:** N66_GUID_011
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Il parere del CHMP, a seguito della conclusione della procedura di Referral ai sensi dell'articolo 31 della direttiva 2001/83/CE, è stato recepito in toto dalla Commissione europea (CE), la cui decisione è stata pubblicata nella gazzetta ufficiale europea nel gennaio 2012. In sintesi nimesulide va prescritta esclusivamente per il trattamento di seconda linea ed è indicata soltanto nel trattamento del dolore acuto."

---

#### E.12 — Codeine in ibuprofene/codeina: risks of tolerance and dependence

**rule_id:** N66_GUID_012
**Page:** 4 — Sicurezza section

**Verbatim:**
> "Possono svilupparsi tolleranza e dipendenza, in particolare in connessione con l'impiego prolungato di quantitativi elevati di codeina. Sebbene il rischio di sviluppare dipendenza dalla codeina sia basso rispetto alla morfina, questa possibilità deve comunque essere tenuta in considerazione."

---

#### E.13 — Minimum effective dose for minimum duration (for combination products)

**rule_id:** N66_GUID_013
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "Nel caso delle coformulazioni in associazione fissa con altri analgesici, come con tutti i FANS e gli oppioidi, gli effetti indesiderati possono essere minimizzati con l'uso della più bassa dose efficace per la più breve durata possibile di trattamento che occorre per controllare i sintomi. Il trattamento deve essere iniziato con la più bassa dose efficace, che potrà in seguito essere aggiustata in base alla risposta terapeutica e a eventuali effetti indesiderati."

---

#### E.14 — Female fertility: long-term NSAID use associated with reversible reduction

**rule_id:** N66_GUID_014
**Page:** 4 — "Particolari avvertenze"

**Verbatim:**
> "L'impiego a lungo termine di alcuni FANS è associato a una riduzione della fertilità femminile, reversibile con la sospensione del trattamento."

---

### F) TABLES

#### Table 1 — Standard NSAIDs (Nota 66, page 2)

**Table title/label:** (Unnumbered, implicit label: "FANS in nota — indicazioni e principi attivi")
**PDF page:** 2
**Section:** Main normative box

| Limitatamente alle seguenti indicazioni | Limitatamente ai seguenti principi attivi |
|---|---|
| Artropatie su base connettivitica | aceclofenac |
| Osteoartrosi in fase algica o infiammatoria | acemetacina |
| Dolore neoplastico | acido mefenamico |
| Attacco acuto di gotta | acido tiaprofenico |
| | amtolmetina guacile |
| | celecoxib |
| | cinnoxicam |
| | dexibuprofene |
| | diclofenac |
| | diclofenac + misoprostolo |
| | etoricoxib |
| | fentiazac |
| | flurbiprofene |
| | furprofene |
| | ibuprofene |
| | indometacina |
| | ketoprofene |
| | Lornoxicam |
| | meloxicam |
| | nabumetone |
| | naprossene |
| | oxaprozina |
| | piroxicam |
| | proglumetacina |
| | sulindac |
| | tenoxicam |
| Trattamento di breve durata del dolore acuto nell'ambito delle patologie sopra descritte | Nimesulide |

**Extraction note:** The table as published presents the four main indications aligned with the full drug list (rows 1–4), and a separate sub-row for Nimesulide with its restricted indication. The drug list column spans all four indications (one-to-many relationship).

---

#### Table 2 — FANS in Associazione Fissa con Altri Analgesici (Nota 66, page 2)

**Table title/label:** "FANS IN ASSOCIAZIONE FISSA CON ALTRI ANALGESICI"
**PDF page:** 2

| Limitatamente alle seguenti indicazioni | Limitatamente ai seguenti principi attivi |
|---|---|
| Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente. | Ibuprofene/Codeina |

---

#### Table 3 — WHO Pain Scale (informational, page 3)

**Table title/label:** Scala Analgesica OMS (embedded in Background text, not a formal table)
**PDF page:** 3

| VAS Score | Pain Level | Suggested Treatment |
|---|---|---|
| 1–4 | Dolore lieve (mild) | FANS o paracetamolo ± adiuvanti |
| 5–6 | Dolore lieve-moderato (mild-moderate) | Oppioidi deboli ± FANS o paracetamolo ± adiuvanti |
| 7–10 | Dolore grave o da moderato a grave (severe/moderate-to-severe) | Oppioidi forti ± FANS o paracetamolo ± adiuvanti |

---

### G) DRUG LIST — Nota 66

#### G.1 — Standard NSAIDs (Track 1 — all four main indications)

| # | Drug (Italian/generic) | Drug class | Rule ID |
|---|---|---|---|
| 1 | Aceclofenac | NSAID — arylacetic acid | N66_DRUG_001 |
| 2 | Acemetacina (acemetacin) | NSAID — indole acetic acid derivative | N66_DRUG_002 |
| 3 | Acido mefenamico (mefenamic acid) | NSAID — fenamate | N66_DRUG_003 |
| 4 | Acido tiaprofenico (tiaprofenic acid) | NSAID — propionic acid | N66_DRUG_004 |
| 5 | Amtolmetina guacile (amtolmetin guacil) | NSAID — pyrrolacetic acid | N66_DRUG_005 |
| 6 | Celecoxib | NSAID — selective COX-2 inhibitor (COXIB) | N66_DRUG_006 |
| 7 | Cinnoxicam | NSAID — oxicam | N66_DRUG_007 |
| 8 | Dexibuprofene (dexibuprofen) | NSAID — propionic acid (S-enantiomer of ibuprofen) | N66_DRUG_008 |
| 9 | Diclofenac | NSAID — arylacetic acid | N66_DRUG_009 |
| 10 | Diclofenac + Misoprostolo (fixed combination) | NSAID + prostaglandin analogue | N66_DRUG_010 |
| 11 | Etoricoxib | NSAID — selective COX-2 inhibitor (COXIB) | N66_DRUG_011 |
| 12 | Fentiazac | NSAID — thiazolineacetic acid | N66_DRUG_012 |
| 13 | Flurbiprofene (flurbiprofen) | NSAID — propionic acid | N66_DRUG_013 |
| 14 | Furprofene (furprofen) | NSAID — propionic acid | N66_DRUG_014 |
| 15 | Ibuprofene (ibuprofen) | NSAID — propionic acid | N66_DRUG_015 |
| 16 | Indometacina (indomethacin) | NSAID — indole acetic acid | N66_DRUG_016 |
| 17 | Ketoprofene (ketoprofen) | NSAID — propionic acid | N66_DRUG_017 |
| 18 | Lornoxicam | NSAID — oxicam | N66_DRUG_018 |
| 19 | Meloxicam | NSAID — oxicam (preferential COX-2) | N66_DRUG_019 |
| 20 | Nabumetone | NSAID — naphthylalkanone | N66_DRUG_020 |
| 21 | Naprossene (naproxen) | NSAID — propionic acid | N66_DRUG_021 |
| 22 | Oxaprozina (oxaprozin) | NSAID — propionic acid | N66_DRUG_022 |
| 23 | Piroxicam | NSAID — oxicam | N66_DRUG_023 |
| 24 | Proglumetacina (proglumetacin) | NSAID — indole acetic acid | N66_DRUG_024 |
| 25 | Sulindac | NSAID — arylacetic acid | N66_DRUG_025 |
| 26 | Tenoxicam | NSAID — oxicam | N66_DRUG_026 |

---

#### G.2 — Restricted NSAID (Track 1b — acute pain, short-duration, second-line)

| # | Drug | Class | Restriction | Rule ID |
|---|---|---|---|---|
| 27 | Nimesulide | NSAID — sulphonanilide | Acute pain only; short-duration; second-line; NOT for osteoarthritis long-term | N66_DRUG_027 |

---

#### G.3 — Fixed-dose NSAID + analgesic combination (Track 2)

| # | Drug | Class | Rule ID |
|---|---|---|---|
| 28 | Ibuprofene/Codeina (ibuprofen/codeine) | NSAID + weak opioid (fixed combination) | N66_DRUG_028 |

---

#### G.4 — Drugs mentioned but withdrawn from market (mentioned in safety context)

| Drug | Reason | Page |
|---|---|---|
| Rofecoxib | Withdrawn due to cardiovascular risk | 3 |
| Valdecoxib | Withdrawn due to cardiovascular risk | 3 |
| Lumiracoxib | Withdrawn due to hepatotoxicity | 3 |
| Azapropazone | Withdrawn; highest GI risk | 4 |
| Ketorolac | Not in nota; EMA-limited use (see SPC) | 4 |

---

#### G.5 — Other drugs mentioned in guidance/safety context (not in nota)

| Drug | Context | Page |
|---|---|---|
| Paracetamolo (paracetamol) | Comparator; monotherapy alternative before ibuprofene/codeina | 3 |
| Morfina (morphine) | Comparator for codeine dependence risk | 4 |
| Acido acetilsalicilico / ASA (aspirin) | GI risk interaction when combined with NSAIDs | 4 |
| Codeina (codeine, standalone) | Safety context for ibuprofene/codeina combination | 4 |

---

---

## Cross-Note Rules (Inter-Note Relationships)

| rule_id | Description | Source note | Target note | Verbatim |
|---|---|---|---|---|
| N01_ROUTE_001 | Misoprostolo + diclofenac combination: governed by Nota 66, not Nota 01 | Nota 01, p.2 | Nota 66 | "La prescrizione dell'associazione misoprostolo + diclofenac è rimborsata alle condizioni previste dalla Nota 66." |
| N66_ROUTE_003 | Diclofenac + misoprostolo included in Nota 66 drug list | Nota 66, p.2 | Nota 01 | [drug listed in Table 1 as "diclofenac + misoprostolo"] |

**Implementation consequence:** When a prescription contains misoprostol + diclofenac (fixed-dose), the rule engine must evaluate Nota 66 criteria (four indications), NOT Nota 01 criteria (PPI gastroprotection risk conditions).

---

## Rule ID Master Index

### Nota 01

| rule_id | Type | Summary |
|---|---|---|
| N01_SCOPE_001 | SCOPE | SSN prescription limited to upper GI complication prevention |
| N01_INCL_001 | INCLUSION | Qualifying treatment: chronic NSAIDs |
| N01_INCL_002 | INCLUSION | Qualifying treatment: low-dose ASA antiaggregant |
| N01_INCL_003 | INCLUSION | Risk condition: prior digestive haemorrhage or unhealed peptic ulcer |
| N01_INCL_004 | INCLUSION | Risk condition: concomitant anticoagulant or corticosteroid |
| N01_INCL_005 | INCLUSION | Risk condition: advanced age (contextually 65–75 years) |
| N01_EXCL_001 | EXCLUSION | H2-antagonists not eligible under Nota 01 |
| N01_EXCL_002 | EXCLUSION | Gastroprotected/buffered ASA not appropriate |
| N01_ROUTE_001 | ROUTING | Misoprostol + diclofenac → evaluate under Nota 66 |
| N01_ROUTE_002 | ROUTING | ASA + clopidogrel dual therapy → use misoprostol, not PPI |
| N01_ROUTE_003 | ROUTING | H. pylori positive + ASA + bleeding history → eradication preferred |
| N01_GUID_001 | GUIDANCE | Misoprostol 800 mg: poor tolerability data |
| N01_GUID_002 | GUIDANCE | Blanket gastroprotection not justified in low-risk ASA users |
| N01_GUID_003 | GUIDANCE | H2-blockers: therapeutic only after NSAID stop, not for prevention |
| N01_GUID_004 | GUIDANCE | COXIB data not applicable to NSAID GI risk evidence |
| N01_GUID_005 | GUIDANCE | Omeprazole + diclofenac equivalent to celecoxib for recurrent bleeding |
| N01_DRUG_001–005 | DRUG | Pantoprazole, omeprazole, lansoprazole, esomeprazole, misoprostol (in nota) |
| N01_DRUG_006–008 | DRUG | H2-antagonists, gastroprotected ASA (excluded/not applicable) |

### Nota 66

| rule_id | Type | Summary |
|---|---|---|
| N66_SCOPE_001 | SCOPE | SSN NSAID prescription limited to specific pathological conditions |
| N66_INCL_001 | INCLUSION | Four main indications for standard NSAIDs |
| N66_INCL_002 | INCLUSION | Nimesulide: restricted to short-duration acute pain within above indications |
| N66_INCL_003 | INCLUSION | Ibuprofene/codeina: short-duration moderate acute pain, inadequate monotherapy control |
| N66_INCL_004 | INCLUSION | Ibuprofene/codeina: dosing — 1 tablet q4–6h, max 6 tablets/24h |
| N66_EXCL_001 | EXCLUSION | All NSAIDs contraindicated in severe heart failure |
| N66_EXCL_002 | EXCLUSION | COX-2 inhibitors contraindicated in ischaemic heart disease, cerebrovascular/peripheral arterial disease, moderate-severe HF |
| N66_EXCL_003 | EXCLUSION | All NSAIDs contraindicated in aspirin/NSAID allergy |
| N66_EXCL_004 | EXCLUSION | All NSAIDs contraindicated in peptic ulcer |
| N66_EXCL_005 | EXCLUSION | Nimesulide contraindicated in hepatic disease, alcohol abuse, concomitant hepatotoxic drugs |
| N66_EXCL_006 | EXCLUSION | COX-2 inhibitors contraindicated in active peptic ulcer (specific) |
| N66_EXCL_007 | EXCLUSION | Nimesulide not reimbursable for chronic osteoarthritis |
| N66_ROUTE_001 | ROUTING | COX-2 inhibitors preferred over non-selective NSAIDs only with very high GI risk + cardiovascular risk assessment |
| N66_ROUTE_002 | ROUTING | Ibuprofene/codeina: step-therapy prerequisite (monotherapy failure required) |
| N66_ROUTE_003 | ROUTING | Diclofenac + misoprostolo: governed by Nota 66 |
| N66_GUID_001 | GUIDANCE | WHO VAS pain scale (1–4 / 5–6 / 7–10) treatment recommendations |
| N66_GUID_002 | GUIDANCE | Use minimum effective dose for minimum duration |
| N66_GUID_003 | GUIDANCE | Cardiovascular risk by drug: diclofenac/etoricoxib higher; naproxen lower; ibuprofen dose-dependent |
| N66_GUID_004 | GUIDANCE | Caution in elderly |
| N66_GUID_005 | GUIDANCE | Caution in pregnancy, breastfeeding, coagulation disorders |
| N66_GUID_006 | GUIDANCE | Caution in renal insufficiency |
| N66_GUID_007 | GUIDANCE | COX-2 inhibitors: caution with HF history, LV dysfunction, hypertension, oedema, CV risk factors |
| N66_GUID_008 | GUIDANCE | NSAID + low-dose ASA combination increases GI risk |
| N66_GUID_009 | GUIDANCE | Ibuprofen and diclofenac may reduce antiplatelet effect of low-dose ASA |
| N66_GUID_010 | GUIDANCE | Piroxicam and ketorolac: EMA-limited use due to higher GI risk |
| N66_GUID_011 | GUIDANCE | Nimesulide: second-line only, acute pain only (CHMP/EC January 2012 decision) |
| N66_GUID_012 | GUIDANCE | Codeine in ibuprofene/codeina: tolerance and dependence risk |
| N66_GUID_013 | GUIDANCE | Fixed combinations: minimum dose, minimum duration |
| N66_GUID_014 | GUIDANCE | Long-term NSAID use: reversible reduction of female fertility |
| N66_DRUG_001–026 | DRUG | 26 standard NSAIDs (Track 1) |
| N66_DRUG_027 | DRUG | Nimesulide (Track 1b, restricted) |
| N66_DRUG_028 | DRUG | Ibuprofene/Codeina (Track 2) |
