"""
QAEval (Malasi 4.2.2): F1 of micro-questions extracted from gold_answer
                       (Recall) and from model answer (Precision).

Process:
  1. Extract micro-questions from gold_answer  →  gold_qs  (max_qs each)
  2. For each gold_q, judge YES/NO whether model_answer contains the answer
     →  Recall = N_yes / N_gold_qs
  3. Extract micro-questions from model answer →  rag_qs
  4. For each rag_q, judge YES/NO whether gold_answer contains the answer
     →  Precision = N_yes / N_rag_qs
  5. F1 = 2 P R / (P + R)

The judge LLM is the same Llama 3.1 8B used by the pipeline (declared as a
known limitation: same-family judge). Temperature 0 for determinism.

For thesis credibility we report (Malasi-style):
  - per-case Recall, Precision, F1
  - the raw lists of gold_qs and rag_qs
  - the YES/NO verdict for each micro-question (auditable artifact)

Output:
  evaluation/results/qaeval.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from statistics import mean


_PROJECT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_MODEL = "llama3.1:8b"
_DEFAULT_BASE = "http://localhost:11434"
_MAX_QS = 8


# ── LLM client (Ollama) ────────────────────────────────────────────────────────

def _chat(model: str, base_url: str, messages: list[dict], timeout: int = 120) -> str:
    import httpx
    payload = {
        "model": model,
        "messages": messages,
        "options": {"temperature": 0, "num_ctx": 8192},
        "stream": False,
    }
    r = httpx.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("message") or {}).get("content", "")


# ── Prompts (italianized) ─────────────────────────────────────────────────────

_EXTRACT_PROMPT = """Sei un valutatore esperto. Estrai dal seguente testo le {max_qs} affermazioni fattuali principali.
Per ogni affermazione, riformulala come una domanda chiusa (risposta sì/no o risposta breve fattuale).
Rispondi ESCLUSIVAMENTE in JSON, formato:
{{"questions": ["...", "...", ...]}}

TESTO:
\"\"\"
{text}
\"\"\""""

_JUDGE_PROMPT = """Sei un valutatore esperto. Devi decidere se il seguente TESTO contiene la risposta corretta alla DOMANDA.
Rispondi ESCLUSIVAMENTE in JSON, formato:
{{"verdict": "YES" | "NO", "reason": "breve motivazione"}}

DOMANDA: {question}

TESTO:
\"\"\"
{text}
\"\"\""""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_json(s: str) -> dict | None:
    """Robust JSON extraction from LLM output (handles wrapping/prefix junk)."""
    s = s.strip()
    # Direct parse
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Find {...} substring
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _extract_micro_questions(text: str, model: str, base_url: str, max_qs: int = _MAX_QS) -> list[str]:
    prompt = _EXTRACT_PROMPT.format(text=text[:1500], max_qs=max_qs)
    out = _chat(model, base_url, [{"role": "user", "content": prompt}])
    parsed = _safe_json(out)
    if not parsed or "questions" not in parsed:
        return []
    qs = parsed.get("questions", [])
    return [str(q).strip() for q in qs if str(q).strip()][:max_qs]


def _judge_question(question: str, text: str, model: str, base_url: str) -> dict:
    prompt = _JUDGE_PROMPT.format(question=question, text=text[:2000])
    out = _chat(model, base_url, [{"role": "user", "content": prompt}])
    parsed = _safe_json(out) or {}
    verdict = (parsed.get("verdict") or "").strip().upper()
    if verdict not in ("YES", "NO"):
        # heuristic fallback
        verdict = "YES" if re.search(r"\b(yes|sì|si\b|true|vero)\b", out, re.IGNORECASE) else "NO"
    return {"verdict": verdict, "reason": parsed.get("reason", "")[:200]}


# ── Per-case ──────────────────────────────────────────────────────────────────

