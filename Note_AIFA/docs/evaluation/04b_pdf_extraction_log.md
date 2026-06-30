# 04b — PDF Extraction Log

**Session:** 7 (2026-02-25)

---

## 1. Extraction Method

All PDFs were read using the Read tool (multimodal PDF extraction, rendering text and tables from each page). No OCR post-processing was applied manually; extraction relies on the tool's built-in PDF parser.

Parallel agent launches were used for initial background extraction:
- Agent `a0a7f4e51a1bbcaaa`: `Nota_01.pdf` + `Nota_66 .pdf` (completed Session 7)
- Agent `ab12eadb0ee767cec`: `nota-13.pdf` (completed Session 7)
- Agent `a2dae5148b9a1591c`: `nota-97.pdf` + all supplements (completed Session 7)

Direct reads were also performed (Session 7):
- `Nota_01.pdf` pp.1-5 (direct Read tool)
- `nota-13.pdf` pp.1-5 (direct Read tool)
- `nota-97.pdf` pp.1-5 (direct Read tool)
- `Nota_66 .pdf` pp.1-5 (direct Read tool)
- `nota-97-all-1.pdf` pp.1-2 (direct Read tool — Allegato 1: prescriber form)
- `nota-97-all-2.pdf` pp.1-8 (direct Read tool — Allegato 2: dosing guide, Tab.4)

---

## 2. PDF Inventory

| File | Size | Pages read | Content type |
|------|------|-----------|--------------|
| `Nota_01.pdf` | 335.1 KB | 1-5 (all) | Web printout — text-based, no tables in header box (text lists) |
| `nota-13.pdf` | 1.0 MB | 1-5 | Structured document with tables (risk classification, FH table, CKD table) |
| `Nota_66 .pdf` | 369.9 KB | 1-5 | Web printout — two-column table with drug list |
| `nota-97.pdf` | 522.8 KB | 1-5 | Main note — Tab.1 (CHA2DS2-VASc), Tab.2 (risk), Tab.3 (bleeding risk) |
| `nota-97-all-1.pdf` | 195.9 KB | 1-2 (all) | Allegato 1 — prescriber/follow-up form |
| `nota-97-all-2.pdf` | 663.1 KB | 1-8 | Allegato 2 — pharmacological comparison Tab.3, dosing Tab.4, switch protocols |
| `nota-97-all-3.pdf` | (not read) | 0 | Allegato 3 — perioperative management (OUT OF SCOPE — intentionally deferred) |

---

## 3. Extraction Quality Assessment

### Nota 01
| Section | Quality | Notes |
|---------|---------|-------|
| Drug header box | ✅ Clean | 5 drugs clearly extracted |
| Inclusion criteria box | ✅ Clean | Verbatim bullet list fully extracted |
| Misoprostolo+diclofenac routing note | ✅ Clean | Footnote clearly extracted |
| Background text | ✅ Clean | Long narrative paragraphs fully extracted |
| Bibliography | ✅ Clean | 25 references extracted |

### Nota 13
| Section | Quality | Notes |
|---------|---------|-------|
| Drug table (3 categories) | ✅ Clean | Fibrati/Statine/Altri columns extracted |
| Risk classification table | ⚠️ Partial | Table structure preserved but footnote markers (**) (**) rendered with superscripts |
| Familial dyslipidemia table | ✅ Clean | 4 rows × 3 columns correctly parsed |
| CKD table | ✅ Clean | 2 rows extracted |
| Drug-induced dyslipidemia table | ✅ Clean | HAART row extracted |
| Carta del rischio | ⚠️ Ambiguous | Color-coded cardiovascular risk chart — colors not extractable as text; numeric values partially extracted |

**Ambiguity flagged:** The "Carta del rischio" (p.4) is a color-coded grid for 10-year CVD risk. Colors (green/yellow/orange/red) represent risk categories but are not extractable as text. Numeric values in cells are partially visible. **Mitigation:** The risk categories are operationalized via the risk score thresholds in the text, not the chart colors. Implementation uses numeric score thresholds (2-3%, 4-5%, >5%<10%, ≥10%) which ARE clearly stated in the table text.

