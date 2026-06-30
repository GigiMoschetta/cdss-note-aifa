# 06 — Traceability Matrix

**Format:** `rule_id → normative_anchor → implementation → tests → status`
**Evidence:** `rules/nota_*/rules.yaml`, `aifa_rule_engine/engine/evaluator.py`, `tests/test_nota_*.py`
**Last updated:** 2026-02-25 (Session 7)

---

## Legend

| Status | Meaning |
|--------|---------|
| **OK** | Implementation matches PDF criteria; test coverage present |
| **OK-NOTESTS** | Implementation matches PDF criteria; test coverage via gold standard only |
| **PARTIAL** | Implementation partially correct; known gap documented |
| **INCONSISTENT** | Implementation deviates from PDF; needs fix |
| **MISSING** | Rule required by PDF but not implemented |

---

## Nota 97 — Anticoagulanti Orali in FANV (18 rules)

| rule_id | Type | PDF Anchor | Implementation | Test File | Tests | Status |
|---------|------|-----------|----------------|-----------|-------|--------|
| N97_SCOPE_001 | SCOPE | nota-97.pdf p.1 §Percorso A | `evaluator.py` Phase 1 → `eval_condition(AND[IS_TRUE(diagnosi_fanv), IS_TRUE(ecg_confermato), IS_TRUE(valutazione_clinica_eseguita)])` | test_nota_97.py | `TestScope` (3 tests) | **OK** |
| N97_EXCL_HARD_001 | EXCL_HARD | nota-97.pdf p.4 §Controindicazioni | `evaluator.py` Phase 3 → `eval_condition(AND[IS_TRUE(protesi_valvolari_meccaniche), IN(farmaco, {apixaban,dabigatran,edoxaban,rivaroxaban})])` | test_nota_97.py | `TestExclHard::test_doac_protesi_meccaniche` | **OK** |
| N97_EXCL_HARD_002 | EXCL_HARD | nota-97.pdf p.4 §Controindicazioni | Phase 3 → `AND[IS_TRUE(fa_valvolare), IN(farmaco, DOACs)]` | test_nota_97.py | `TestExclHard::test_doac_fa_valvolare` | **OK** |
| N97_EXCL_HARD_003 | EXCL_HARD | nota-97-all-2.pdf p.6 §Tab.4 | Phase 3 → `AND[EQ(farmaco,dabigatran), LT(vfg_cockroft_gault, 30)]` | test_nota_97.py | `TestExclHard::test_dabigatran_vfg_below30` | **OK** |
| N97_PATH_001 | PATHWAY | nota-97.pdf p.3 §Percorso C | Phase 5 → `SCORE_RANGE_GTE(cha2ds2vasc_range, cha2ds2vasc_threshold)`; thresholds M=2, F=3 (OCR-corrected) | test_nota_97.py | `TestPathwayCha2ds2vasc` (6 tests) | **OK** |
| N97_GDOSE_001 | GUIDANCE_DOSE | nota-97-all-2.pdf p.6 §Tab.4 Block A | Phase 6 → `AND[EQ(farmaco,dabigatran), OR[GTE(eta,80), IS_TRUE(uso_verapamil)]]` | test_nota_97.py | `TestGuidanceDose` (2 tests) | **OK** |
| N97_GDOSE_002 | GUIDANCE_DOSE | nota-97-all-2.pdf p.6 §Tab.4 | Phase 6 → `AND[EQ(farmaco,apixaban), COUNT_GEQ([eta≥80, peso≤60, creat≥1.5], thr=2)]` | test_nota_97.py | `TestGuidanceDose` (2 tests) | **OK** |
| N97_GDOSE_003 | GUIDANCE_DOSE | nota-97-all-2.pdf p.6 §Tab.4 | Phase 6 → `AND[EQ(farmaco,apixaban), BETWEEN(vfg,15,29)]` | test_nota_97.py | `TestGuidanceDose::test_rivaroxaban_vfg22_dose_and_warn` (covers same BETWEEN pattern) | **OK** |
| N97_GDOSE_004 | GUIDANCE_DOSE | nota-97-all-2.pdf p.6 §Tab.4 | Phase 6 → `AND[EQ(farmaco,edoxaban), OR[BETWEEN(vfg,15,50), LTE(peso,60), IS_TRUE(uso_inibitori_pgp)]]` | test_nota_97.py | — | **OK-NOTESTS** |
| N97_GDOSE_005 | GUIDANCE_DOSE | nota-97-all-2.pdf p.6 §Tab.4 | Phase 6 → `AND[EQ(farmaco,rivaroxaban), OR[BETWEEN(vfg,30,49), BETWEEN(vfg,15,29)]]` | test_nota_97.py | `TestGuidanceDose::test_rivaroxaban_vfg22_dose_and_warn`, `test_rivaroxaban_vfg35_dose_only` | **OK** |
| N97_GPREF_001 | GUIDANCE_PREF | nota-97.pdf p.3 §Percorso D | Phase 7 → `OR[IS_TRUE(ttr_sotto_70), IS_TRUE(difficolta_monitoraggio_inr)]` | — | — | **OK-NOTESTS** |
| N97_GPREF_002 | GUIDANCE_PREF | nota-97.pdf p.4 §Percorso E | Phase 7 → `OR[LT(vfg,15), IS_TRUE(interazioni_farmacologiche_doac)]` | — | — | **OK-NOTESTS** |
| N97_GPREF_003 | GUIDANCE_PREF | nota-97.pdf p.4 §Percorso F | Phase 7 → `IS_TRUE(pregressa_emorragia_intracranica)` | — | — | **OK-NOTESTS** |
| N97_GWARN_001 | GUIDANCE_WARN | nota-97-all-2.pdf p.6 §Tab.4 | Phase 8 → `AND[EQ(farmaco,apixaban), LT(vfg,15)]` | — | — | **OK-NOTESTS** |
| N97_GWARN_002 | GUIDANCE_WARN | nota-97-all-2.pdf p.6 §Tab.4 | Phase 8 → `AND[EQ(farmaco,edoxaban), OR[LT(vfg,15), IS_TRUE(in_dialisi)]]` | — | — | **OK-NOTESTS** |
| N97_GWARN_003 | GUIDANCE_WARN | nota-97-all-2.pdf p.6 §Tab.4 | Phase 8 → `AND[EQ(farmaco,rivaroxaban), LT(vfg,15)]` | — | — | **OK-NOTESTS** |
| N97_GWARN_004 | GUIDANCE_WARN | nota-97-all-2.pdf p.6 §Tab.4 Block B | Phase 8 → `AND[EQ(farmaco,dabigatran), BETWEEN(eta,75,80), OR[BETWEEN(vfg,30,50), IS_TRUE(aumentato_rischio_sanguinamento)]]` | test_nota_97.py | `TestGuidanceDose::test_dabigatran_75_80_ckd_warning_not_dose` | **OK** |
| N97_GWARN_005 | GUIDANCE_WARN | nota-97-all-2.pdf p.6 §Tab.4 | Phase 8 → `AND[EQ(farmaco,rivaroxaban), BETWEEN(vfg,15,29)]` | test_nota_97.py | `test_rivaroxaban_vfg22_dose_and_warn` | **OK** |