def _evaluate_case(
    case_id: str,
    gold_answer: str,
    model_answer: str,
    judge_model: str,
    base_url: str,
    max_qs: int,
) -> dict:
    if not gold_answer or not model_answer:
        return {"case_id": case_id, "skip_reason": "missing inputs"}

    # Step 1: gold_qs
    gold_qs = _extract_micro_questions(gold_answer, judge_model, base_url, max_qs)
    if not gold_qs:
        return {"case_id": case_id, "skip_reason": "no_gold_qs_extracted"}

    # Step 2: recall
    recall_verdicts = []
    for q in gold_qs:
        v = _judge_question(q, model_answer, judge_model, base_url)
        recall_verdicts.append({"question": q, **v})
    n_recall_yes = sum(1 for v in recall_verdicts if v["verdict"] == "YES")
    recall = n_recall_yes / len(gold_qs)

    # Step 3: rag_qs
    rag_qs = _extract_micro_questions(model_answer, judge_model, base_url, max_qs)
    precision_verdicts: list[dict] = []
    if rag_qs:
        # Step 4: precision
        for q in rag_qs:
            v = _judge_question(q, gold_answer, judge_model, base_url)
            precision_verdicts.append({"question": q, **v})
    n_prec_yes = sum(1 for v in precision_verdicts if v["verdict"] == "YES")
    precision = n_prec_yes / len(rag_qs) if rag_qs else 0.0

    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "case_id": case_id,
        "n_gold_qs": len(gold_qs),
        "n_rag_qs": len(rag_qs),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "gold_qs": gold_qs,
        "rag_qs": rag_qs,
        "recall_verdicts": recall_verdicts,
        "precision_verdicts": precision_verdicts,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pipeline-report", required=True)
    p.add_argument("--explanations-dir", required=True)
    p.add_argument("--gold-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--judge-model", default=os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL))
    p.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE))
    p.add_argument("--max-qs", type=int, default=_MAX_QS)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--resume", action="store_true", help="skip cases already in output")
    args = p.parse_args()

    with open(args.pipeline_report, encoding="utf-8") as f:
        report = json.load(f)
    case_results = report.get("case_results", [])
    if args.limit:
        case_results = case_results[:args.limit]

    expl_dir = Path(args.explanations_dir)
    gold_idx = _load_gold_index(Path(args.gold_dir))

    # Resume support
    existing: dict[str, dict] = {}
    out_path = Path(args.output)
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            prev = json.load(f)
        for r in prev.get("per_case", []):
            existing[r["case_id"]] = r
        print(f"[resume] {len(existing)} cases already done", file=sys.stderr)

    per_case: list[dict] = list(existing.values())
    t0 = time.monotonic()
    for cr in case_results:
        cid = cr.get("case_id", "?")
        if cid in existing:
            continue
        gold = gold_idx.get(cid, {})
        gold_answer = gold.get("gold_answer", "")
        expl_file = expl_dir / f"{cid}.txt"
        model_answer = expl_file.read_text(encoding="utf-8") if expl_file.exists() else ""

        try:
            result = _evaluate_case(
                cid, gold_answer, model_answer,
                args.judge_model, args.ollama_base_url, args.max_qs,
            )
        except Exception as exc:
            print(f"  ERROR {cid}: {exc}", file=sys.stderr)
            result = {"case_id": cid, "skip_reason": f"error: {exc}"}
        per_case.append(result)
        # Periodic checkpoint write so resume works
        if len(per_case) % 5 == 0:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"metric": "qaeval", "judge_model": args.judge_model,
                           "per_case": per_case, "_in_progress": True}, f, indent=2, ensure_ascii=False)
        sys.stderr.write(".")
        sys.stderr.flush()
    sys.stderr.write("\n")

    elapsed = time.monotonic() - t0
    valid = [r for r in per_case if "skip_reason" not in r]
    aggregate = {"n_cases_evaluated": len(valid)}
    if valid:
        aggregate.update({
            "mean_recall": round(mean(r["recall"] for r in valid), 4),
            "mean_precision": round(mean(r["precision"] for r in valid), 4),
            "mean_f1": round(mean(r["f1"] for r in valid), 4),
            "median_f1": round(sorted(r["f1"] for r in valid)[len(valid)//2], 4),
        })

    out = {
        "metric": "qaeval",
        "judge_model": args.judge_model,
        "max_qs": args.max_qs,
        "wall_time_s": round(elapsed, 1),
        "aggregate": aggregate,
        "per_case": per_case,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"QAEval — {len(valid)} cases (judge: {args.judge_model})")
    print("=" * 60)
    for k, v in aggregate.items():
        print(f"  {k:30s} {v}")
    print(f"\nReport: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
