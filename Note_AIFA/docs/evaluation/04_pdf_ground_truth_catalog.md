# 04 — PDF Ground Truth Catalog

**Session:** 7 (2026-02-25)
**Sources:** Nota_01.pdf, nota-13.pdf, Nota_66 .pdf, nota-97.pdf, nota-97-all-1.pdf, nota-97-all-2.pdf
**Extraction method:** PDF read via Read tool (pages 1-5 per note; nota-97-all-2.pdf pages 1-8)

---

## 1. Nota 01 — Gastroprotettori (PPIs)

**Source:** `Nota_01.pdf` (pp. 1-3)

### 1.1 Drugs in Scope
`pantoprazolo, omeprazolo, misoprostolo, lansoprazolo, esomeprazolo`

### 1.2 Verbatim Inclusion Criteria
> *"La prescrizione a carico del SSN è limitata:*
> - *alla prevenzione delle complicanze gravi del tratto gastrointestinale superiore*
>   - *in trattamento cronico con farmaci antinfiammatori non steroidei (FANS)*
>   - *in terapia antiaggregante con ASA a basse dosi*
> - *purché sussista una delle seguenti condizioni di rischio:*
>   - *storia di pregresse emorragie digestive o di ulcera peptica non guarita con terapia eradicante*
>   - *concomitante terapia con anticoagulanti o cortisonici*
>   - *età avanzata."*
>
> *"* La prescrizione dell'associazione misoprostolo + diclofenac è rimborsata alle condizioni previste dalla Nota 66 *."*

**Source:** `Nota_01.pdf` p. 2, section heading box

### 1.3 Rule Mapping

| PDF Criterion | Rule ID | Implementation |
|---------------|---------|----------------|
| Drug must be a PPI (pantoprazolo/omeprazolo/etc) | N01_SCOPE_001 | `drug_in_list(["pantoprazolo",…])` |
| Chronic NSAID therapy | N01_INCL_001 | `OR(uso_cronico_fans, terapia_antiaggreg_asa)` |
| ASA low-dose antiaggregant therapy | N01_INCL_001 | (same OR) |
| Risk condition: bleeding history | N01_INCL_001 | `pregresse_emorragie_digestive` |
| Risk condition: anticoagulant/corticosteroid therapy | N01_INCL_001 | `terapia_anticoagulante OR terapia_corticosteroidea` |
| Risk condition: advanced age | N01_INCL_001 | `eta_avanzata` |
| Exception: misoprostolo+diclofenac → route to Nota 66 | N01_EXCEPT_001 | ROUTE_TO(nota_66) |
| Guidance warning (elderly etc.) | N01_GWARN_001 | GUIDANCE_WARN |

### 1.4 Boundary Notes
- "Età avanzata" is not given a precise numeric threshold in the PDF — implementation uses `eta_avanzata` as a boolean (patient/physician assessment).
- Both the NSAID condition AND one risk condition must hold simultaneously (boolean AND).

---

## 2. Nota 13 — Ipolipemizzanti (Statine/Fibrati)

**Source:** `nota-13.pdf` (pp. 1-5)

### 2.1 Drugs in Scope

| Category | Drugs |
|----------|-------|
| Fibrati | bezafibrato, fenofibrato, gemfibrozil |
| Statine | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina, rosuvastatina |
| Altri | PUFA-N3, ezetimibe |

### 2.2 Verbatim Admission Criterion
> *"La prescrizione a carico del SSN è limitata ai pazienti affetti da: Ipercolesterolemia non corretta dalla sola dieta, seguita per almeno tre mesi, e ipercolesterolemia poligenica secondo i criteri specificati al relativo paragrafo"*

**Source:** `nota-13.pdf` p. 1, text above main table

### 2.3 Risk Classification Table (Verbatim)

| Classificazione | Target LDL (mg/dL) | 1° livello | 2° livello |
|-----------------|-------------------|------------|------------|
| Rischio medio (score 2-3%) | LDL <130 | Modifica stile di vita ≥6 mesi | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina (**) |
| Rischio moderato (score 4-5%) | LDL <115 | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina (**) | — |
| Rischio alto (score >5% <10%) | LDL <100 | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina (**) | rosuvastatina; ezetimibe più statine (**) |
| Rischio molto alto (score ≥10%) | LDL <70 (riduzione ≥50%) | atorvastatina§; pravastatina; fluvastatina; lovastatina; simvastatina (**)§ | ezetimibe più statine (**) |
| Pazienti con statine + HDL basse (<40M, <50F) e/o TG>200 | — | fibrati^ | — |

