"""
For each rule whose normative_anchor.excerpt is NOT verbatim from the cited PDF
page, suggest the best verbatim replacement.

Strategy
--------
1. For each problematic rule (NOT_FOUND / WRONG_PAGE / PARTIAL_MATCH from
   audit/PDF_AUDIT_REPORT.json):
   a. Take the target PDF page text.
   b. Score every candidate substring (sentence-aligned) by keyword overlap
      with the current excerpt (token Jaccard after Italian stopword removal).
   c. Take the top candidate, expand to nearest sentence boundaries.
   d. Output (current_excerpt, suggested_verbatim, confidence).

The output is a Markdown report `audit/EXCERPT_FIXES_PROPOSED.md` and a YAML
patch `audit/excerpt_fixes.yaml` that another script can apply.

Usage:
    python tools/suggest_verbatim_excerpts.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml


_PROJECT = Path(__file__).resolve().parent.parent
_PDF_DIR = _PROJECT
_RULES_DIR = _PROJECT / "aifa_rule_engine" / "rules"
_AUDIT_DIR = _PROJECT.parent / "audit"


# Italian stopwords + Note AIFA-specific noise
_STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "del", "della",
    "dello", "dei", "degli", "delle", "di", "a", "da", "in", "su", "con",
    "per", "tra", "fra", "ed", "e", "o", "che", "cui", "non", "si", "se",
    "anche", "come", "ma", "al", "allo", "alla", "ai", "agli", "alle",
    "nel", "nello", "nella", "nei", "negli", "nelle", "il", "questi",
    "queste", "questo", "questa", "ciò", "essere", "stato", "essere",
    "è", "sono", "deve", "devono", "dovrà", "dovranno", "può", "possono",
    "ha", "hanno", "avere",
}

# Synonyms: words to consider equivalent for matching
_SYNONYMS = {
    "ecg": "elettrocardiogramma",
    "fa": "fanv",
    "fans": "fans",
    "doac": "doac",
    "nao/doac": "doac",
    "nao": "doac",
    "avk": "avk",
    "irc": "insufficienza renale cronica",
    "vfg": "vfg",
    "ldl": "ldl",
    "hdl": "hdl",
    "tg": "trigliceridi",
    "cv": "cardiovascolare",
}


def _normalize_token(t: str) -> str:
    t = unicodedata.normalize("NFC", t).lower()
    t = re.sub(r"[«»\"'`‘’“”„‚,;:.!?()\[\]{}–—_/\\*–·•]", "", t)
    return t.strip()


def _tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[«»\"'`‘’“”„‚]", " ", text)
    text = re.sub(r"[,;:.!?()\[\]{}–—_/\\*–·•]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = []
    for t in text.split():
        # Expand synonyms
        if t in _SYNONYMS:
            tokens.extend(_SYNONYMS[t].split())
        else:
            tokens.append(t)
    return [t for t in tokens if t and t not in _STOPWORDS]


def _split_sentences(page_text: str) -> list[str]:
    """Split page text into sentences (Italian-aware) and clean noise."""
    # Replace bullet-like glyphs with periods to help splitting
    text = re.sub(r"[•▪]", ".", page_text)
    # Normalize line breaks and collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Split on sentence terminators followed by capital letter or end
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÀÈÉÌÒÙ])", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _token_set(text: str) -> set[str]:
    return set(_tokenize(text))


def _expand_to_window(sentences: list[str], best_idx: int, target_words: int) -> str:
    """Combine adjacent sentences around best_idx until total length ~target_words."""
    chosen = [sentences[best_idx]]
    chosen_count = len(_tokenize(sentences[best_idx]))
    left, right = best_idx - 1, best_idx + 1
    while chosen_count < target_words and (left >= 0 or right < len(sentences)):
        # Pick whichever side has higher overlap budget; default left
        if left >= 0 and (right >= len(sentences) or len(sentences[left]) <= len(sentences[right])):
            chosen.insert(0, sentences[left])
            chosen_count += len(_tokenize(sentences[left]))
            left -= 1
        elif right < len(sentences):
            chosen.append(sentences[right])
            chosen_count += len(_tokenize(sentences[right]))
            right += 1
        else:
            break
    return " ".join(chosen)


def _suggest_verbatim(current_excerpt: str, page_text: str, target_words: int = 30) -> dict:
    sentences = _split_sentences(page_text)
    if not sentences:
        return {"suggested": "", "confidence": 0.0, "method": "no_sentences"}

    excerpt_tokens = _token_set(current_excerpt)
    if not excerpt_tokens:
        return {"suggested": "", "confidence": 0.0, "method": "empty_excerpt"}

    scored = [
        (i, s, _jaccard(excerpt_tokens, _token_set(s)))
        for i, s in enumerate(sentences)
    ]
    best_idx, best_sentence, best_score = max(scored, key=lambda x: x[2])

    if best_score < 0.10:
        # Try with windows of 2 consecutive sentences
        best_window = ""
        best_w_score = 0.0
        for i in range(len(sentences) - 1):
            window = sentences[i] + " " + sentences[i + 1]
            s = _jaccard(excerpt_tokens, _token_set(window))
            if s > best_w_score:
                best_w_score = s
                best_window = window
        if best_w_score > best_score:
            return {
                "suggested": best_window,
                "confidence": round(best_w_score, 3),
                "method": "2-sentence-window",
            }
        return {
            "suggested": best_sentence,
            "confidence": round(best_score, 3),
            "method": "single-sentence (low confidence)",
        }

    # Optionally expand to neighbors if sentence is short
    if len(_tokenize(best_sentence)) < target_words / 2:
        suggested = _expand_to_window(sentences, best_idx, target_words)
    else:
        suggested = best_sentence

    return {
        "suggested": suggested,
        "confidence": round(best_score, 3),
        "method": "single-sentence",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_audit() -> list[dict]:
    audit_path = _AUDIT_DIR / "PDF_AUDIT_REPORT.json"
    with open(audit_path, encoding="utf-8") as f:
        data = json.load(f)
    return data["results"]


def _resolve_pdf_path(pdf_filename: str) -> Path | None:
    candidates = [_PDF_DIR / pdf_filename, _PDF_DIR / pdf_filename.replace(" ", "")]
    for c in candidates:
        if c.exists():
            return c
    base = pdf_filename.replace(" ", "").replace(".pdf", "")
    for f in _PDF_DIR.glob("*.pdf"):
        if f.name.replace(" ", "").startswith(base):
            return f
    return None


def _extract_pages(pdf_path: Path) -> dict[int, str]:
    import fitz
    doc = fitz.open(str(pdf_path))
    pages = {i + 1: p.get_text("text") for i, p in enumerate(doc)}
    doc.close()
    return pages


def main() -> int:
    results = _load_audit()
    # Aligned with audit_rules_vs_pdf.py status values:
    # FABRICATED (BLOCKING — text not in PDF), WRONG_PAGE (text exists on different page),
    # PARAPHRASE_DOCUMENTED (only paraphrase found — verbatim still missing).
    problematic = [
        r for r in results
        if r["status"] in ("FABRICATED", "WRONG_PAGE", "PARAPHRASE_DOCUMENTED")
    ]

    print(f"Processing {len(problematic)} problematic rules...", file=sys.stderr)

    pdf_cache: dict[str, dict[int, str]] = {}
    proposals: list[dict] = []

    for r in problematic:
        pdf_path = _resolve_pdf_path(r["pdf_file"])
        if pdf_path is None:
            continue
        if r["pdf_file"] not in pdf_cache:
            pdf_cache[r["pdf_file"]] = _extract_pages(pdf_path)

        # Use the best_page found by the audit (might be different from declared)
        target_page = r.get("best_page") or r["page"]
        target_text = pdf_cache[r["pdf_file"]].get(target_page, "")

        suggestion = _suggest_verbatim(r["excerpt"], target_text, target_words=30)
        proposals.append({
            "rule_id": r["rule_id"],
            "nota_id": r["nota_id"],
            "rule_type": r["rule_type"],
            "pdf_file": r["pdf_file"],
            "current_page": r["page"],
            "suggested_page": target_page,
            "current_excerpt": r["excerpt"],
            "suggested_verbatim": suggestion["suggested"],
            "confidence": suggestion["confidence"],
            "method": suggestion["method"],
            "audit_status": r["status"],
        })

    # Write JSON for programmatic apply
    out_json = _AUDIT_DIR / "excerpt_fixes_proposed.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"proposals": proposals}, f, indent=2, ensure_ascii=False)
    print(f"JSON: {out_json}", file=sys.stderr)

    # Write Markdown
    md_lines = ["# Excerpt fix proposals (verbatim from PDF)", ""]
    md_lines.append(f"_Generated for {len(proposals)} rules with NOT_FOUND/WRONG_PAGE/PARTIAL_MATCH status._")
    md_lines.append("")
    md_lines.append("Each proposal suggests the verbatim PDF passage that best matches "
                    "the current paraphrase. Manually review and approve before applying.")
    md_lines.append("")
    by_conf = sorted(proposals, key=lambda x: -x["confidence"])
    for p in by_conf:
        md_lines.append(f"## `{p['rule_id']}` ({p['nota_id']}, {p['rule_type']}) — confidence: {p['confidence']}")
        md_lines.append("")
        md_lines.append(f"- **PDF:** `{p['pdf_file']}` p.{p['current_page']} "
                        + (f"→ suggested p.{p['suggested_page']}" if p['suggested_page'] != p['current_page'] else ""))
        md_lines.append(f"- **Audit status:** `{p['audit_status']}`")
        md_lines.append(f"- **Method:** {p['method']}")
        md_lines.append("")
        md_lines.append("**Current excerpt (paraphrase):**")
        md_lines.append("> " + p["current_excerpt"].strip().replace("\n", " "))
        md_lines.append("")
        md_lines.append("**Suggested verbatim from PDF:**")
        md_lines.append("> " + (p["suggested_verbatim"] or "_(no candidate found)_").strip().replace("\n", " "))
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    out_md = _AUDIT_DIR / "EXCERPT_FIXES_PROPOSED.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Markdown: {out_md}", file=sys.stderr)

    # Summary by confidence
    high_conf = sum(1 for p in proposals if p["confidence"] >= 0.5)
    med_conf = sum(1 for p in proposals if 0.25 <= p["confidence"] < 0.5)
    low_conf = sum(1 for p in proposals if p["confidence"] < 0.25)
    print(f"\nConfidence distribution:")
    print(f"  HIGH (≥0.5):   {high_conf}  (likely correct, can auto-apply)")
    print(f"  MEDIUM (0.25-0.5): {med_conf}  (review recommended)")
    print(f"  LOW (<0.25):  {low_conf}  (manual fix required)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
