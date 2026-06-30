"""
Generate evaluation/results/OVERNIGHT_SUMMARY.md from all the JSON reports
produced by the overnight orchestrator.

Reads any report it finds under evaluation/results/ and assembles a single
human-readable Markdown that the user can scan in the morning.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


_PROJECT = Path(__file__).resolve().parent.parent.parent
_RESULTS = _PROJECT / "evaluation" / "results"
_AUDIT = _PROJECT.parent / "audit"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fmt(v, fmt=".4f"):
    if v is None or v == "":
        return "—"
    try:
        return format(float(v), fmt)
    except (ValueError, TypeError):
        return str(v)


def main() -> int:
    out: list[str] = []
    out.append(f"# Overnight Evaluation Summary")
    out.append("")
    out.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_")
    out.append("")

    # ── PDF audit ───────────────────────────────────────────────
    audit = _load(_AUDIT / "PDF_AUDIT_REPORT.json")
    out.append("## 1. Maniacal PDF→rule fidelity audit")
    out.append("")
    if audit:
        s = audit.get("summary", {})
        total = sum(s.values())
        out.append(f"_{total} rules audited._")
        out.append("")
        out.append("| Status | Count | Severity |")
        out.append("|---|---|---|")
        for k in ("VERBATIM_FOUND", "APPROX_FOUND", "PARAPHRASE_DOCUMENTED", "WRONG_PAGE", "FABRICATED"):
            out.append(f"| {k} | {s.get(k, 0)} | {('INFO','INFO','MEDIO','ALTO','BLOCCANTE')[('VERBATIM_FOUND','APPROX_FOUND','PARAPHRASE_DOCUMENTED','WRONG_PAGE','FABRICATED').index(k)]} |")
        out.append("")
        if s.get("FABRICATED", 0) == 0:
            out.append("**✅ 0 BLOCCANTI** — pipeline procede con regole verificate.")
        else:
            out.append(f"**⚠️ {s['FABRICATED']} regole con excerpt fabbricato** — fix richiesto prima della release.")
    else:
        out.append("_(audit not yet run)_")
    out.append("")

    # ── Track 1 Rule Engine ────────────────────────────────────
    rule_eng = _load(_RESULTS / "rule_engine_report.json")
    out.append("## 2. Track 1 — Rule Engine")
    out.append("")
    if rule_eng:
        out.append(f"- Total cases: **{rule_eng.get('total_cases')}**")
        out.append(f"- Pass rate: **{_fmt(rule_eng.get('pass_rate'), '.4f')}**")
        macro = rule_eng.get("per_class_metrics", {}).get("macro_avg", {})
        out.append(f"- Macro F1: **{_fmt(macro.get('f1'), '.4f')}**")
        out.append("")
        out.append("| Classe | Precision | Recall | F1 | Support |")
        out.append("|---|---|---|---|---|")
        for cls, m in (rule_eng.get("per_class_metrics") or {}).items():
            if cls == "macro_avg":
                continue
            out.append(
                f"| {cls} | {_fmt(m.get('precision'))} | {_fmt(m.get('recall'))} "
                f"| {_fmt(m.get('f1'))} | {m.get('support', '—')} |"
            )
    else:
        out.append("_(rule engine report not found)_")
    out.append("")

    # ── Track 2 Retrieval ──────────────────────────────────────
    retr = _load(_RESULTS / "retrieval_report.json")
    out.append("## 3. Track 2 — Retrieval")
    out.append("")
    if retr:
        agg = retr.get("aggregate", {})
        recall_at_k = agg.get("recall_at_k", {})
        out.append(f"- Recall@3 = **{_fmt(recall_at_k.get('3'))}** "
                   f"Recall@5 = **{_fmt(recall_at_k.get('5'))}** "
                   f"Recall@10 = **{_fmt(recall_at_k.get('10'))}**")
        precision_at_k = agg.get("precision_at_k", {})
        out.append(f"- Precision@3 = **{_fmt(precision_at_k.get('3'))}** "
                   f"Precision@5 = **{_fmt(precision_at_k.get('5'))}**")
        out.append(f"- MRR = **{_fmt(agg.get('mrr'))}**")
        stage = agg.get("anchor_stage_coverage", {})
        out.append(f"- Stage A (anchor) = {_fmt(stage.get('anchor_guided_fraction'), '.2%')} "
                   f"Stage B (semantic) = {_fmt(stage.get('semantic_fraction'), '.2%')}")
        out.append(f"- Total cases: {agg.get('total_cases', '—')}")
    else:
        out.append("_(retrieval report not found)_")
    out.append("")

    # ── Track 3 Pipeline LLM ──────────────────────────────────
    pip = _load(_RESULTS / "pipeline_report.json")
    out.append("## 4. Track 3 — Pipeline LLM")
    out.append("")
    if pip:
        agg = pip.get("aggregate_metrics", {})
        out.append(f"- Total cases: **{agg.get('total_cases')}**")
        out.append(f"- Overall pass rate: **{_fmt(agg.get('overall_pass_rate'))}**")
        out.append(f"- Decision consistency: **{_fmt(agg.get('decision_consistency_rate'))}**")
        out.append(f"- Citation coverage: **{_fmt(agg.get('citation_coverage_rate'))}**")
        out.append(f"- Hallucination rate: **{_fmt(agg.get('hallucination_rate'))}**")
        out.append(f"- Section completeness: **{_fmt(agg.get('section_completeness_rate'))}**")
        # Token stats
        tok = agg.get("token_stats", {}).get("total_tokens", {})
        out.append(f"- Mean total tokens/case: {_fmt(tok.get('mean'), '.0f')} "
                   f"(median {_fmt(tok.get('median'), '.0f')}, max {_fmt(tok.get('max'), '.0f')})")
    else:
        out.append("_(pipeline report not found)_")
    out.append("")

    # ── LLM-Output deterministic metrics ─────────────────────
    llm = _load(_RESULTS / "llm_output_metrics.json")
    out.append("## 5. LLM-Output deterministic metrics")
    out.append("")
    if llm:
        a = llm.get("aggregate", {})
        n_total = a.get("n_cases")
        out.append("| Metric | Mean | Median | n |")
        out.append("|---|---|---|---|")
        for k in ("claim_coverage_score", "citation_precision", "citation_recall",
                  "citation_f1", "gold_citation_recall", "decision_compliance_score",
                  "rouge_l_f1",
                  "sentence_support_rate_strict", "sentence_support_rate_loose",
                  "sentence_support_mean_max_sim",
                  "decision_rationale_alignment"):
            v = a.get(k, {})
            if isinstance(v, dict):
                out.append(f"| {k} | {_fmt(v.get('mean'))} | {_fmt(v.get('median'))} | {v.get('n')} |")
        # Footnote when a metric is computed on a subset
        dr = a.get("decision_rationale_alignment", {})
        if isinstance(dr, dict) and isinstance(n_total, int) and dr.get("n", n_total) < n_total:
            skipped = n_total - dr["n"]
            out.append("")
            out.append(f"_Nota: `decision_rationale_alignment` è definito solo sui casi con "
                       f"`blocking_rules` non vuoto ({dr['n']}/{n_total}); i restanti {skipped} casi "
                       f"sono RIMBORSABILE_standard senza regole bloccanti per definizione._")
    else:
        out.append("_(llm_output_metrics not found)_")
    out.append("")

    # ── NLI Faithfulness ────────────────────────────────────
    nli = _load(_RESULTS / "nli_faithfulness.json")
    out.append("## 6. NLI Faithfulness (mDeBERTa, deterministic)")
    out.append("")
    if nli:
        a = nli.get("aggregate", {})
        out.append(f"- Mean entailment rate: **{_fmt(a.get('mean_entailment_rate'))}**")
        out.append(f"- Mean contradiction rate: **{_fmt(a.get('mean_contradiction_rate'))}**")
        out.append(f"- Cases evaluated: {a.get('n_cases_evaluated')}")
    else:
        out.append("_(nli_faithfulness not found)_")
    out.append("")

    # ── Faithfulness Verbatim ────────────────────────────────
    verb = _load(_RESULTS / "faithfulness_verbatim.json")
    out.append("## 7. Faithfulness Verbatim (3-gram, deterministic)")
    out.append("")
    if verb:
        a = verb.get("aggregate", {})
        out.append(f"- Mean verbatim quote rate: **{_fmt(a.get('mean_verbatim_quote_rate'))}**")
        out.append(f"- Mean 3-gram coverage: **{_fmt(a.get('mean_3gram_coverage'))}**")
        out.append(f"- Cases evaluated: {verb.get('n_cases_evaluated')}")
    else:
        out.append("_(faithfulness_verbatim not found)_")
    out.append("")

    # ── Excerpt Match ────────────────────────────────────────
    exc = _load(_RESULTS / "excerpt_match.json")
    exc_loose = _load(_RESULTS / "excerpt_match_loose.json")
    out.append("## 8. Excerpt Match (gold PDF excerpt → LLM output)")
    out.append("")
    if exc:
        a = exc.get("aggregate", {})
        thr = a.get('ngram_threshold', '?')
        out.append(f"- (soglia stretta {thr}) excerpt_match_rate_llm = **{_fmt(a.get('excerpt_match_rate_llm'))}** "
                   f"· retrieval = **{_fmt(a.get('excerpt_match_rate_retrieval'))}**")
        out.append(f"- gold_anchor_recall@3 / @5 / @10 = "
                   f"**{_fmt(a.get('gold_anchor_recall_at_3'))}** / "
                   f"**{_fmt(a.get('gold_anchor_recall_at_5'))}** / "
                   f"**{_fmt(a.get('gold_anchor_recall_at_10'))}**")
    if exc_loose:
        a = exc_loose.get("aggregate", {})
        thr = a.get('ngram_threshold', '?')
        out.append(f"- (soglia lasca {thr}) excerpt_match_rate_llm = **{_fmt(a.get('excerpt_match_rate_llm'))}** "
                   f"· retrieval = **{_fmt(a.get('excerpt_match_rate_retrieval'))}**")
    if not exc and not exc_loose:
        out.append("_(excerpt_match not found)_")
    out.append("")

    # ── BLEU / chrF (deterministic lexical alignment) ────────
    bc = _load(_RESULTS / "bleu_chrf.json")
    out.append("## 8b. BLEU / chrF — MOTIVAZIONE vs source (deterministic)")
    out.append("")
    if bc:
        a = bc.get("aggregate", {})
        out.append(f"_n_cases: {a.get('n_cases_evaluated')} (skipped {a.get('n_cases_skipped')})._")
        out.append("")
        out.append("| Metric | Mean | Median | std | n |")
        out.append("|---|---|---|---|---|")
        for k in ("bleu_vs_chunks", "chrf_vs_chunks", "chrfpp_vs_chunks",
                  "bleu_vs_excerpt", "chrf_vs_excerpt", "chrfpp_vs_excerpt"):
            m = a.get(k)
            if m:
                out.append(f"| {k} | {_fmt(m.get('mean'))} | {_fmt(m.get('median'))} | {_fmt(m.get('std'))} | {m.get('n')} |")
    else:
        out.append("_(bleu_chrf not run)_")
    out.append("")

    # ── RAGAS ───────────────────────────────────────────────
    ragas = _load(_RESULTS / "ragas_report.json")
    out.append("## 9. RAGAS Metrics (LLM judge: Llama 3.1 8B, italianized prompts)")
    out.append("")
    if ragas:
        a = ragas.get("aggregate", {})
        out.append(f"_n_cases: {ragas.get('n_cases')}, judge: {ragas.get('judge_llm')}, "
                   f"wall-time: {_fmt(ragas.get('wall_time_s'), '.0f')}s_")
        out.append("")
        out.append("| Metric | Mean | Median | n |")
        out.append("|---|---|---|---|")
        for k, m in a.items():
            if isinstance(m, dict):
                out.append(f"| {k} | {_fmt(m.get('mean'))} | {_fmt(m.get('median'))} | {m.get('n')} |")
    else:
        out.append("_(ragas not run, or skipped)_")
    out.append("")

    # ── QAEval ──────────────────────────────────────────────
    qa = _load(_RESULTS / "qaeval.json")
    out.append("## 10. QAEval (Malasi-style F1 on micro-questions)")
    out.append("")
    if qa:
        a = qa.get("aggregate", {})
        out.append(f"- Mean Recall: **{_fmt(a.get('mean_recall'))}**")
        out.append(f"- Mean Precision: **{_fmt(a.get('mean_precision'))}**")
        out.append(f"- Mean F1: **{_fmt(a.get('mean_f1'))}**")
        out.append(f"- Median F1: **{_fmt(a.get('median_f1'))}**")
        out.append(f"- Cases evaluated: {a.get('n_cases_evaluated')}")
    else:
        out.append("_(qaeval not run, or skipped)_")
    out.append("")

    # ── Composite Scores ─────────────────────────────────────
    comp = _load(_RESULTS / "composite_scores.json")
    out.append("## 11. Composite Scores (Malasi-inspired)")
    out.append("")
    if comp:
        weights = comp.get("weights", {})
        out.append(f"_Weights: α(Decision)={weights.get('alpha_decision')}, "
                   f"β(Evidence)={weights.get('beta_evidence')}, "
                   f"γ(Utility)={weights.get('gamma_utility')}, "
                   f"δ(Quality)={weights.get('delta_quality')}_")
        out.append("")
        a = comp.get("aggregate", {})
        out.append("| Composite | Mean | Median | Trimmed Mean | Std | n |")
        out.append("|---|---|---|---|---|---|")
        for k in ("DecisionScore", "EvidenceSupport", "ContextualUtility", "AnswerQuality", "ALES"):
            m = a.get(k, {})
            out.append(
                f"| **{k}** | {_fmt(m.get('mean'))} | {_fmt(m.get('median'))} "
                f"| {_fmt(m.get('trimmed_mean'))} | {_fmt(m.get('std'))} | {m.get('n')} |"
            )
    else:
        out.append("_(composite_scores not generated)_")
    out.append("")

    # ── Robustness + baselines ──────────────────────────────
    rob_idem = _load(_RESULTS / "robustness_idempotency.json")
    rob_bnd = _load(_RESULTS / "robustness_boundary.json")
    base_maj = _load(_RESULTS / "baseline_majority_class.json")
    base_llm = _load(_RESULTS / "baseline_llm_only.json")
    base_rag = _load(_RESULTS / "baseline_llm_rag.json")
    rule_eng_full = _load(_RESULTS / "rule_engine_report.json")
    out.append("## 12. Robustness + Baselines")
    out.append("")
    if rob_idem:
        n_pass = rob_idem.get('n_pass', rob_idem.get('n_passed', '?'))
        n_total = rob_idem.get('n_cases', '?')
        n_runs = rob_idem.get('n_runs_per_case', 1)
        if isinstance(n_total, int) and isinstance(n_runs, int):
            denom = f"{n_total}×{n_runs} runs"
        else:
            denom = '?'
        out.append(f"- Idempotency: **{_fmt(rob_idem.get('pass_rate'), '.2%')}** "
                   f"({n_pass}/{denom})")
    if rob_bnd:
        n_pass = rob_bnd.get('n_pass', rob_bnd.get('n_passed', '?'))
        n_total = rob_bnd.get('n_probes', rob_bnd.get('n_total', '?'))
        out.append(f"- Boundary perturbation: **{_fmt(rob_bnd.get('pass_rate'), '.2%')}** "
                   f"({n_pass}/{n_total})")
    out.append("")
    out.append("**Tabella ablation baseline:**")
    out.append("")
    out.append("| Baseline | Accuracy | Macro F1 | Note |")
    out.append("|---|---|---|---|")
    if base_maj:
        m = base_maj.get('metrics', base_maj)
        out.append(f"| Majority class (sempre RIMBORSABILE) | {_fmt(m.get('accuracy'))} | "
                   f"{_fmt(m.get('macro_f1'))} | trivial — baseline rate |")
    if base_llm:
        out.append(f"| LLM-only ({base_llm.get('model','?')}, no RAG, no rules) | "
                   f"{_fmt(base_llm.get('accuracy'))} | "
                   f"{_fmt(base_llm.get('macro_f1'))} | "
                   f"degenera a majority class |")
    if base_rag:
        k = base_rag.get('k_chunks', '?')
        out.append(f"| LLM+RAG ({base_rag.get('model','?')}, k={k}, no rules) | "
                   f"{_fmt(base_rag.get('accuracy'))} | "
                   f"{_fmt(base_rag.get('macro_f1'))} | "
                   f"retrieval ablation |")
    if rule_eng_full:
        m = rule_eng_full.get('per_class_metrics', {}).get('macro_avg', {})
        out.append(f"| **Hybrid (full system)** | "
                   f"**{_fmt(rule_eng_full.get('pass_rate'))}** | "
                   f"**{_fmt(m.get('f1'))}** | "
                   f"rule engine deterministico + RAG + LLM |")
    # Δ analysis
    if base_llm and base_rag and rule_eng_full:
        f1_llm = base_llm.get('macro_f1', 0)
        f1_rag = base_rag.get('macro_f1', 0)
        f1_full = (rule_eng_full.get('per_class_metrics', {})
                   .get('macro_avg', {}).get('f1', 0))
        out.append("")
        out.append("**Δ ablation (Macro F1):**")
        out.append(f"- Δ LLM+RAG vs LLM-only = **+{f1_rag - f1_llm:.4f}** "
                   f"(contributo del retrieval)")
        out.append(f"- Δ Hybrid vs LLM+RAG = **+{f1_full - f1_rag:.4f}** "
                   f"(contributo del rule engine)")
        out.append(f"- Δ Hybrid vs LLM-only = **+{f1_full - f1_llm:.4f}** "
                   f"(RAG + rule engine combinati)")
    out.append("")

    # ── Per-case reports ─────────────────────────────────────
    per_case_dir = _RESULTS / "per_case_reports"
    out.append("## 13. Per-case verifiable reports")
    out.append("")
    if per_case_dir.exists():
        n_md = len(list(per_case_dir.rglob("*.md")))
        n_json = len(list(per_case_dir.rglob("*.json")))
        out.append(f"- Generated: **{n_md}** markdown + **{n_json}** JSON files")
        out.append(f"- Index: `evaluation/results/per_case_reports/INDEX.md`")
    else:
        out.append("_(not generated)_")
    out.append("")

    # ── Notes ──────────────────────────────────────────────
    out.append("---")
    out.append("")
    out.append("## How to read this summary")
    out.append("")
    out.append("- **Track 1 (Rule Engine)** is the safety-critical layer — must be 100% pass.")
    out.append("- **Track 3 + LLM-Output metrics** evaluate explanation quality on multiple dimensions.")
    out.append("- **NLI faithfulness** is the deterministic counterpart to RAGAS faithfulness — "
               "if both are high, evidence is trustworthy.")
    out.append("- **ALES** is the composite score for thesis-grade comparison; "
               "see `composite_scores.json` for per-case breakdown.")
    out.append("- For verifying a single case, open "
               "`evaluation/results/per_case_reports/N{NN}/{case_id}.md` — "
               "it shows input, gold, engine output, retrieved chunks (with verbatim text), "
               "LLM explanation, and all per-case metric scores side-by-side.")
    out.append("")

    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