**Source:** `nota-13.pdf` pp. 1-2, main classification table

### 2.4 Footnotes (Verbatim)

> **(\*\*)** Nei pazienti che siano intolleranti alle statine, per il conseguimento del target terapeutico è rimborsato il trattamento con ezetimibe in monoterapia

> **§** Nei pazienti con sindromi coronariche acute o in quelli sottoposti a interventi di rivascolarizzazione percutanea è indicata atorvastatina a dosaggio elevato (≥40 mg).

> **^** Il farmaco di prima scelta è il fenofibrato per la maggiore sicurezza di uso nei pazienti in terapia con statine; la combinazione di statine e gemfibrozil è invece associata ad un aumentato rischio di miopatia.

**Source:** `nota-13.pdf` p. 2

### 2.5 Familial Dyslipidemia Table

| Dislipidemia | 1° livello | 2° livello | 3° livello |
|---|---|---|---|
| Ipercolesterolemia familiare monogenica (FH) | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina, rosuvastatina (**) | ezetimibe più statine (**) | Aggiunta di resine sequestranti gli acidi biliari |
| Iperlipidemia familiare combinata | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina (**) | rosuvastatina; PUFA-N3; ezetimibe più statine (**) | — |
| Disbetalipoproteinemia | simvastatina, pravastatina, fluvastatina, lovastatina, atorvastatina (**) | rosuvastatina; ezetimibe più statine (**) | Aggiunta di resine |
| Iperchilomicronemia e gravi ipertrigliceridemie | fibrati; PUFA N3 | fibrati in associazione a PUFA N3 | — |

**Source:** `nota-13.pdf` p. 3

### 2.6 CKD Table

| Condition | Drug |
|-----------|------|
| TG ≥500 mg/dL | PUFA-N3 |
| LDL-C ≥130 mg/dL | I scelta: simvastatina + ezetimibe; II scelta: altre statine a minima escrezione renale* |

**Source:** `nota-13.pdf` p. 3

### 2.7 Drug-Induced Dyslipidemia (HAART)
> *"Farmaci immunosoppressori, antiretrovirali e inibitori della aromatasi: Statine considerando con la massima attenzione l'interferenza con il trattamento antiretrovirale altamente attivo (HAART). Fibrati nel caso sia predominante l'iperTG. Ezetimibe in monoterapia per i pazienti che non tollerano il trattamento con statine o non possono eseguirlo."*

**Source:** `nota-13.pdf` p. 4

### 2.8 Rule Mapping

| PDF Criterion | Rule ID | Notes |
|---------------|---------|-------|
| Drug must be ipolipemizzante | N13_SCOPE_001 | checks drug in full drug list |
| Ipercolesterolemia non corretta dalla sola dieta ≥3 mesi | N13_INCL_001 | `ipercolesterolemia_dieta_3mesi` |
| Risk category + LDL target + 2nd line failure | N13_PATH_001 | `categoria_rischio` derived var |
| Poligenica criteria | N13_PATH_002 | familial dislipidemia pathway |
| Statin intolerance → ezetimibe monotherapy | N13_EXCEPT_001 | exception bypass |
| Acute coronary syndrome → atorvastatina ≥40mg | N13_EXCEPT_002 | exception pathway |
| Dose guidance | N13_GDOSE_001 | GUIDANCE_DOSE |

### 2.9 Key Thresholds

| Threshold | PDF Value | Operator | Implementation | Notes |
|-----------|-----------|----------|----------------|-------|
| Rischio alto: score lower | >5% | `>` | GTE(5) or GT(5)? | PDF uses ">5%" |
| Rischio alto: score upper | <10% | `<` | LTE(10) or LT(10)? | PDF uses "<10%" |
| Rischio molto alto | ≥10% | `≥` | GTE(10) ✅ | Correct |
| LDL target molto alto | <70 | `<` | LT(70) ✅ | |
| LDL target alto | <100 | `<` | LT(100) ✅ | |
| LDL target moderato | <115 | `<` | LT(115) ✅ | |
| LDL target medio | <130 | `<` | LT(130) ✅ | |
| Statin intolerance: LDL target | Depends on category | | see N13_EXCEPT_001 | ⚠️ boundary ambiguity |

