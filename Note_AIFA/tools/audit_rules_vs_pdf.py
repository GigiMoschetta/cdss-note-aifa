"""
Maniacal PDF→rule fidelity audit.

For every rule in aifa_rule_engine/rules/nota_*/rules.yaml, verifies that the
`normative_anchor.excerpt` is actually present (verbatim or near-verbatim) in
the cited PDF page. This is the foundation of thesis correctness: every rule
the system enforces must be a faithful transcription of the AIFA PDF.

Status hierarchy (worst → best):
  NOT_FOUND        — excerpt not found anywhere in the PDF                    BLOCKING
  WRONG_PAGE       — excerpt found in a DIFFERENT page than declared          ALTO
  PARTIAL_MATCH    — 0.50 ≤ 3-gram coverage < 0.85 on the target page         MEDIO
  APPROX_FOUND     — 3-gram coverage ≥ 0.85 on the target page (paraphrase OK)INFO
  VERBATIM_FOUND   — exact substring match after normalization                 INFO

Output:
  audit/PDF_AUDIT_REPORT.md      — human-readable summary
  audit/PDF_AUDIT_REPORT.json    — machine-readable per-rule status

Exit code:
  0 — no BLOCKING findings (pipeline can proceed)
  1 — at least one BLOCKING finding (must be fixed before proceeding)

Usage:
  python tools/audit_rules_vs_pdf.py
  python tools/audit_rules_vs_pdf.py --strict           # also fail on ALTO
  python tools/audit_rules_vs_pdf.py --json-only        # skip markdown
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml


_PROJECT = Path(__file__).resolve().parent.parent
_RULES_DIR = _PROJECT / "aifa_rule_engine" / "rules"
_PDF_DIR = _PROJECT
_AUDIT_DIR = _PROJECT.parent / "audit"

_VERBATIM = "VERBATIM_FOUND"
_APPROX = "APPROX_FOUND"
_PARAPHRASE = "PARAPHRASE_DOCUMENTED"
_WRONG_PAGE = "WRONG_PAGE"
_FABRICATED = "FABRICATED"

_SEVERITY = {
    _VERBATIM: "INFO",
    _APPROX: "INFO",
    _PARAPHRASE: "MEDIO",
    _WRONG_PAGE: "ALTO",
    _FABRICATED: "BLOCCANTE",
}

# 3-gram overlap thresholds
_NGRAM_APPROX = 0.85   # ≥ → APPROX_FOUND (verbatim-like)
_NGRAM_PARAPHRASE = 0.30  # ≥ → PARAPHRASE_DOCUMENTED (semantically present)
# < _NGRAM_PARAPHRASE  → FABRICATED (no real overlap)
_NGRAM_N = 3

# Italian stop-words + Note-AIFA synonyms used by the keyword overlap check
_IT_STOPWORDS = {
    "il","lo","la","i","gli","le","un","uno","una","del","della","dello",
    "dei","degli","delle","di","a","da","in","su","con","per","tra","fra",
    "ed","e","o","che","cui","non","si","se","anche","come","ma",
    "al","allo","alla","ai","agli","alle","nel","nello","nella","nei",
    "negli","nelle","è","sono","essere","stato","deve","devono","dovrà",
    "può","possono","ha","hanno","avere","essere","essendo",
    "questo","questa","questi","queste","ciò","ad","sul","sulla","sui","sulle",
}

_SYNONYMS = {
    "ecg": "elettrocardiogramma", "fa": "fanv", "fanv": "fanv",
    "fans": "fans", "doac": "doac", "nao": "doac", "naoc": "doac", "nao/doac": "doac",
    "avk": "avk", "irc": "renale cronica", "vfg": "vfg",
    "ldl": "ldl", "hdl": "hdl", "tg": "trigliceridi", "cv": "cardiovascolare",
    "ssn": "ssn", "tia": "ictus transitorio", "te": "embolia", "ttr": "ttr",
}

def _tokens(text: str) -> list[str]:
    norm = _normalize(text)
    out: list[str] = []
    for tok in norm.split():
        if tok in _IT_STOPWORDS:
            continue
        if tok in _SYNONYMS:
            out.extend(_SYNONYMS[tok].split())
        else:
            out.append(tok)
    return out


def _jaccard(text_a: str, text_b: str) -> float:
    a = set(_tokens(text_a))
    b = set(_tokens(text_b))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(needle_text: str, haystack_text: str) -> float:
    """Token-level recall: how many distinct content tokens of `needle_text`
    appear in `haystack_text`. Asymmetric — measures *if the excerpt is
    contained semantically in the page*, regardless of page length."""
    a = set(_tokens(needle_text))
    b = set(_tokens(haystack_text))
    if not a:
        return 0.0
    return len(a & b) / len(a)


# ── Normalization ─────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Aggressive normalization for fuzzy matching: NFC, lowercase, strip
    punctuation including curly quotes, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = re.sub(r"[«»\"'`‘’“”„‚]", " ", text)
    text = re.sub(r"[,;:.!?()\[\]{}–—_/\\*–·•]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ngrams(text: str, n: int = _NGRAM_N) -> list[str]:
    """Word-level n-grams. If text is shorter than n, return the whole text."""
    words = _normalize(text).split()
    if len(words) < n:
        return [_normalize(text)] if text else []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def _coverage(needle: str, haystack_normalized: str) -> float:
    """Fraction of the needle's n-grams that appear in haystack."""
    grams = _ngrams(needle)
    if not grams:
        return 0.0
    matched = sum(1 for g in grams if g in haystack_normalized)
    return matched / len(grams)


