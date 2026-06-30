"""
update_latex_v2_numbers.py — Update LaTeX thesis with v2 metrics
==================================================================

Reads the v2 results JSON files and patches the LaTeX manuscript
(`tesi_latex/chapters/cap6_risultati.tex`, `cap7_conclusioni.tex`,
`abstract.tex`) with the new numbers.

Conservative approach: only adds a new "V2 (PDF-anchored)" subsection
to cap6 with the M1..M7 numbers. Does NOT overwrite existing tables —
those become "V3.4 (legacy)" reference, the new section is the
"V2 final" current state.

Usage:
    python tools/update_latex_v2_numbers.py        # dry-run
    python tools/update_latex_v2_numbers.py --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent  # Tesi Triennale/
_RESULTS = _ROOT / "Note_AIFA" / "evaluation" / "results"
_LATEX_DIR = _ROOT / "tesi_latex" / "chapters"


def _load(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text())
    return None


def _fmt(v, fmt="{:.4f}"):
    if v is None:
        return "n/a"
    if isinstance(v, str):
        return v
    return fmt.format(v)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes to LaTeX files (default: dry-run)")
    parser.add_argument("--results-dir", type=Path, default=_RESULTS)
    parser.add_argument("--latex-dir", type=Path, default=_LATEX_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("latex_v2")

    R = args.results_dir

    # Load all v2 metrics
    cva = _load(R / "citation_verbatim_accuracy.json")
    crs = _load(R / "citation_relevance.json")
    sf = _load(R / "semantic_faithfulness_v2.json")
    eu = _load(R / "explanation_uniqueness.json")
    lc = _load(R / "logical_consistency.json")
    gulp = _load(R / "readability_gulpease.json")
    pgf = _load(R / "pdf_gold_decision_f1.json")
    wilson = _load(R / "wilson_ci_rule_engine.json")
    retr = _load(R / "retrieval_report.json")
    pipeline = _load(R / "pipeline_report.json")
    anchors = _load(R.parent / "gold_standard" / "pdf_derived_anchors.json")

    if not all([cva, crs, eu, lc, gulp, pgf, wilson]):
        log.error("Missing one or more v2 metric files. Run cleanroom first.")
        return 1

    # Build the LaTeX section
    cva_mean = cva["aggregate"].get("mean", 0)
    crs_mean = crs["aggregate"].get("mean", 0)
    sf_ent = sf["aggregate"].get("sf_mean_entailment", 0) if sf else None
    sf_con = sf["aggregate"].get("sf_mean_contradiction", 0) if sf else None
    eu_score = eu["aggregate"].get("eu_score", 0)
    eu_dup = eu["aggregate"].get("exact_duplicate_rate", 0)
    lc_score = lc["aggregate"].get("lc_score", 0)
    gulp_norm = gulp["aggregate"].get("mean_gulpease_norm", 0)
    gulp_raw = gulp["aggregate"].get("mean_gulpease_raw", 0)
    f1 = pgf["aggregate"].get("macro_f1", 0)
    anchor_rate = pgf["anchor_coverage"].get("rate", 0)
    wilson_ci = wilson.get("pass_rate_ci", [0, 1])

    n_total = pipeline["aggregate_metrics"]["total_cases"] if pipeline else 122
    pass_rate = pipeline["aggregate_metrics"]["overall_pass_rate"] if pipeline else 0
    halluc = pipeline["aggregate_metrics"]["hallucination_rate"] if pipeline else 0

    if retr:
        rk = retr["aggregate"].get("recall_at_k", {})
        recall5 = rk.get("5", 0)
        recall10 = rk.get("10", 0)
        mrr = retr["aggregate"].get("mrr", 0)
    else:
        recall5 = recall10 = mrr = 0

    # Anchor breakdown
    if anchors:
        s = anchors.get("summary", {})
        verbatim_n = s.get("VERBATIM_FOUND", 0)
        approx_n = s.get("APPROX_FOUND", 0)
        low_n = s.get("LOW_SIM_FOUND", 0)
        weak_n = s.get("WEAK_SIM_FOUND", 0)
        fail_n = s.get("FAIL_NOT_FOUND", 0)
        n_rules = anchors.get("n_total", 44)
    else:
        verbatim_n = approx_n = low_n = weak_n = fail_n = n_rules = 0

    section_tex = rf"""