---

## 3. Nota 66 — FANS/NSAIDs

**Source:** `Nota_66 .pdf` (pp. 1-5)

### 3.1 Complete Drug List (28 drugs)

**FANS in monoterapia (26 drugs):**
> aceclofenac; acemetacina; acido mefenamico; acido tiaprofenico; amtolmetina guacile; celecoxib; cinnoxicam; dexibuprofene; diclofenac; diclofenac + misoprostolo; etoricoxib; fentiazac; flurbiprofene; furprofene; ibuprofene; indometacina; ketoprofene; Lornoxicam; meloxicam; nabumetone; naprossene; oxaprozina; piroxicam; proglumetacina; sulindac; tenoxicam.

**FANS in associazione fissa con altri analgesici (1):** Nimesulide (breve durata, dolore acuto only)

**FANS + analgesici fissi (1):** Ibuprofene/Codeina

**Source:** `Nota_66 .pdf` p. 2, two-column table + lower table

### 3.2 Verbatim Inclusion Criteria
> *"La prescrizione dei farmaci antinfiammatori non steroidei a carico del SSN è limitata alle seguenti condizioni patologiche:*
> - *Artropatie su base connettivitica;*
> - *Osteoartrosi in fase algica o infiammatoria;*
> - *Dolore neoplastico;*
> - *Attacco acuto di gotta."*

**Source:** `Nota_66 .pdf` p. 2, left column of main table

**Nimesulide additional restriction:**
> *"Trattamento di breve durata del dolore acuto nell'ambito delle patologie sopra descritte"*

**Ibuprofene/Codeina restriction:**
> *"Trattamento di breve durata del dolore acuto di entità moderata nei soggetti in cui il sintomo non sia adeguatamente controllato con altri antidolorifici assunti singolarmente."*

**Source:** `Nota_66 .pdf` p. 2, lower table

### 3.3 Nimesulide Safety Notes
> *"Vari FANS possono avere un effetto epatotossico. In particolare nimesulide ha un rischio epatotossico maggiore degli altri FANS ed è controindicata nei pazienti epatopatici, in quelli con una storia di abuso di alcol e negli assuntori di altri farmaci epatotossici."*

> *"nel 2001 nimesulide è stata riesaminata dall'EMA… nimesulide va prescritta esclusivamente per il trattamento di seconda linea ed è indicata soltanto nel trattamento del dolore acuto."*

**Source:** `Nota_66 .pdf` p. 4 ("Particolari avvertenze" section)

### 3.4 General NSAID Contraindications
> *"Tutti i FANS sono controindicati nello scompenso cardiaco grave. Gli inibitori selettivi della ciclossigenasi 2 sono controindicati nella cardiopatia ischemica, nelle patologie cerebrovascolari, nelle patologie arteriose periferiche e nello scompenso cardiaco moderato e grave."*

**Source:** `Nota_66 .pdf` p. 4

### 3.5 Rule Mapping

| PDF Criterion | Rule ID | Implementation |
|---|---|---|
| Drug must be in N66 drug list | N66_SCOPE_001 | closed list of 28 drugs |
| Indication: connective arthropathy | N66_INCL_001 | `artropatie_base_connettivit` |
| Indication: osteoarthritis algic/inflam | N66_INCL_002 | `osteoartrosi_fase_algica` |
| Indication: neoplastic pain | N66_INCL_003 | `dolore_neoplastico` (also: gotta) |
| Hepatic disease exclusion (nimesulide) | N66_EXCL_HARD_001 | `malattia_epatica` |
| Ibuprofene/codeina: severe cardiac failure | N66_EXCL_HARD_002 | `scompenso_cardiaco_grave` |
| COX-2: ischemic heart/cerebrovascular | N66_EXCL_HARD_003 | `cardiopatia_ischemica` etc. |
| Nimesulide guidance warning | N66_GWARN_001 | GUIDANCE_WARN (design choice, see §3.4 above) |
| Ibuprofene+codeina warning | N66_GWARN_002 | GUIDANCE_WARN |

### 3.6 Design Note: Nimesulide Severity Classification
The PDF says nimesulide is "controindicata" in epatopatico patients — linguistically a hard contraindication. The implementation classifies this as `EXCL_HARD` (N66_EXCL_HARD_001). The `N66_GWARN_001` rule documents a *guidance warning* about nimesulide hepatotoxicity, which is a weaker signal. The severity of GWARN vs EXCL_HARD classification for nimesulide warnings (distinct from the exclusion) is an intentional design decision documented in the implementation audit.

