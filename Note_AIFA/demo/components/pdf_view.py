"""Render a PDF page reference with optional verbatim highlight.

`render_pdf_anchor` opens an expander showing the requested PDF page using
streamlit-pdf-viewer; when `highlight_text` is provided it locates the snippet
via PyMuPDF and passes word-level annotations to the viewer so the user sees
the exact rule citation highlighted in context. When PyMuPDF is missing the
viewer still renders the page (no highlights), and when streamlit-pdf-viewer
is missing it falls back to a download button.
"""
from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent

# Filesystem unified to "Nota_66.pdf" (no space) on 2026-05-06 (audit fix H3);
# aliases kept for backward-compat with legacy chunks/reports.
_FILE_ALIASES = {
    "nota_66.pdf": "Nota_66.pdf",
    "nota_66 .pdf": "Nota_66.pdf",
    "Nota_66 .pdf": "Nota_66.pdf",
}


def _resolve_pdf_path(pdf_file: str | None) -> Path | None:
    if not pdf_file:
        return None
    # Audit fix 2026-05-07 (V3-W4-MEDIUM): path-traversal guard. The pdf_file
    # argument flows from rule-engine evidence; reject anything outside project root.
    project_root = _PROJECT.resolve()

    def _safe(p: Path) -> Path | None:
        try:
            resolved = p.resolve()
        except (OSError, RuntimeError):
            return None
        try:
            resolved.relative_to(project_root)
        except ValueError:
            return None
        return resolved if resolved.exists() and resolved.is_file() else None

    candidates = [pdf_file, _FILE_ALIASES.get(pdf_file, pdf_file)]
    for cand in candidates:
        safe = _safe(_PROJECT / cand)
        if safe is not None:
            return safe
    target = pdf_file.lower().strip().replace(" ", "")
    for f in _PROJECT.glob("*.pdf"):
        if f.name.lower().strip().replace(" ", "") == target:
            safe = _safe(f)
            if safe is not None:
                return safe
    return None


def _build_highlight_annotations(path: Path, page: int, highlight_text: str) -> list[dict]:
    """Locate `highlight_text` on `page` (1-indexed) and return viewer annotations.

    PDF excerpts often contain newlines, bullet markers, and quote chars that
    don't appear verbatim in the PDF text layer when chunking is char-offset
    based. Strategy:
      1. Normalize and strip the excerpt.
      2. Split into short word-windows (5-9 tokens) and run page.search_for()
         on each — PyMuPDF matches short phrases across line wraps.
      3. Deduplicate overlapping rectangles.
    Returns [] when PyMuPDF missing or no match found.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    # Clean: collapse whitespace, strip quotes/bullet markers/leading colons
    text = highlight_text or ""
    text = re.sub(r"[“”«»«»\"••]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .:;-—")
    if len(text) < 8:
        return []

    annotations: list[dict] = []
    try:
        doc = fitz.open(str(path))
    except Exception:
        return []
    try:
        p_idx = max(0, int(page) - 1)
        if p_idx >= doc.page_count:
            return []
        p = doc[p_idx]

        words = text.split()
        attempts: list[str] = []

        # Build word-windows of size 5-9, stepping by 3, biased to start at
        # word boundaries. These are short enough that newline wraps inside
        # the PDF don't break the match.
        if len(words) <= 6:
            attempts.append(" ".join(words))
        else:
            for size in (8, 6, 5):
                for start in range(0, max(1, len(words) - size + 1), 3):
                    win = " ".join(words[start : start + size])
                    if len(win) >= 20:
                        attempts.append(win)
                if attempts:  # found candidates at this size
                    break

        # Always also try the full normalized text (best match if PDF allows)
        full = text[:200]
        attempts.insert(0, full)

        seen_rects: set[tuple[float, float, float, float]] = set()
        for snippet in attempts:
            try:
                rects = p.search_for(snippet, quads=False)
            except Exception:
                continue
            for r in rects:
                key = (round(r.x0, 1), round(r.y0, 1),
                       round(r.x1, 1), round(r.y1, 1))
                if key in seen_rects:
                    continue
                seen_rects.add(key)
                annotations.append({
                    "page": int(page),
                    "x": float(r.x0),
                    "y": float(r.y0),
                    "width": float(r.width),
                    "height": float(r.height),
                    "color": "yellow",
                })
            if len(annotations) >= 30:
                break
    finally:
        doc.close()
    return annotations


def render_pdf_anchor(
    pdf_file: str | None,
    page: int | None,
    key_suffix: str = "",
    highlight_text: str = "",
    auto_open: bool = False,
) -> None:
    """Render a PDF page in an expander with optional verbatim highlighting.

    Parameters
    ----------
    pdf_file : str
        Filename relative to the project root.
    page : int
        1-indexed page number.
    key_suffix : str
        Must be unique per call site within the same Streamlit run.
    highlight_text : str
        Verbatim excerpt to highlight on the page (best-effort via PyMuPDF
        text search; silently degrades to no-highlight when not found).
    auto_open : bool
        If True the expander starts expanded (for blocking-rule citations).
    """
    if not pdf_file or page is None:
        return
    path = _resolve_pdf_path(pdf_file)
    if path is None:
        st.warning(f"PDF `{pdf_file}` non trovato in {_PROJECT}.")
        return
    safe_id = f"{pdf_file}_{page}_{key_suffix}".replace(" ", "_").replace("/", "_")

    n_hl = 0
    annotations: list[dict] = []
    if highlight_text:
        annotations = _build_highlight_annotations(path, int(page), highlight_text)
        n_hl = len(annotations)

    label_bits = [f"📄 Apri {pdf_file} a pag. {page}"]
    if n_hl:
        label_bits.append(f"({n_hl} riferiment{'i' if n_hl != 1 else 'o'} evidenziato)")
    label = " ".join(label_bits)

    try:
        from streamlit_pdf_viewer import pdf_viewer  # type: ignore
        with st.expander(label, expanded=auto_open):
            if highlight_text and not annotations:
                st.caption(
                    "_(impossibile evidenziare il riferimento sul PDF — la citazione "
                    "esatta non è stata localizzata; il viewer mostra la pagina intera.)_"
                )
            elif annotations:
                st.caption(
                    f"_Riferimento evidenziato in giallo sul PDF — {n_hl} occorrenz"
                    f"{'e' if n_hl != 1 else 'a'} corrispondent"
                    f"{'i' if n_hl != 1 else 'e'} al testo della citazione._"
                )
            # streamlit-pdf-viewer rejects None for annotations (TypeError);
            # pass [] when nothing to highlight.
            kwargs = {
                "pages_to_render": [int(page)],
                "annotations": annotations if annotations else [],
                "width": "100%",
                "key": f"pdfv_{safe_id}",
            }
            if annotations:
                kwargs["scroll_to_annotation"] = 1
            pdf_viewer(str(path), **kwargs)
    except ImportError:
        with st.expander(label, expanded=auto_open):
            st.caption("(installa `streamlit-pdf-viewer` per il viewer inline)")
            with open(path, "rb") as f:
                st.download_button(
                    label=f"Scarica {pdf_file}",
                    data=f.read(),
                    file_name=pdf_file,
                    mime="application/pdf",
                    key=f"dl_{safe_id}",
                )