%% ============================================================
%%  AUTO-GENERATED V2 SECTION — append to cap6_risultati.tex
%%  Source: tools/update_latex_v2_numbers.py
%% ============================================================

\section{{Refactor V2: citazioni granulari e metriche non-tautologiche}}
\label{{sec:v2_refactor}}

Il refactor V2 introduce due cambiamenti metodologici fondamentali rispetto
alla valutazione V3.4:

\begin{{enumerate}}
  \item \textbf{{Citazioni granulari verbatim.}} Ogni regola e ogni evidenza
    riportata dall'LLM include posizione testuale precisa nel PDF
    (\texttt{{(pdf, page, righe N–M, char A–B)}}) con SHA256 del chunk e
    flag \emph{{Verificato}} che attesta la presenza letterale del testo
    nel PDF a quella posizione. Lo strumento \texttt{{tools/derive\_gold\_from\_pdf.py}}
    ricostruisce automaticamente il \emph{{gold}} dal PDF, sostituendo il gold
    autore-scritto della V3.4.
  \item \textbf{{Sette metriche genuinamente non-tautologiche.}} La V3.4 era
    affetta da metriche tautologiche (citation\_coverage~=~1.0 perché la
    sezione FONTI è composta deterministicamente; pass\_rate~=~1.0 perché il
    gold era generato dal codice stesso). La V2 introduce M1..M7 confrontate
    contro il PDF o un gold derivato dal PDF, separando esplicitamente i
    valori \emph{{by-construction}} come ``integrity asserts''.
\end{{enumerate}}

\subsection{{Audit fedeltà PDF$\to$YAML aggiornato}}

Riapplicato l'audit V2 sulle 44 regole, con dehyphenation aggressiva e
NFKC normalization:

\begin{{table}}[H]
  \centering
  \caption{{Risultati audit fedeltà V2 (sostituzione di excerpt YAML con verbatim PDF dove possibile)}}
  \label{{tab:audit_v2}}
  \begin{{tabular}}{{lc}}
    \toprule
    \textbf{{Stato}} & \textbf{{Regole}} \\
    \midrule
    VERBATIM\_FOUND  & {verbatim_n} \\
    APPROX\_FOUND    & {approx_n} \\
    LOW\_SIM\_FOUND  & {low_n} \\
    WEAK\_SIM\_FOUND & {weak_n} \\
    FAIL\_NOT\_FOUND & {fail_n} \\
    \midrule
    \textbf{{Totale}} & \textbf{{{n_rules}}} \\
    \bottomrule
  \end{{tabular}}
\end{{table}}

\subsection{{Le sette metriche genuine}}

\begin{{table}}[H]
  \centering
  \caption{{Metriche non-tautologiche V2 (n={n_total} casi)}}
  \label{{tab:metriche_v2}}
  \small
  \begin{{tabular}}{{clcc}}
    \toprule
    \textbf{{ID}} & \textbf{{Metrica}} & \textbf{{Valore}} & \textbf{{Range}} \\
    \midrule
    M7 & PDF-gold Decision Macro F1 & {_fmt(f1)} & [0,1] \\
    M1 & Citation Verbatim Accuracy (CVA) & {_fmt(cva_mean)} & [0,1] \\
    M2 & Citation Relevance Score (CRS) & {_fmt(crs_mean)} & [0,1] \\
    M3 & Semantic Faithfulness (NLI it.) & {_fmt(sf_ent) if sf_ent is not None else 'n/a'} & [0,1] \\
    M4 & Explanation Uniqueness (EU) & {_fmt(eu_score)} & [0,1] \\
    M5 & Logical Consistency (LC) & {_fmt(lc_score)} & [0,1] \\
    M6 & Readability (Gulpease norm) & {_fmt(gulp_norm)} & [0,1] \\
    \bottomrule
  \end{{tabular}}
\end{{table}}