---

## 4. Nota 97 — Anticoagulanti Orali in FANV

**Sources:** `nota-97.pdf` (pp. 1-5), `nota-97-all-1.pdf` (pp. 1-2 — Allegato 1, prescriber form), `nota-97-all-2.pdf` (pp. 1-8 — Allegato 2, dosing guide)

### 4.1 Drugs in Scope

| Category | Drugs |
|----------|-------|
| AVK (Vit. K antagonists) | Warfarin (Coumadin® 5 mg), Acenocumarolo (Sintrom® 1+4 mg) |
| NAO/DOAC (direct) | Dabigatran (Pradaxa® 110+150 mg), Apixaban (Eliquis® 2,5+5 mg), Edoxaban (Lixiana® 30+60 mg), Rivaroxaban (Xarelto® 15+20 mg) |

**Source:** `nota-97.pdf` p. 1 (left column), `nota-97-all-2.pdf` p. 1

### 4.2 Verbatim Scope
> *"La prescrizione della terapia anticoagulante orale è a carico del SSN limitatamente alla FANV e al rispetto del percorso decisionale illustrato ai punti A, B, C, D."*

**Source:** `nota-97.pdf` p. 1

### 4.3 CHA2DS2-VASc Score Components (Tab. 1)

| Component | Condition | Weight |
|-----------|-----------|--------|
| C | Scompenso cardiaco congestizio / LVEF ridotta | +1 |
| H | Ipertensione arteriosa (PA >140/90 o terapia) | +1 |
| A2 | Età ≥75 anni | **+2** |
| D | Diabete mellito (glicemia a digiuno >126 mg/dL o trattamento con antidiabetici) | +1 |
| S2 | Pregresso ICTUS o TIA o tromboembolismo arterioso | **+2** |
| V | Vasculopatia (cardiopatia ischemica, arteriopatia periferica) | +1 |
| A | Età 65-74 anni | +1 |
| Sc | Sesso femminile | +1 |
| — | Nessuno dei precedenti | 0 |

**Source:** `nota-97.pdf` p. 2, Tab. 1