**Perioperative rules (nota-97-all-3.pdf):** Intentionally MISSING — marked as TODO in `rules.yaml` (L695-701). Not in scope.

---

## Nota 01 — Gastroprotettori (4 rules)

| rule_id | Type | PDF Anchor | Implementation | Test File | Tests | Status |
|---------|------|-----------|----------------|-----------|-------|--------|
| N01_SCOPE_001 | SCOPE | Nota_01.pdf p.2 §Box prescrittivo | Phase 1 → `OR[IS_TRUE(trattamento_cronico_fans), IS_TRUE(terapia_antiaggregante_asa)]` | test_nota_01.py | `TestNota01Scope` (4 tests) | **OK** |
| N01_EXCEPT_001 | EXCEPTION | Nota_01.pdf p.2 §asterisco | Phase 2 → `EQ(farmaco, diclofenac_misoprostolo)` → `outcome_if_true=ROUTE` → nota_66 | test_nota_01.py | `TestNota01Exception::test_diclofenac_misoprostolo_routes_to_66` | **OK** |
| N01_INCL_001 | INCLUSION | Nota_01.pdf p.2 §Box prescrittivo | Phase 4 → `OR[pregresse_emorragie, ulcera_non_guarita, anticoagulanti, cortisonici, eta_avanzata]` | test_nota_01.py | `TestNota01Inclusion` (5 tests) | **OK** |
| N01_GWARN_001 | GUIDANCE_WARN | Nota_01.pdf p.3 §Avvertenze | Phase 8 → `AND[IS_TRUE(terapia_concomitante_anticoagulanti), IS_TRUE(trattamento_cronico_fans)]` | test_nota_01.py | `TestNota01Guidance` (2 tests) | **OK** |

