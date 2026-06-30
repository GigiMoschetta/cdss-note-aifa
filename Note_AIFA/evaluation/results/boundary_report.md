# Boundary perturbation report

Probes that target threshold values where the rule engine could plausibly flip its decision (eta=74/75, peso=60, VFG=30, creat=1.5, score=1/2/3, …).
Generated from `evaluation/robustness/boundary_perturbation.py`.

**Totals:** 9 probes, pass rate **1.0000** (9/9).

| Probe family | n | pass | fail | pass rate | Values tested |
|---|---:|---:|---:|---:|---|
| `apixaban_eta_threshold_80` | 3 | 3 | 0 | 1.0000 | 79, 80, 81 |
| `cha2ds2vasc_male_threshold_2` | 3 | 3 | 0 | 1.0000 | None, None, None |
| `dabigatran_vfg_excl_30` | 3 | 3 | 0 | 1.0000 | 29.0, 30.0, 31.0 |