\noindent\textbf{{Anchor coverage:}} {_fmt(anchor_rate, "{:.1%}")} delle blocking rules
hanno \texttt{{excerpt\_pdf\_verbatim}} estratto dal PDF (status APPROX o
superiore).

\subsection{{Wilson 95\% CI (non degenerate)}}

A differenza dell'intervallo bootstrap normal-percentile (degenere a
$[1.0, 1.0]$ quando $\hat{{p}}=1.0$), il Wilson score interval è
non-degenerate ai confini:

\noindent Pass rate rule engine = {_fmt(pass_rate)}, Wilson 95\% CI =
$[{_fmt(wilson_ci[0])},\ {_fmt(wilson_ci[1])}]$.

\subsection{{Asserts di integrità (NON metriche)}}

I seguenti valori sono garantiti per costruzione e \textbf{{non}} costituiscono
metriche di qualità:

\begin{{itemize}}
  \item \texttt{{decision\_injection\_integrity\_assert}} = 1.0
    (la decisione del rule engine è inserita nella sezione~1 dell'output LLM).
  \item \texttt{{fonti\_section\_completeness\_byconstruction}} = 1.0
    (la sezione FONTI è ricomposta deterministicamente).
  \item \texttt{{section\_completeness}} = 1.0 (template del prompt enforced).
  \item \texttt{{rule\_engine\_self\_consistency}} = 1.0
    (sostituito da M7 per validità rispetto al PDF).
\end{{itemize}}

\subsection{{Patologie identificate dalle metriche}}

Le metriche M4 e M5 hanno reso visibili patologie precedentemente nascoste:

\begin{{itemize}}
  \item \textbf{{M4 — Output duplicati:}} il {_fmt(eu_dup, "{:.1%}")} dei casi
    condividono una spiegazione bytewise-identica con almeno un altro caso
    (l'LLM produce testo generico per categorie cliniche distinte).
  \item \textbf{{M5 — Errori logici latenti:}} {_fmt(1-lc_score, "{:.1%}")} dei
    casi contengono affermazioni numericamente contraddittorie del tipo
    ``[X,Y] inferiore alla soglia di Z'' con $X \geq Z$ — non rilevate dal
    detector di hallucination lessicale.
  \item \textbf{{M6 — Leggibilità:}} indice Gulpease medio = {_fmt(gulp_raw, "{:.2f}")}
    (bucket \emph{{scuola superiore}}), atteso per testo medico-normativo.
\end{{itemize}}

\subsection{{Retrieval (Track 2)}}

Recall@5 = {_fmt(recall5)}, Recall@10 = {_fmt(recall10)}, MRR = {_fmt(mrr)}.
Cross-encoder italiano (\texttt{{nickprock/cross-encoder-italian-bert-stsb}})
sostituisce il precedente MS-MARCO inglese, eliminando il mismatch di dominio
documentato nell'audit V3.4.

%% END auto-generated V2 section
"""

    out_path = args.latex_dir / "cap6_v2_appendix.tex"
    if args.apply:
        out_path.write_text(section_tex)
        log.info(f"Wrote V2 section to {out_path}")
        log.info("Add to tesi.tex: \\input{chapters/cap6_v2_appendix}")
        # Also update the main cap6 to include it (idempotent)
        main_cap6 = args.latex_dir / "cap6_risultati.tex"
        if main_cap6.exists():
            content = main_cap6.read_text()
            if "cap6_v2_appendix" not in content:
                # Append \input directive at the end
                content_lines = content.rstrip().split("\n")
                # Insert before any final % comment markers
                content_lines.append("")
                content_lines.append("%% V2 refactor — auto-generated section")
                content_lines.append("\\input{chapters/cap6_v2_appendix}")
                main_cap6.write_text("\n".join(content_lines) + "\n")
                log.info(f"Patched {main_cap6} to include V2 appendix")
    else:
        log.info("DRY-RUN: would write V2 LaTeX section")
        log.info(f"Output preview (first 30 lines):")
        for line in section_tex.split("\n")[:30]:
            log.info(f"  {line}")
        log.info("...")
        log.info("Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