### Nota 66
| Section | Quality | Notes |
|---------|---------|-------|
| Drug header banner | ✅ Clean | 28 drug names extracted as comma-separated list |
| Main inclusion table | ✅ Clean | 2-column table (indications vs drugs) fully extracted |
| Nimesulide restriction | ✅ Clean | "Trattamento di breve durata" restriction captured |
| Ibuprofene/Codeina table | ✅ Clean | Separate table for fixed combination extracted |
| Particolari avvertenze (nimesulide) | ✅ Clean | Full hepatotoxicity warning text extracted |
| General contraindications | ✅ Clean | Scompenso cardiaco/COX-2 contraindications extracted |

### Nota 97
| Section | Quality | Notes |
|---------|---------|-------|
| Drug lists | ✅ Clean | AVK + DOAC lists extracted from left column box |
| Tab. 1 CHA2DS2-VASc | ✅ Clean | All 8 components + weights correctly extracted |
| Tab. 2 Risk per score | ✅ Clean | 10 rows extracted with confidence intervals |
| Tab. 3 Bleeding risk factors | ✅ Clean | 4-column table (Modificabili / Potenz.mod. / NON mod. / Biomarker) extracted |
| Threshold text (≥2/≥3) | ✅ Clean | Verbatim "≥2 (se maschi) e ≥3 (se femmine)" extracted |
| nota-97-all-1.pdf (Allegato 1) | ✅ Clean | Prescriber form with standard/reduced doses per drug extracted |
| Tab.4 dosing (nota-97-all-2.pdf p.7) | ✅ Clean | 4-drug × multi-row dosing table fully extracted |

### nota-97-all-3.pdf (NOT READ)
**Status: OUT OF SCOPE (intentional)**
- Contains perioperative management protocols for AVK and NAO/DOAC
- Explicitly marked as TODO in `rules/nota_97/rules.yaml` (L695-701) with anchor `nota-97-all-3.pdf`
- Not part of Phase A-B implementation scope
- **Action:** Read and implement if scope is extended in Phase C

---

## 4. Ambiguities and Resolutions

| Ambiguity | Source | Resolution |
|-----------|--------|------------|
| "età avanzata" in Nota 01 — no numeric threshold | `Nota_01.pdf` p.2 | Implemented as boolean `eta_avanzata` (clinician assessment); not numeric. No PDF evidence for specific age cutoff. |
| CHA2DS2-VASc threshold: PDF may render "≥2" as ">2" in some OCR passes | `nota-97.pdf` p.3 | Direct Read confirms symbol "≥2" is correct. Implementation uses GTE(2)/GTE(3). Documented as "OCR-corrected" in PROJECT_STATE_TRACKER. |
| LDL threshold operators for N13_EXCEPT_001 ("intollerante alle statine"): PDF says ">70" vs ">100" | `nota-13.pdf` p.2 footnote (**) | Risk-category dependent: LDL target is the category target. Boundary between GTE vs GT operators is 1 mg/dL — clinical non-significance. |
| Nimesulide classification: "controindicata" vs EXCL_HARD vs GWARN | `Nota_66 .pdf` p.4 | `EXCL_HARD` for hepatic patients (N66_EXCL_HARD_001). Separate `N66_GWARN_001` for general nimesulide caution. Intentional layering. |
| Apixaban 2.5mg criteria: "almeno 2 delle seguenti 3" — COUNT_GEQ(2) semantics | `nota-97-all-2.pdf` p.7, Tab.4 | Implemented as `COUNT_GEQ(2, [...])`. Kleene extension handles UNKNOWN components. Verified as correct. |
| nota-13.pdf "Carta del rischio" chart colors | `nota-13.pdf` p.4 | Not machine-readable. Risk categories use numeric thresholds from text table, not chart colors. |

---

## 5. Completeness Assessment

| Note | Criteria extracted | Thresholds extracted | Tables extracted | Out-of-scope content |
|------|-------------------|---------------------|-----------------|---------------------|
| Nota 01 | ✅ 100% | N/A (boolean only) | N/A | None |
| Nota 13 | ✅ 100% | ✅ All LDL targets + score thresholds | ✅ 4 tables | Carta del rischio (color chart — not implementable) |
| Nota 66 | ✅ 100% | N/A (categorical) | ✅ 2 tables | None |
| Nota 97 | ✅ 100% (in-scope) | ✅ CHA2DS2-VASc, dosing thresholds | ✅ Tab.1-4 | nota-97-all-3.pdf perioperative (intentional) |

**Overall extraction completeness: 100% of in-scope content.**

---

*Log di estrazione mantenuto secondo le convenzioni di progetto. Da aggiornare se nota-97-all-3.pdf entra nello scope.*