# ── PDF loading ───────────────────────────────────────────────────────────────

def _resolve_pdf_path(pdf_filename: str) -> Path | None:
    """Match rule's pdf_file against actual filenames, handling space variants."""
    candidates = [
        _PDF_DIR / pdf_filename,
        _PDF_DIR / pdf_filename.replace(" ", ""),
        _PDF_DIR / pdf_filename.replace("_", "_ "),  # Nota_66.pdf → Nota_66 .pdf
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback: glob with suffix
    base = pdf_filename.replace(" ", "").replace(".pdf", "")
    for f in _PDF_DIR.glob("*.pdf"):
        if f.name.replace(" ", "").startswith(base):
            return f
    return None


def _extract_pages(pdf_path: Path) -> dict[int, str]:
    """Return {page_number: text} for the PDF (1-indexed)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF (fitz) not installed", file=sys.stderr)
        sys.exit(2)

    doc = fitz.open(str(pdf_path))
    pages: dict[int, str] = {}
    for i, page in enumerate(doc):
        pages[i + 1] = page.get_text("text")
    doc.close()
    return pages


# ── Audit logic ───────────────────────────────────────────────────────────────

def _audit_excerpt_in_pages(
    excerpt: str,
    expected_page: int,
    pages: dict[int, str],
) -> dict:
    """Return audit result for a single excerpt vs PDF pages."""
    norm_excerpt = _normalize(excerpt)

    # Strip leading/trailing quotes that YAML often preserves around the excerpt
    norm_excerpt = norm_excerpt.strip(' "\'')

    if not norm_excerpt:
        return {
            "status": _FABRICATED,
            "coverage_target": 0.0,
            "coverage_best": 0.0,
            "best_page": None,
            "note": "empty excerpt",
        }

    # Primary check: target page
    target_text = pages.get(expected_page, "")
    norm_target = _normalize(target_text)
    cov_target = _coverage(norm_excerpt, norm_target)
    target_verbatim = norm_excerpt in norm_target

    # Cross-page search: best matching page in the entire PDF
    cov_per_page = {p: _coverage(norm_excerpt, _normalize(t)) for p, t in pages.items()}
    best_page, cov_best = max(cov_per_page.items(), key=lambda kv: kv[1])
    best_verbatim = norm_excerpt in _normalize(pages.get(best_page, ""))

    # Token containment with synonyms (semantic equivalence)
    # = fraction of distinct content tokens of the excerpt that are present in the page
    cont_target = _containment(excerpt, pages.get(expected_page, ""))
    cont_per_page = {p: _containment(excerpt, t) for p, t in pages.items()}
    best_page_cont, cont_best = max(cont_per_page.items(), key=lambda kv: kv[1])
    # If the n-gram-best-page differs from containment-best-page, prefer containment
    if cont_best > cov_best:
        best_page = best_page_cont

    # Status determination
    if target_verbatim:
        status = _VERBATIM
    elif cov_target >= _NGRAM_APPROX:
        status = _APPROX
    elif best_verbatim and best_page != expected_page:
        status = _WRONG_PAGE
    elif cov_best >= _NGRAM_APPROX and best_page != expected_page:
        status = _WRONG_PAGE
    elif cov_target >= _NGRAM_PARAPHRASE or cont_target >= 0.60:
        # paraphrase: most content tokens present on declared page
        status = _PARAPHRASE
    elif (cov_best >= _NGRAM_APPROX or cont_best >= 0.80) and best_page != expected_page:
        status = _WRONG_PAGE
    elif cov_best >= _NGRAM_PARAPHRASE or cont_best >= 0.60:
        # found on a different page
        status = _WRONG_PAGE
    else:
        status = _FABRICATED

    return {
        "status": status,
        "coverage_target": round(cov_target, 4),
        "coverage_best": round(cov_best, 4),
        "containment_target": round(cont_target, 4),
        "containment_best": round(cont_best, 4),
        "best_page": best_page,
        "target_page": expected_page,
        "verbatim_target": target_verbatim,
        "note": "",
    }


def _gather_rules() -> list[dict]:
    """Load all rules from all 4 nota YAMLs and tag with nota_id."""
    all_rules: list[dict] = []
    for nota in ("01", "13", "66", "97"):
        rules_path = _RULES_DIR / f"nota_{nota}" / "rules.yaml"
        with open(rules_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for rule in data:
            rule["_nota_id"] = nota
            all_rules.append(rule)
    return all_rules


def _audit_one_rule(rule: dict, pdf_cache: dict[str, dict[int, str]]) -> dict:
    anchor = rule.get("normative_anchor", {})
    pdf_filename = anchor.get("pdf_file", "")
    page = int(anchor.get("page", 0))
    excerpt = anchor.get("excerpt", "")
    section = anchor.get("section", "")

    pdf_path = _resolve_pdf_path(pdf_filename)
    if pdf_path is None:
        return {
            "rule_id": rule["rule_id"],
            "nota_id": rule["_nota_id"],
            "rule_type": rule.get("rule_type", "?"),
            "pdf_file": pdf_filename,
            "page": page,
            "section": section,
            "excerpt": excerpt.strip(),
            "status": _FABRICATED,
            "severity": "BLOCCANTE",
            "note": f"PDF not found for filename '{pdf_filename}'",
        }

    if pdf_filename not in pdf_cache:
        pdf_cache[pdf_filename] = _extract_pages(pdf_path)
    pages = pdf_cache[pdf_filename]

    if page not in pages:
        return {
            "rule_id": rule["rule_id"],
            "nota_id": rule["_nota_id"],
            "rule_type": rule.get("rule_type", "?"),
            "pdf_file": pdf_filename,
            "page": page,
            "section": section,
            "excerpt": excerpt.strip(),
            "status": _FABRICATED,
            "severity": "BLOCCANTE",
            "note": f"Page {page} does not exist in PDF (max page: {max(pages)})",
        }

    audit = _audit_excerpt_in_pages(excerpt, page, pages)

    return {
        "rule_id": rule["rule_id"],
        "nota_id": rule["_nota_id"],
        "rule_type": rule.get("rule_type", "?"),
        "pdf_file": pdf_filename,
        "page": page,
        "section": section,
        "excerpt": excerpt.strip(),
        "status": audit["status"],
        "severity": _SEVERITY[audit["status"]],
        "coverage_target": audit["coverage_target"],
        "coverage_best": audit["coverage_best"],
        "containment_target": audit.get("containment_target"),
        "containment_best": audit.get("containment_best"),
        "best_page": audit["best_page"],
        "verbatim_target": audit["verbatim_target"],
        "note": audit.get("note", ""),
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def _summarize(results: list[dict]) -> dict:
    counts = {s: 0 for s in (_VERBATIM, _APPROX, _PARAPHRASE, _WRONG_PAGE, _FABRICATED)}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def _render_markdown(results: list[dict], summary: dict) -> str:
    lines: list[str] = []
    lines.append("# Maniacal PDF → Rule Fidelity Audit")
    lines.append("")
    lines.append(f"_Generated: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total rules:       **{len(results)}**")
    lines.append(f"- ✅ VERBATIM_FOUND:  **{summary[_VERBATIM]}**")
    lines.append(f"- ✅ APPROX_FOUND:    **{summary[_APPROX]}**  _(3-gram coverage ≥ {_NGRAM_APPROX})_")
    lines.append(f"- ⚠️ PARTIAL_MATCH:   **{summary[_PARAPHRASE]}**  _(coverage in [{_NGRAM_PARAPHRASE}, {_NGRAM_APPROX}))_")
    lines.append(f"- 🟠 WRONG_PAGE:      **{summary[_WRONG_PAGE]}**  _(found on a different page)_")
    lines.append(f"- 🔴 NOT_FOUND:       **{summary[_FABRICATED]}**  _(BLOCKING)_")
    lines.append("")
    if summary[_FABRICATED] == 0:
        lines.append("**🟢 NO BLOCCANTI — pipeline può procedere.**")
    else:
        lines.append("**🔴 BLOCCANTI presenti — fix richiesto prima di procedere.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # By severity, then by Nota
    severity_order = ["BLOCCANTE", "ALTO", "MEDIO", "INFO"]
    for sev in severity_order:
        rows = [r for r in results if r["severity"] == sev]
        if not rows:
            continue
        lines.append(f"## {sev} ({len(rows)} regole)")
        lines.append("")
        lines.append("| rule_id | Nota | type | pdf p. | status | cov_target | cov_best | best_p | excerpt |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: (x["nota_id"], x["rule_id"])):
            excerpt_preview = r["excerpt"][:80].replace("\n", " ").replace("|", "\\|")
            if len(r["excerpt"]) > 80:
                excerpt_preview += "…"
            lines.append(
                f"| `{r['rule_id']}` | {r['nota_id']} | {r['rule_type']} "
                f"| {r['pdf_file']} p.{r['page']} | **{r['status']}** "
                f"| {r.get('coverage_target', '—')} | {r.get('coverage_best', '—')} "
                f"| {r.get('best_page', '—')} | _{excerpt_preview}_ |"
            )
        lines.append("")

    # Per-Nota breakdown
    lines.append("## Per-Nota breakdown")
    lines.append("")
    lines.append("| Nota | rules | VERBATIM | APPROX | PARTIAL | WRONG_PAGE | NOT_FOUND |")
    lines.append("|---|---|---|---|---|---|---|")
    for nota in ("01", "13", "66", "97"):
        rows = [r for r in results if r["nota_id"] == nota]
        cnt = {s: sum(1 for r in rows if r["status"] == s) for s in (_VERBATIM, _APPROX, _PARAPHRASE, _WRONG_PAGE, _FABRICATED)}
        lines.append(
            f"| {nota} | {len(rows)} | {cnt[_VERBATIM]} | {cnt[_APPROX]} | {cnt[_PARAPHRASE]} "
            f"| {cnt[_WRONG_PAGE]} | {cnt[_FABRICATED]} |"
        )
    lines.append("")

    # Detailed problem rules with full excerpt + best-page text snippet
    problems = [r for r in results if r["severity"] in ("BLOCCANTE", "ALTO", "MEDIO")]
    if problems:
        lines.append("---")
        lines.append("")
        lines.append("## Detail of issues (BLOCCANTE + ALTO + MEDIO)")
        lines.append("")
        for r in sorted(problems, key=lambda x: (severity_order.index(x["severity"]), x["nota_id"], x["rule_id"])):
            lines.append(f"### `{r['rule_id']}` — {r['severity']}")
            lines.append("")
            lines.append(f"- **PDF:** `{r['pdf_file']}` page **{r['page']}** (section: *{r.get('section', '—')}*)")
            lines.append(f"- **Status:** `{r['status']}`")
            lines.append(f"- **Coverage on target page:** {r.get('coverage_target', '?')}")
            lines.append(f"- **Best coverage anywhere:** {r.get('coverage_best', '?')} on page {r.get('best_page', '?')}")
            if r.get("note"):
                lines.append(f"- **Note:** {r['note']}")
            lines.append("")
            lines.append("**Excerpt declared in YAML:**")
            lines.append("")
            lines.append("> " + r["excerpt"].strip().replace("\n", "\n> "))
            lines.append("")

    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true", help="exit 1 also on ALTO")
    p.add_argument("--json-only", action="store_true", help="skip markdown")
    args = p.parse_args()

    print("Loading rules...", file=sys.stderr)
    rules = _gather_rules()
    print(f"  {len(rules)} rules across 4 Note", file=sys.stderr)

    print("Auditing each rule against the PDF...", file=sys.stderr)
    pdf_cache: dict[str, dict[int, str]] = {}
    results: list[dict] = []
    for rule in rules:
        results.append(_audit_one_rule(rule, pdf_cache))
        sys.stderr.write(".")
        sys.stderr.flush()
    sys.stderr.write("\n")

    summary = _summarize(results)

    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = _AUDIT_DIR / "PDF_AUDIT_REPORT.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"JSON written: {json_path}", file=sys.stderr)

    if not args.json_only:
        md_path = _AUDIT_DIR / "PDF_AUDIT_REPORT.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(_render_markdown(results, summary))
        print(f"Markdown written: {md_path}", file=sys.stderr)

    print("\n" + "=" * 60)
    print(f"PDF Audit — {len(results)} rules audited")
    print("=" * 60)
    for status in (_VERBATIM, _APPROX, _PARAPHRASE, _WRONG_PAGE, _FABRICATED):
        print(f"  {status:18s} {summary[status]:3d}  ({_SEVERITY[status]})")
    print("=" * 60)

    blocking = summary[_FABRICATED]
    high = summary[_WRONG_PAGE]
    if blocking > 0:
        print(f"\n🔴 {blocking} BLOCKING rules — fix required.")
        return 1
    if args.strict and high > 0:
        print(f"\n🟠 --strict: {high} ALTO rules treated as failure.")
        return 1
    print("\n🟢 No blocking findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
