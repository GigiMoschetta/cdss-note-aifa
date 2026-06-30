"""
Generate per-case verifiable artifacts.

For every gold case, writes two files under
`evaluation/results/per_case_reports/N{NN}/{case_id}.{md,json}`:

  - .md   human-readable report (input, gold from PDF, engine output,
            retrieved chunks with verbatim text, full LLM explanation,
            validation flags, per-case metric scores)
  - .json machine-readable consolidated record (same content, structured)

Plus an INDEX.md table at the top with a one-line summary per case so the
user can scan / filter / link to any case.

Inputs:
  --pipeline-report     pipeline_report.json (Track 3 output)
  --explanations-dir    pipeline_explanations/ (saved with --save-explanations)
  --rule-engine-report  rule_engine_report.json (Track 1 output)
  --retrieval-report    retrieval_report.json (Track 2 output)
  --excerpt-match       excerpt_match.json (deterministic excerpt metric)
  --ragas-report        ragas_report.json (RAGAS metrics; optional)
  --gold-dir            evaluation/gold_standard/
  --output-dir          evaluation/results/per_case_reports/

Usage:
  python -m evaluation.scripts.per_case_report \\
      --pipeline-report  evaluation/results/pipeline_report.json \\
      --explanations-dir evaluation/results/pipeline_explanations \\
      --rule-engine-report evaluation/results/rule_engine_report.json \\
      --retrieval-report evaluation/results/retrieval_report.json \\
      --excerpt-match    evaluation/results/excerpt_match.json \\
      --ragas-report     evaluation/results/ragas_report.json \\
      --gold-dir         evaluation/gold_standard \\
      --output-dir       evaluation/results/per_case_reports
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _index_by_case(report: dict, key: str = "case_id") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in report.get("case_results", []) or report.get("results", []) or report.get("per_case", []):
        cid = r.get(key) or r.get("case_id")
        if cid:
            out[cid] = r
    return out


def _load_gold_index(gold_dir: Path) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for nota in ("01", "13", "66", "97"):
        f = gold_dir / f"nota_{nota}_cases.json"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fp:
            for c in json.load(fp).get("cases", []):
                idx[c["id"]] = c
    return idx


def _load_chroma_text(case_chunks: list[dict]) -> dict[str, str]:
    if not case_chunks:
        return {}
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError:
        return {}

    db_path = _PROJECT_ROOT / "rag_pipeline" / "chroma_db"
    client = chromadb.PersistentClient(path=str(db_path))
    emb = SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-mpnet-base-v2")

    by_nota: dict[str, list[str]] = {}
    for c in case_chunks:
        cid = c.get("chunk_id", "")
        if not cid:
            continue
        pdf = c.get("pdf_file", "")
        if "97" in pdf:
            nid = "97"
        elif "13" in pdf:
            nid = "13"
        elif "66" in pdf:
            nid = "66"
        elif "01" in pdf or "Nota_01" in pdf:
            nid = "01"
        else:
            continue
        by_nota.setdefault(nid, []).append(cid)

    out: dict[str, str] = {}
    for nid, ids in by_nota.items():
        try:
            col = client.get_collection(name=f"nota_{nid}", embedding_function=emb)
            res = col.get(ids=ids, include=["documents"])
            for cid, doc in zip(res.get("ids", []), res.get("documents", []) or []):
                out[cid] = doc or ""
        except Exception:
            continue
    return out


def _truncate(text: str, n: int = 600) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[:n].rstrip() + " […]"


def _md_table_row(items: list[str]) -> str:
    return "| " + " | ".join(str(x) for x in items) + " |"


def _build_case_record(
    cid: str,
    gold: dict,
    rule_eng: dict,
    pipeline: dict,
    explanation: str,
    retrieval: dict,
    excerpt: dict,
    ragas: dict,
    chunk_texts: dict[str, str],
) -> dict:
    inp = gold.get("input", {})
    pdf_ref = gold.get("pdf_reference", {}) or {}
    expected = gold.get("expected_rule_engine", {})
    crit = gold.get("explanation_criteria", {})

    rule_chk = (rule_eng or {}).get("checks", {})
    pip_details = (pipeline or {}).get("details", {}) or {}
    chunks = (pipeline or {}).get("retrieved_chunks_metadata", [])

    return {
        "case_id": cid,
        "nota_id": inp.get("nota_id"),
        "drug_id": inp.get("drug_id"),
        "category": gold.get("category"),
        "description": gold.get("description"),
        "tags": gold.get("tags", []),

        "input": {
            "patient_data": inp.get("patient_data", {}),
            "clinician_asserted": inp.get("clinician_asserted", {}),
        },

        "gold": {
            "expected_decision": expected.get("reimbursement_decision"),
            "expected_decision_status": expected.get("decision_status"),
            "expected_blocking_rule_ids": expected.get("expected_blocking_rule_ids", []),
            "expected_clinical_flag_rule_ids": expected.get("expected_clinical_flag_rule_ids", []),
            "missing_fields_coverage": expected.get("missing_fields_coverage", []),
            "explanation_criteria": crit,
            "pdf_reference": pdf_ref,
        },

        "engine": {
            "actual_decision": rule_chk.get("reimbursement_decision", {}).get("actual"),
            "actual_decision_status": rule_chk.get("decision_status", {}).get("actual"),
            "rule_check_pass": (rule_eng or {}).get("pass"),
            "actual_blocking_rule_ids": rule_chk.get("blocking_rule_ids", {}).get("actual"),
            "actual_clinical_flag_rule_ids": rule_chk.get("clinical_flag_rule_ids", {}).get("actual"),
        },

        "retrieval": {
            "recall_at_3": (retrieval or {}).get("recall_at_3"),
            "recall_at_5": (retrieval or {}).get("recall_at_5"),
            "recall_at_10": (retrieval or {}).get("recall_at_10"),
            "mrr": (retrieval or {}).get("mrr"),
            "anchors_expected": (retrieval or {}).get("anchors", []),
            "chunks": [
                {
                    "rank": idx + 1,
                    "chunk_id": c.get("chunk_id"),
                    "pdf_file": c.get("pdf_file"),
                    "page": c.get("page"),
                    "section": c.get("section"),
                    "stage": c.get("retrieval_stage"),
                    "score": c.get("score"),
                    "text": chunk_texts.get(c.get("chunk_id"), ""),
                }
                for idx, c in enumerate(chunks)
            ],
        },

        "llm": {
            "explanation": explanation,
            "validation": {
                "decision_consistent": pip_details.get("decision_consistent"),
                "decision_contradicted": pip_details.get("decision_contradicted"),
                "missing_citations": pip_details.get("missing_citations", []),
                "suspected_hallucinations": pip_details.get("suspected_hallucinations", []),
                "missing_sections": pip_details.get("missing_sections", []),
                "string_checks": pip_details.get("string_checks", {}),
                "missing_justification_rules": pip_details.get("missing_justification_rules", []),
            },
            "decision_consistent": (pipeline or {}).get("decision_consistent"),
            "citation_complete": (pipeline or {}).get("citation_complete"),
            "sections_complete": (pipeline or {}).get("sections_complete"),
            "strings_ok": (pipeline or {}).get("strings_ok"),
            "has_hallucination": (pipeline or {}).get("has_hallucination"),
            "overall_pass": (pipeline or {}).get("overall_pass"),
            "token_usage": (pipeline or {}).get("token_usage", {}),
            "latency_s": (pipeline or {}).get("latency_s"),
        },

        "metrics": {
            "excerpt_match": excerpt or {},
            "ragas": ragas or {},
        },
    }


def _render_markdown(rec: dict) -> str:
    cid = rec["case_id"]
    g = rec["gold"]
    e = rec["engine"]
    r = rec["retrieval"]
    l = rec["llm"]
    m = rec["metrics"]
    pdf_ref = g.get("pdf_reference", {}) or {}

    pass_engine = "✅" if e.get("rule_check_pass") else "❌"
    pass_llm = "✅" if l.get("overall_pass") else "❌"

    s = []
    s.append(f"# {cid} — {rec.get('category', '?')}")
    s.append("")
    s.append(f"**Nota AIFA:** {rec.get('nota_id')} **Farmaco:** `{rec.get('drug_id')}`  "
             f"**Tags:** {', '.join(rec.get('tags', []))}")
    s.append("")
    s.append(f"**Description:** {rec.get('description')}")
    s.append("")
    s.append("---")

    # Quick verdict box
    s.append("\n## Verdetto sintetico")
    s.append("")
    s.append("| Layer | Atteso | Prodotto | Esito |")
    s.append("|---|---|---|---|")
    s.append(_md_table_row([
        "Rule engine",
        g.get("expected_decision") or "?",
        e.get("actual_decision") or "?",
        pass_engine,
    ]))
    s.append(_md_table_row([
        "LLM explanation",
        "5 sez., decisione coerente, citazioni complete",
        f"dec.coerente={l.get('decision_consistent')} cit.compl={l.get('citation_complete')} sez.={l.get('sections_complete')}",
        pass_llm,
    ]))

    em = m.get("excerpt_match") or {}
    if em:
        s.append(_md_table_row([
            "Excerpt match (PDF→LLM)",
            f"verbatim coverage ≥0,8 (PDF p.{pdf_ref.get('page')})",
            f"cov_LLM={em.get('excerpt_coverage_llm')} cov_RET={em.get('excerpt_coverage_retrieval')}",
            "✅" if em.get("excerpt_in_llm") or em.get("excerpt_in_retrieval") else "❌",
        ]))
    rg = m.get("ragas") or {}
    if rg:
        scores = {k: v for k, v in rg.items() if k != "case_id"}
        s.append(_md_table_row([
            "RAGAS",
            "alti = ottimo (~1,0)",
            ", ".join(f"{k}={v:.2f}" for k, v in scores.items() if v is not None),
            "—",
        ]))

    # Patient input
    s.append("\n## 1. Input paziente")
    s.append("")
    s.append("```json")
    s.append(json.dumps(rec.get("input", {}), indent=2, ensure_ascii=False))
    s.append("```")

    # Gold from PDF
    s.append("\n## 2. Gold standard (derivato dal PDF AIFA)")
    s.append("")
    s.append(f"- **Decisione attesa:** `{g.get('expected_decision')}` "
             f"(stato: `{g.get('expected_decision_status')}`)")
    s.append(f"- **Regole bloccanti attese:** "
             f"{g.get('expected_blocking_rule_ids') or '— (nessuna)'}")
    s.append(f"- **Flag clinici attesi:** "
             f"{g.get('expected_clinical_flag_rule_ids') or '— (nessuno)'}")
    s.append(f"- **Dati mancanti attesi:** "
             f"{g.get('missing_fields_coverage') or '— (nessuno)'}")

    crit = g.get("explanation_criteria", {})
    if crit:
        s.append("")
        s.append("**Criteri spiegazione (gold):**")
        if crit.get("must_contain_strings"):
            s.append(f"- deve contenere: {crit['must_contain_strings']}")
        if crit.get("must_not_contain_strings"):
            s.append(f"- NON deve contenere: {crit['must_not_contain_strings']}")
        if crit.get("expected_citation_count_min") is not None:
            s.append(f"- citazioni min: {crit['expected_citation_count_min']}")
        if crit.get("notes"):
            s.append(f"- note: {crit['notes']}")

    s.append("")
    s.append("**PDF reference (verbatim dal PDF):**")
    s.append("")
    s.append(f"- file: `{pdf_ref.get('pdf_file')}`  pagina: **{pdf_ref.get('page')}**  "
             f"sezione: *{pdf_ref.get('section')}*  rule_id: `{pdf_ref.get('rule_id')}`")
    s.append("")
    s.append("> " + (pdf_ref.get("excerpt") or "—").replace("\n", "\n> "))

    # Engine output
    s.append("\n## 3. Output del rule engine (deterministico)")
    s.append("")
    s.append(f"- **Decisione prodotta:** `{e.get('actual_decision')}` "
             f"(stato: `{e.get('actual_decision_status')}`)")
    s.append(f"- **Blocking rule_id:** {e.get('actual_blocking_rule_ids') or '—'}")
    s.append(f"- **Flag clinici:** {e.get('actual_clinical_flag_rule_ids') or '—'}")

    # Retrieval
    s.append("\n## 4. Retrieval (chunk PDF recuperati da ChromaDB)")
    s.append("")
    chunks = r.get("chunks", []) or []
    if r.get("recall_at_5") is not None:
        s.append(f"_Recall@5={r.get('recall_at_5')}, MRR={r.get('mrr')}_")
        s.append("")
    if not chunks:
        s.append("_(nessun chunk recuperato)_")
    else:
        for c in chunks:
            mark = "🅰" if (c.get("stage") or "").startswith("anchor") else "🅱"
            s.append(f"### Chunk #{c['rank']} {mark} {c.get('stage')}")
            s.append(f"- file: `{c.get('pdf_file')}`  p.{c.get('page')}  "
                     f"sezione: *{c.get('section')}*  score: {c.get('score'):.3f}"
                     if c.get("score") is not None
                     else f"- file: `{c.get('pdf_file')}`  p.{c.get('page')}  "
                          f"sezione: *{c.get('section')}*")
            s.append(f"- chunk_id: `{c.get('chunk_id')}`")
            s.append("")
            s.append("> " + _truncate(c.get("text", ""), 500).replace("\n", "\n> "))
            s.append("")

    # LLM explanation
    s.append("## 5. Spiegazione generata dall'LLM (Llama 3.1 8B)")
    s.append("")
    s.append(f"_token: prompt={l.get('token_usage', {}).get('prompt_tokens')}, "
             f"completion={l.get('token_usage', {}).get('completion_tokens')}, "
             f"latenza={l.get('latency_s')}s_")
    s.append("")
    s.append("```")
    s.append((l.get("explanation") or "_(non salvata — esegui pipeline con --save-explanations)_").rstrip())
    s.append("```")

    # Validation
    val = l.get("validation", {})
    s.append("\n## 6. Validation flags (deterministici, post-LLM)")
    s.append("")
    s.append("| Flag | Valore |")
    s.append("|---|---|")
    s.append(f"| decision_consistent | {val.get('decision_consistent')} |")
    s.append(f"| decision_contradicted | {val.get('decision_contradicted')} |")
    s.append(f"| missing_citations | {val.get('missing_citations') or '—'} |")
    s.append(f"| suspected_hallucinations | {val.get('suspected_hallucinations') or '—'} |")
    s.append(f"| missing_sections | {val.get('missing_sections') or '—'} |")
    s.append(f"| missing_justification_rules | {val.get('missing_justification_rules') or '—'} |")
    if val.get("string_checks"):
        s.append("")
        s.append("**String checks (gold criteria):**")
        for k, v in val["string_checks"].items():
            s.append(f"- {'✅' if v else '❌'} {k}")

    # Per-case metrics
    s.append("\n## 7. Metriche per-caso")
    s.append("")
    if em:
        s.append("**Excerpt match (deterministica, PDF↔LLM):**")
        s.append(f"- excerpt_in_llm: {em.get('excerpt_in_llm')}  (3-gram coverage: {em.get('excerpt_coverage_llm')})")
        s.append(f"- excerpt_in_retrieval: {em.get('excerpt_in_retrieval')}  (cov: {em.get('excerpt_coverage_retrieval')})")
        s.append(f"- gold_anchor_in_top_3: {em.get('gold_anchor_in_top_3')}, "
                 f"top_5: {em.get('gold_anchor_in_top_5')}, "
                 f"top_10: {em.get('gold_anchor_in_top_10')}")
        s.append("")

    if rg:
        s.append("**RAGAS (judge: Llama 3.1 8B):**")
        for k, v in rg.items():
            if k == "case_id":
                continue
            s.append(f"- {k}: {v}")

    return "\n".join(s) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--rule-engine-report", required=True)
    p.add_argument("--retrieval-report", default=None)
    p.add_argument("--excerpt-match", default=None)
    p.add_argument("--ragas-report", default=None)
    p.add_argument("--gold-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    pipeline = _load_json(args.pipeline_report)
    rule_eng = _load_json(args.rule_engine_report)
    retrieval = _load_json(args.retrieval_report)
    excerpt = _load_json(args.excerpt_match)
    ragas = _load_json(args.ragas_report)
    gold_idx = _load_gold_index(Path(args.gold_dir))

    pipeline_idx = _index_by_case(pipeline)
    rule_eng_idx = {r["case_id"]: r for r in rule_eng.get("results", [])}
    retrieval_idx = {
        r["case_id"]: r
        for r in (retrieval.get("case_results") or retrieval.get("per_case") or [])
    }
    excerpt_idx = {r["case_id"]: r for r in (excerpt.get("per_case") or [])}
    ragas_idx = {r["case_id"]: r for r in (ragas.get("per_case") or [])}
    if not retrieval_idx and retrieval:
        print("[per_case_report] WARN: retrieval_idx empty (check key 'case_results')", file=sys.stderr)

    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    expl_dir = Path(args.explanations_dir)
    index_rows: list[tuple] = []
    n_written = 0

    for cid, gold in sorted(gold_idx.items()):
        nota = gold.get("input", {}).get("nota_id", "?")
        nota_dir = out_root / f"N{nota}"
        nota_dir.mkdir(exist_ok=True)

        explanation_file = expl_dir / f"{cid}.txt"
        explanation = explanation_file.read_text(encoding="utf-8") if explanation_file.exists() else ""

        pip = pipeline_idx.get(cid, {})
        chunks = pip.get("retrieved_chunks_metadata", [])
        chunk_texts = _load_chroma_text(chunks)

        rec = _build_case_record(
            cid=cid,
            gold=gold,
            rule_eng=rule_eng_idx.get(cid, {}),
            pipeline=pip,
            explanation=explanation,
            retrieval=retrieval_idx.get(cid, {}),
            excerpt=excerpt_idx.get(cid, {}),
            ragas=ragas_idx.get(cid, {}),
            chunk_texts=chunk_texts,
        )

        # Write JSON
        with open(nota_dir / f"{cid}.json", "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        # Write Markdown
        with open(nota_dir / f"{cid}.md", "w", encoding="utf-8") as f:
            f.write(_render_markdown(rec))

        em = rec.get("metrics", {}).get("excerpt_match", {}) or {}
        rg = rec.get("metrics", {}).get("ragas", {}) or {}
        index_rows.append(
            (
                cid,
                nota,
                rec["gold"].get("expected_decision"),
                rec["engine"].get("actual_decision"),
                "✅" if rec["engine"].get("rule_check_pass") else "❌",
                "✅" if rec["llm"].get("overall_pass") else "❌",
                em.get("excerpt_coverage_llm"),
                rg.get("faithfulness"),
                rg.get("answer_correctness"),
                f"N{nota}/{cid}.md",
            )
        )
        n_written += 1

    # Index
    idx_lines = ["# Per-case verifiable reports — Index", ""]
    idx_lines.append(f"_Generated for {n_written} cases. Each case has both a markdown summary "
                     "and a JSON record with full input, gold from PDF, engine output, retrieved chunks "
                     "with verbatim text, full LLM explanation, validation flags, and per-case metric scores._")
    idx_lines.append("")
    idx_lines.append("| case_id | Nota | gold | engine | engine_pass | LLM_pass | exc_cov_LLM | RAGAS_faith | RAGAS_corr | link |")
    idx_lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in index_rows:
        cid, nota, gold_dec, eng_dec, eng_p, llm_p, cov, faith, corr, link = row
        idx_lines.append(
            f"| {cid} | {nota} | {gold_dec or '—'} | {eng_dec or '—'} | "
            f"{eng_p} | {llm_p} | "
            f"{cov if cov is not None else '—'} | "
            f"{f'{faith:.3f}' if isinstance(faith, (int, float)) else '—'} | "
            f"{f'{corr:.3f}' if isinstance(corr, (int, float)) else '—'} | "
            f"[{cid}]({link}) |"
        )
    with open(out_root / "INDEX.md", "w", encoding="utf-8") as f:
        f.write("\n".join(idx_lines) + "\n")

    print(f"Wrote {n_written} per-case reports to {out_root}/")
    print(f"Index: {out_root}/INDEX.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
