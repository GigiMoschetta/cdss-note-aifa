# 07 — Baseline Reproduction Report

**Session:** 7 (2026-02-25)
**Commands run:** 2026-02-25 ~15:17 local time

---

## 1. Environment

| Item | Value |
|------|-------|
| OS | Linux 6.17.0-14-generic |
| Python | 3.12.3 |
| Project root | `/home/gigimoschetta/Desktop/Tesi Triennale/Note_AIFA/` |
| venv | `aifa_rule_engine/.venv/` |
| Rule Engine version | v3.3.0 |
| pytest | 9.0.2 |
| LLM backend | Ollama llama3.1:8b @ http://localhost:11434 (not active this session) |
| ChromaDB | `rag_pipeline/chroma_db/` — 97 chunks, 4 collections |

---

## 2. `make test-local` — Unit Tests

**Command:**
```
aifa_rule_engine/.venv/bin/pytest aifa_rule_engine/tests/ -v --tb=short
```

**Result: 173/173 PASS (0.28s)**

```
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0
asyncio: mode=Mode.AUTO
collected 173 items

test_derived_vars.py        29 PASSED
test_expression_eval.py     28 PASSED
test_nota_01.py             10 PASSED
test_nota_66.py             16 PASSED
test_nota_97.py             22 PASSED
test_properties.py           6 PASSED
test_startup_validation.py   8 PASSED
test_three_valued.py        54 PASSED

============================= 173 passed in 0.28s ==============================
```

**Test file coverage:**
| File | Cases | What it covers |
|------|-------|----------------|
| `test_three_valued.py` | 54 | Kleene truth tables, NOT, COUNT_GEQ, SCORE_RANGE_GTE, numeric comparison |
| `test_expression_eval.py` | 28 | AST node types, AND/OR short-circuit, BETWEEN, IN, missing fields |
| `test_derived_vars.py` | 29 | CHA2DS2-VASc range, threshold, apixaban count, categoria_rischio |
| `test_nota_01.py` | 10 | Nota 01 scope, inclusion, exception (routing), guidance (warning) |
| `test_nota_66.py` | 16 | Nota 66 scope, inclusion (nimesulide, ibuprofene_codeina), EXCL_HARD, warnings |
| `test_nota_97.py` | 22 | Nota 97 scope, EXCL_HARD, pathway (CHA2DS2-VASc), guidance dose, safety invariants, short-circuit |
| `test_startup_validation.py` | 8 | S1-S6 startup validation (DAG cycles, type errors, missing anchors, duplicate IDs) |
| `test_properties.py` | 6 | Cross-nota safety invariants (guidance not in trace, dose-on-denial, routed=null, score monotone) |

**⚠️ Gap:** `test_nota_13.py` does **not exist**. Nota 13 rules (7 rules) have no dedicated unit test file. Integration coverage exists via gold standard cases only.

---

## 3. `make eval-rule-engine` — Gold Standard Regression

**Command:**
```
aifa_rule_engine/.venv/bin/python -m evaluation.scripts.evaluate_rule_engine \
    --json-report evaluation/results/rule_engine_report.json
```

**Result: 37/37 PASS (100.0%), Macro F1 = 1.0000**

```
Rules loaded: 38 rules

Nota 97 (12 cases): 12/12 PASS
Nota 01 (8 cases):   8/8  PASS
Nota 13 (8 cases):   8/8  PASS
Nota 66 (9 cases):   9/9  PASS

======================================================================
SUMMARY: 37/37 cases passed (100.0%)
======================================================================

Track 1 — Per-class Metrics
Class                   Precision     Recall         F1    Support
---------------------------------------------------------
RIMBORSABILE               1.0000     1.0000     1.0000         18
NON_RIMBORSABILE           1.0000     1.0000     1.0000         16
NON_DETERMINABILE          1.0000     1.0000     1.0000          2
ROUTED                     1.0000     1.0000     1.0000          1

Macro F1: 1.0000
```

**Report file:** `evaluation/results/rule_engine_report.json` (35,992 bytes, 2026-02-25 15:17)

---

## 4. Pipeline Evaluation (Cached — Session 6 run)

**Services were not running in Session 7.** The pipeline_report.json is from the Session 6 run (2026-02-25 01:00 UTC).