**Implementation verification:** Age scores A2 (+2) and A (+1) are mutually exclusive (can't be both ≥75 and 65-74). Max age contribution = +2. Implementation correctly enforces this via interval arithmetic: `max_age_contrib = min(2, sum_of_applicable_age_scores)`.

### 4.4 CHA2DS2-VASc Thresholds (Verbatim)

> *"C. LA TERAPIA ANTICOAGULANTE DOVRÀ ESSERE INIZIATA*
> - *in tutti i pazienti con punteggio CHA2DS2-VASc:*
> - *≥2 (se maschi) e ≥3 (se femmine)."*

**Source:** `nota-97.pdf` p. 3 (bold text in box C)

**Implementation:** `threshold_M = 2, threshold_F = 3` → `GTE(2)` for males, `GTE(3)` for females. ✅ Correct (OCR noted the original as ">2" but the correct PDF text is "≥2").

### 4.5 Risk Score Table (Tab. 2)

| Punteggio CHA2DS2-VASc | Eventi cardioembolici per 100 paz./anno (IC) |
|---|---|
| 0 | 0.78 (0.58-1.04) |
| 1 | 2.01 (1.70-2.36) |
| 2 | 3.71 (3.36-4.09) |
| 3 | 5.92 (5.53-6.34) |
| 4 | 9.27 (8.71-9.86) |
| 5 | 15.26 (14.35-16.24) |
| 6 | 19.74 (18.21-21.41) |
| 7 | 21.50 (18.75-24.64) |
| 8 | 22.38 (16.29-30.76) |
| 9 | 23.64 (10.02-52.61) |

> *"Punteggio CHA₂DS₂VASc: ≤4: Basso/moderato rischio trombo embolico (TE); >4: Alto rischio TE"*

**Source:** `nota-97.pdf` p. 2, Tab. 2

### 4.6 NAO/DOAC Dosing Table (Tab. 4 — Allegato 2)

**Source:** `nota-97-all-2.pdf` p. 7 (Tab. 4)

#### Apixaban
| Regime | Dose | Criteria |
|--------|------|---------|
| Standard | **5 mg × 2/die** | Default |
| Ridotta | **2,5 mg × 2/die** | ≥2 of: {età >80 anni, peso <60 kg, Creatinina >1,5 mg/dL} |
| Ridotta | **2,5 mg × 2/die** | VFG 15-29 ml/min |
| Controindicato | — | VFG <15 ml/min o in dialisi |

#### Dabigatran
| Regime | Dose | Criteria |
|--------|------|---------|
| Standard | **150 mg × 2/die** | Default |
| Ridotta | **110 mg × 2/die** | Età >80 anni, oppure associato a verapamil |
| Ridotta | **110 mg × 2/die** | Fra 75 e 80 anni + VFG 30-50 ml/min oppure aumentato rischio sanguinamento |
| Controindicato | — | VFG <30 ml/min |

#### Edoxaban
| Regime | Dose | Criteria |
|--------|------|---------|
| Standard | **60 mg/die** monosomministrazione | Default |
| Ridotta | **30 mg/die** | VFG 15-50 ml/min, oppure peso <60 kg, oppure inibitori P-glicoproteina |
| Non raccomandato | — | VFG <15 ml/min o in dialisi |

#### Rivaroxaban
| Regime | Dose | Criteria |
|--------|------|---------|
| Standard | **20 mg/die** monosomministrazione | Default |
| Ridotta | **15 mg/die** | VFG 30-49 ml/min oppure VFG 15-29 ml/min |
| Non raccomandato | — | VFG <15 ml/min |

### 4.7 Valvular Atrial Fibrillation Exclusion (Verbatim)

> *"Gli AVK sono l'unico trattamento anticoagulante indicato per i pazienti con protesi valvolari cardiache meccaniche e/o fibrillazione atriale valvolare. I NAO/NOAC non si sono dimostrati né efficaci né sicuri in tali pazienti."*

**Source:** `nota-97.pdf` p. 3 (bold text)

### 4.8 Main Contraindications (Allegato 2)
Conditions that "strongly discourage" initiation:
- Emorragia maggiore in atto
- Diatesi emorragica congenita nota
- Gravidanza
- Ipersensibilità documentata al farmaco

**Source:** `nota-97-all-2.pdf` p. 3

### 4.9 Rule Mapping

| PDF Criterion | Rule ID | Implementation |
|---|---|---|
| FANV diagnosis + ECG | N97_SCOPE_001 | `diagnosi_fanv AND ecg_fanv` |
| Drug in N97 scope | N97_SCOPE_002 | drug list check |
| Valvular AF → AVK only exclusion | N97_EXCL_HARD_001 | `fibrillazione_atriale_valvolare` |
| Prosthetic valve exclusion | N97_EXCL_HARD_002 | `protesi_valvolari` |
| CHA2DS2-VASc score threshold | N97_PATH_001 | M≥2, F≥3 via `compute_cha2ds2vasc_threshold()` |
| Apixaban dose standard 5mg×2 | N97_GDOSE_001–003 | GUIDANCE_DOSE pathway |
| Apixaban dose reduced 2.5mg×2 | N97_GDOSE_002 | COUNT_GEQ(2, [age>80, wt<60, creat>1.5]) |
| Dabigatran dose guidance | N97_GDOSE_004–006 | GUIDANCE_DOSE |
| Edoxaban dose guidance | N97_GDOSE_007–009 | GUIDANCE_DOSE |
| Rivaroxaban dose guidance | N97_GDOSE_010–012 | GUIDANCE_DOSE |
| Renal failure guidance | N97_GWARN_001–003 | GUIDANCE_WARN |

---

## 5. Cross-Note Dependencies

| Dependency | Implementation |
|-----------|----------------|
| Nota 01 misoprostolo+diclofenac → Nota 66 | N01_EXCEPT_001: ROUTE_TO(nota_66); N66_SCOPE_001 accepts this drug combo |
| Nota 66 drugs require Nota 66 pathway | ROUTE decision propagated via `routing_nota` field in engine output |

---

## 6. Ground Truth Files

See:
- `data/ground_truth/nota_01_ground_truth.json`
- `data/ground_truth/nota_13_ground_truth.json`
- `data/ground_truth/nota_66_ground_truth.json`
- `data/ground_truth/nota_97_ground_truth.json`

---

*All tables extracted from verbatim PDF text. Where verbatim text is abbreviated, exact quotes are provided with page references.*