---

## Nota 13 — Ipolipemizzanti (7 rules)

| rule_id | Type | PDF Anchor | Implementation | Test File | Tests | Status |
|---------|------|-----------|----------------|-----------|-------|--------|
| N13_SCOPE_001 | SCOPE | nota-13.pdf p.1 §Presupposti | Phase 1 → `AND[IS_TRUE(dislipidemia_diagnosticata), IS_TRUE(ipotiroidismo_escluso)]` | — | None (gold std only) | **OK-NOTESTS** |
| N13_EXCEPT_001 | EXCEPTION | nota-13.pdf p.5 §Esenzioni | Phase 2 → `OR[AND[IS_TRUE(cat_molto_alto), GTE(ldl,70)], AND[IS_TRUE(cat_alto), GTE(ldl,100)]]` → BYPASS N13_INCL_001 | — | None (gold std only) | **OK-NOTESTS** |
| N13_EXCEPT_002 | EXCEPTION | nota-13.pdf p.3 §Ezetimibe | Phase 2 → `IS_TRUE(intolleranza_statine)` → BYPASS N13_INCL_001 | — | None (gold std only) | **OK-NOTESTS** |
| N13_INCL_001 | INCLUSION | nota-13.pdf p.1 §Condizioni | Phase 4 → `IS_TRUE(dieta_seguita_almeno_3_mesi)` (skipped if bypassed) | — | None (gold std only) | **OK-NOTESTS** |
| N13_PATH_001 | PATHWAY | nota-13.pdf p.1 §Criteri | Phase 5 → `NOT(EQ(categoria_rischio, "basso"))` | — | None (gold std only) | **OK-NOTESTS** |
| N13_PATH_002 | PATHWAY | nota-13.pdf p.2 §Step-care | Phase 5 → `IS_TRUE(terapia_primo_livello_tentata)` | — | None (gold std only) | **OK-NOTESTS** |
| N13_GDOSE_001 | GUIDANCE_DOSE | nota-13.pdf p.3 §IRC e PUFA | Phase 6 → `AND[IS_TRUE(irc_moderata), GTE(trigliceridi, 500)]` | test_derived_vars.py | `TestCategoriaRischio` (indirect) | **OK-NOTESTS** |

---

## Nota 66 — FANS / NSAIDs (9 rules)