**Pipeline command (run in Session 6 with `make up-local` + `make eval-pipeline`):**
```
aifa_rule_engine/.venv/bin/python -m evaluation.scripts.evaluate_pipeline \
    --verbose \
    --json-report evaluation/results/pipeline_report.json
```

**LLM:** `ollama/llama3.1:8b`, temperature=0
**Report file:** `evaluation/results/pipeline_report.json` (111,808 bytes, 2026-02-25 02:00)

### 4.1 Aggregate Metrics

| Metric | Value | Thesis Threshold | Status |
|--------|-------|-----------------|--------|
| Overall pass rate | 91.9% (34/37) | — | — |
| Faithfulness rate | **100.0%** | ≥100% | ✅ |
| Citation coverage rate | **94.6%** (35/37) | ≥90% | ✅ |
| Hallucination rate | **0.0%** | ≤10% | ✅ |
| Section completeness | **100.0%** | =100% | ✅ |

### 4.2 Failing Cases (3/37)

| Case | Metric failing | Detail |
|------|---------------|--------|
| N97-005 | `citation_complete=False` | `nota-97.pdf p.4` missing from FONTI section |
| N97-006 | `citation_complete=False` | `nota-97-all-2.pdf p.6` missing from FONTI section |
| N13-007 | `strings_ok=False` | `contains:'ezetimibe'` check fails — drug name absent from explanation |

**Root cause (N97-005, N97-006):** LLM mentions page anchors in body but does not reproduce the exact `nota-97.pdf p.4` / `nota-97-all-2.pdf p.6` format that the citation completeness checker requires.

**Root cause (N13-007):** N13-007 is the statin intolerance bypass case. The LLM explains the exception pathway without explicitly naming "ezetimibe" — uses generic "farmaco alternativo" or omits the drug name.

### 4.3 Token Statistics

| Stat | Value |
|------|-------|
| Mean prompt tokens | 4,013.8 |
| Median prompt tokens | 4,096 |
| Max prompt tokens | 4,096 (at context limit) |
| Mean completion tokens | 352.3 |
| Mean total tokens | 4,366.1 |

**⚠️ Note:** Median prompt = 4,096 = context limit → many cases are hitting the context window. This may contribute to citation omissions.

---

## 5. Retrieval Evaluation (Track 2, Cached)

**Report file:** `evaluation/results/retrieval_report.json` (17,882 bytes, 2026-02-25 02:00)

| Metric | Value |
|--------|-------|
| Recall@3 | 0.60 |
| Recall@5 | 0.70 |
| Recall@10 | 0.76 |
| Precision@3 | 0.71 |
| MRR | 0.76 |
| Stage A (anchor-guided) coverage | 44.4% |
| Stage B (semantic+reranked) coverage | 55.6% |

---

## 6. Summary: Verification Gates

| Gate | Command | Status |
|------|---------|--------|
| Unit tests | `make test-local` | ✅ 173/173 |
| Rule Engine regression | `make eval-rule-engine` | ✅ 37/37 |
| Pipeline evaluation | `make eval-pipeline` (cached) | ✅ All 4 thesis thresholds met |
| Retrieval evaluation | `make eval-retrieval` (cached) | ✅ MRR=0.76, Recall@5=0.70 |

**Overall assessment:** All verification gates pass. The 3 remaining pipeline failures are non-blocking (overall pass rate threshold was not defined, and all 4 specific metric thresholds are met).

---

## 7. Addendum — Current Status (Session 14, 2026-02-28)

Since this Session 7 baseline was captured, the following has changed:

| Gate | Session 7 | Current (Session 14) |
|------|-----------|---------------------|
| Unit tests | 173/173 | **382/382** |
| Gold standard | 37/37 | **100/100** (Macro F1=1.0) |
| Pipeline eval | 34/37 (91.9%) | **100/100** (100.0%) |
| Retrieval | MRR=0.76, Recall@5=0.70 | MRR=0.91, Recall@5=0.89 |

Key additions since Session 7:
- `test_nota_13.py` created (Session 8) — closes the gap noted in Section 2
- `test_drug_normalizer.py` — 90 tests for INN + brand-name normalization
- `test_validators.py`, `test_justification.py`, `test_retriever_anchor.py` — orchestrator tests
- Gold standard expanded: 37→97 (Sessions 8-12) → 100 (Session 14, 3 new N66 drug cases)
- Metric renamed: `faithfulness_rate` → `decision_consistency_rate` (Session 14)