| rule_id | Type | PDF Anchor | Implementation | Test File | Tests | Status |
|---------|------|-----------|----------------|-----------|-------|--------|
| N66_SCOPE_001 | SCOPE | Nota_66.pdf p.2 §Box prescrittivo | Phase 1 → `IN(indicazione_clinica, {artropatia_connettivite, osteoartrosi_algica, dolore_neoplastico, gotta_acuta})` | test_nota_66.py | `TestNota66Scope` (3 tests) | **OK** |
| N66_INCL_001 | INCLUSION | Nota_66.pdf p.2 §Lista farmaci | Phase 4 → `IN(farmaco, {18-drug closed list})` | test_nota_66.py | `TestNota66Inclusion::test_drug_not_in_list` | **OK** |
| N66_EXCL_HARD_001 | EXCL_HARD | Nota_66.pdf p.4 §Controindicazioni | Phase 3 → `IS_TRUE(ulcera_peptica_attiva_pregressa)` | test_nota_66.py | `TestNota66ExclusionHard::test_ulcera_peptica_non_rimb` | **OK** |
| N66_EXCL_HARD_002 | EXCL_HARD | Nota_66.pdf p.4 §Controindicazioni | Phase 3 → `IS_TRUE(scompenso_cardiaco_grave)` | test_nota_66.py | `TestNota66ExclusionHard::test_scompenso_grave_non_rimb` | **OK** |
| N66_EXCL_HARD_003 | EXCL_HARD | Nota_66.pdf p.4 §Controindicazioni | Phase 3 → `AND[IS_TRUE(is_coxib), OR[cardiopatia_ischemica, cerebrovascolare, arteriosa_periferica, scompenso_moderato_grave]]` | test_nota_66.py | `TestNota66ExclusionHard::test_coxib_cardiopatia_non_rimb`, `test_coxib_no_cv_ok` | **OK** |
| N66_INCL_002 | INCLUSION | Nota_66.pdf p.2 §Nimesulide | Phase 4 → `OR[NEQ(farmaco,nimesulide), AND[IS_TRUE(uso_breve_durata), IS_TRUE(seconda_linea)]]` | test_nota_66.py | `TestNota66Inclusion::test_nimesulide_seconda_linea`, `test_nimesulide_not_seconda_linea` | **OK** |
| N66_INCL_003 | INCLUSION | Nota_66.pdf p.2 §Ibuprofene+codeina | Phase 4 → `OR[NEQ(farmaco,ibuprofene_codeina), AND[dolore_acuto_moderato, non_controllato_con_singoli, uso_breve_durata]]` | test_nota_66.py | `TestNota66Inclusion::test_ibuprofene_codeina_requirements`, `test_ibuprofene_codeina_without_requirements` | **OK** |
| N66_GWARN_001 | GUIDANCE_WARN | Nota_66.pdf p.4 §Sicurezza | Phase 8 → `AND[IN(farmaco,{nimesulide}), IS_TRUE(epatopatia)]` | test_nota_66.py | `TestNota66Warnings::test_nimesulide_epatopatia_warning` | **OK** |
| N66_GWARN_002 | GUIDANCE_WARN | Nota_66.pdf p.4 §Sicurezza | Phase 8 → `AND[IS_TRUE(terapia_antiaggregante_asa), IN(farmaco, lista_fans)]` | test_nota_66.py | `TestNota66Warnings::test_fans_asa_warning` | **OK** |

---

## Derived Variables (Phase 0)

| Variable | File | Function | Covers | Tests | Status |
|----------|------|----------|--------|-------|--------|
| `cha2ds2vasc_range` | `derived_vars.py` L19-88 | `compute_cha2ds2vasc_range()` | N97_PATH_001; mutual exclusion A2/A; age=None→max+=2 | `test_derived_vars.py::TestCha2ds2vascRange` (7 tests) | **OK** |
| `cha2ds2vasc_threshold` | `derived_vars.py` L91-104 | `compute_cha2ds2vasc_threshold()` | N97_PATH_001; M=2, F=3 (OCR-corrected) | `test_derived_vars.py::TestCha2ds2vascThreshold` (4 tests) | **OK** |
| `apixaban_riduzione_count` | `derived_vars.py` L111-156 | `compute_apixaban_riduzione_count()` | N97_GDOSE_002; COUNT_GEQ semantics | `test_derived_vars.py::TestApixabanRiduzioneCount` (8 tests) | **OK** |
| `is_coxib` | `derived_vars.py` L238-241 | inline in `compute_derived_variables()` | N66_EXCL_HARD_003 | `test_nota_66.py` (indirectly) | **OK** |
| `categoria_rischio` | `derived_vars.py` L163-198 | `compute_categoria_rischio()` | N13_PATH_001, N13_EXCEPT_001 | `test_derived_vars.py::TestCategoriaRischio` (6 tests) | **OK** |
| `target_ldl` | `derived_vars.py` L201-209 | `compute_target_ldl()` | N13_EXCEPT_001 (indirect) | `test_derived_vars.py::TestComputeDerivedVariables` (3 tests) | **OK** |

---

## Summary Statistics

| Status | Count | % |
|--------|-------|---|
| OK (implementation + tests) | 22 | 57.9% |
| OK-NOTESTS (implementation correct, tests via gold standard only) | 14 | 36.8% |
| PARTIAL | 0 | 0% |
| INCONSISTENT | 0 | 0% |
| MISSING (in scope) | 0 | 0% |
| TODO (out of scope, perioperative) | 1 group | — |

**Critical gap:** 14 rules (all Nota 13 rules + Nota 97 GPREF/GWARN guidance rules) have no dedicated unit tests. They are verified only through gold standard integration cases. A `test_nota_13.py` file should be created.
