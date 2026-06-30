"""
AIFA RAG Pipeline v2 — Granular Citation-Ready Ingestion
=========================================================

Differences vs ingest.py (v1):
- Char-offset tracking inside each page (char_start, char_end in page_text_full)
- Line-level tracking (line_start, line_end, 1-indexed)
- Bounding box per chunk (union of char bboxes, normalized to PDF user-space)
- SHA256 of chunk text (for verbatim integrity check downstream)
- page_text_full stored per chunk for cross-validation
- Table-aware extraction: pdfplumber detects tables, chunks inside table bbox
  are flagged is_in_table=True and split into one chunk per table row
- PDF SHA256 stored at collection level for integrity tracking
- Additive collections: nota_XX_v2 (v1 untouched for rollback)

Usage:
    python ingest_v2.py [--reset]

Output:
    - ChromaDB collections nota_01_v2 ... nota_97_v2
    - rag_pipeline/ingestion_manifest_v2.json
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
DEFAULT_PDF_DIR = _HERE.parent
DEFAULT_DB_DIR = _HERE / "chroma_db"
MANIFEST_PATH = _HERE / "ingestion_manifest_v2.json"

EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

TARGET_CHARS = 1800
OVERLAP_SENTS = 2
MIN_BLOCK_CHARS = 15
CHROMA_BATCH = 100

PDF_NOTA_MAP: dict[str, str] = {
    "Nota_01.pdf": "01",
    "Nota_66.pdf": "66",  # filesystem unified 2026-05-06 (no trailing space)
    "nota-13.pdf": "13",
    "nota-97.pdf": "97",
    "nota-97-all-1.pdf": "97",
    "nota-97-all-2.pdf": "97",
    "nota-97-all-3.pdf": "97",
}
# Backward-compat for legacy data with trailing-space filename
PDF_NOTA_MAP["Nota_66 .pdf"] = "66"
_PDF_META_NAME: dict[str, str] = {k: k.strip() for k in PDF_NOTA_MAP}

_SECTION_HEADER_RE = re.compile(
    r"""(?x)
    ^(?:
        [Pp]ercorso \s+ [A-D]               |
        [Aa]llegato \s+ \d+                 |
        [Tt]ab(?:ella)? \.? \s* \d+         |
        [Nn]ota \s+ \d{1,2}                 |
        [Cc]ontroindicazioni                |
        [Pp]osologia                        |
        [Ii]ndicazioni                      |
        [Aa]vvertenze                       |
        [Pp]remessa                         |
        [Dd]efinizioni?                     |
        [A-ZÀÈÌÒÙÉ]{4,}(?:\s+[A-ZÀÈÌÒÙÉ]{2,}){0,4}
    )$
    """,
    re.UNICODE,
)
_MAX_SECTION_HEADER_CHARS = 80


def _detect_section(text: str) -> str | None:
    text = text.strip()
    if len(text) > _MAX_SECTION_HEADER_CHARS or "\n" in text:
        return None
    if _SECTION_HEADER_RE.match(text):
        return text
    return None


# ---------------------------------------------------------------------------
# Data structures (v2)
# ---------------------------------------------------------------------------

@dataclass
class CharSpan:
    """Per-char info from PyMuPDF rawdict."""
    char: str
    bbox: tuple  # (x0, y0, x1, y1)
    line_idx: int  # 0-indexed line within page
    block_idx: int


@dataclass
class PageData:
    """Aggregated data for one PDF page."""
    page: int  # 1-indexed
    text: str  # concatenation of all chars
    char_spans: list[CharSpan]  # parallel to text (len(text) == len(char_spans))
    line_count: int  # total lines in page
    table_bboxes: list[tuple]  # bboxes of detected tables
    table_rows: list[dict]  # extracted table cells: {table_idx, row_idx, col_idx, text, bbox}
    section_at_offset: list[tuple]  # (char_offset, section_name) checkpoints


@dataclass
class SentenceV2:
    text: str
    page: int
    char_start: int  # offset in page text
    char_end: int
    line_start: int  # 1-indexed
    line_end: int
    bbox: tuple
    section: str = ""


@dataclass
class ChunkV2:
    text: str
    pdf_file: str
    nota_id: str
    page: int
    page_end: int
    char_start: int  # in starting page text
    char_end: int  # in ending page text
    line_start: int  # 1-indexed in starting page
    line_end: int  # 1-indexed in ending page
    bbox: tuple
    sha256: str
    section: str
    is_in_table: bool
    table_id: str  # "" if not in table
    n_sentences: int
    char_count: int


# ---------------------------------------------------------------------------
# Stage 1: PDF page → PageData (PyMuPDF rawdict + pdfplumber tables)
# ---------------------------------------------------------------------------

def _bbox_intersects(a: tuple, b: tuple, tol: float = 2.0) -> bool:
    """Test if two bboxes intersect (with tolerance)."""
    return not (a[2] < b[0] - tol or a[0] > b[2] + tol or a[3] < b[1] - tol or a[1] > b[3] + tol)


def _bbox_inside(inner: tuple, outer: tuple, tol: float = 2.0) -> bool:
    """Test if inner bbox is inside outer bbox."""
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def _bbox_union(boxes: list[tuple]) -> tuple:
    """Union of multiple bboxes."""
    if not boxes:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def extract_page_data(pdf_path: Path, page_idx: int) -> PageData:
    """
    Extract structured page data with char-level tracking.

    Uses PyMuPDF rawdict for char/line bbox AND for table detection
    (find_tables, available since PyMuPDF 1.23). Single coordinate system,
    no cross-library bbox unit conversion.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_idx]
        rd = page.get_text("rawdict")

        text_parts: list[str] = []
        char_spans: list[CharSpan] = []
        line_idx_global = 0
        block_idx = 0
        section_at_offset: list[tuple] = [(0, "")]
        current_section = ""

        for blk in rd["blocks"]:
            if "lines" not in blk:
                continue
            block_text_buf: list[str] = []
            block_start = len("".join(text_parts))

            for line in blk["lines"]:
                line_chars: list[str] = []
                for span in line["spans"]:
                    for ch in span.get("chars", []):
                        c = ch["c"]
                        char_spans.append(
                            CharSpan(
                                char=c,
                                bbox=tuple(ch["bbox"]),
                                line_idx=line_idx_global,
                                block_idx=block_idx,
                            )
                        )
                        line_chars.append(c)
                line_text = "".join(line_chars)
                if line_text:
                    block_text_buf.append(line_text)
                    text_parts.append(line_text)
                    text_parts.append("\n")
                    char_spans.append(
                        CharSpan(
                            char="\n",
                            bbox=tuple(line.get("bbox", (0, 0, 0, 0))),
                            line_idx=line_idx_global,
                            block_idx=block_idx,
                        )
                    )
                    line_idx_global += 1

            block_text = "".join(block_text_buf).strip()
            if block_text and len(block_text) >= MIN_BLOCK_CHARS:
                detected = _detect_section(block_text)
                if detected:
                    current_section = detected
                    section_at_offset.append((block_start, current_section))
            block_idx += 1

        page_text = "".join(text_parts)

        # Table detection via PyMuPDF.
        # Filter for "real" tables only: ≥2 rows AND ≥2 cols, max cell length ≤300 chars,
        # bbox not covering >70% of page area (otherwise it's likely a 2-col layout).
        table_bboxes: list[tuple] = []
        table_rows: list[dict] = []
        page_area = page.rect.width * page.rect.height
        try:
            tables = page.find_tables()
            tlist = tables.tables if hasattr(tables, "tables") else list(tables)
            for t_idx, t in enumerate(tlist):
                bbox = tuple(t.bbox)
                tarea = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
                extracted = t.extract() or []
                n_rows = len(extracted)
                n_cols = len(extracted[0]) if n_rows > 0 else 0
                # Heuristic filters
                if n_rows < 2 or n_cols < 2:
                    continue
                if page_area > 0 and (tarea / page_area) > 0.70:
                    continue
                # Max cell length: if any cell > 300 chars, this is probably a 2-col layout
                max_cell_len = max(
                    (len(c) for row in extracted for c in row if c), default=0
                )
                if max_cell_len > 300:
                    continue
                table_bboxes.append(bbox)
                for r_idx, row in enumerate(extracted):
                    for c_idx, cell in enumerate(row):
                        if cell and cell.strip():
                            table_rows.append({
                                "table_idx": t_idx,
                                "row_idx": r_idx,
                                "col_idx": c_idx,
                                "text": cell.strip(),
                                "bbox": bbox,
                            })
        except Exception as e:
            logging.warning(f"PyMuPDF find_tables failed on page {page_idx + 1}: {e}")

        return PageData(
            page=page_idx + 1,
            text=page_text,
            char_spans=char_spans,
            line_count=line_idx_global,
            table_bboxes=table_bboxes,
            table_rows=table_rows,
            section_at_offset=section_at_offset,
        )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Stage 2: PageData → SentenceV2 list (NLTK + char-offset tracking)
# ---------------------------------------------------------------------------

def page_to_sentences(pd_obj: PageData) -> list[SentenceV2]:
    """Tokenize page text into sentences with char/line/bbox tracking."""
    import nltk
    from nltk.tokenize import sent_tokenize

    if not pd_obj.text.strip():
        return []

    # Audit V4 2026-05-12: NLTK >=3.9 renamed `punkt` to `punkt_tab`. Without
    # this guard, ingestion fails opaquely with LookupError on fresh installs.
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)

    raw_sentences = sent_tokenize(pd_obj.text, language="italian")
    sentences: list[SentenceV2] = []
    cursor = 0
    section_offsets = pd_obj.section_at_offset
    section_starts = [s[0] for s in section_offsets]

    for sent in raw_sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            continue
        pos = pd_obj.text.find(sent_stripped, cursor)
        if pos < 0:
            continue
        char_start = pos
        char_end = pos + len(sent_stripped)
        cursor = char_end

        # Determine line_start and line_end
        line_start = (
            pd_obj.char_spans[char_start].line_idx + 1
            if char_start < len(pd_obj.char_spans)
            else 1
        )
        line_end = (
            pd_obj.char_spans[char_end - 1].line_idx + 1
            if char_end - 1 < len(pd_obj.char_spans)
            else line_start
        )

        # Bbox: union of all char bboxes in [char_start, char_end)
        char_bboxes = [
            pd_obj.char_spans[i].bbox
            for i in range(char_start, min(char_end, len(pd_obj.char_spans)))
            if pd_obj.char_spans[i].char != "\n"
        ]
        bbox = _bbox_union(char_bboxes) if char_bboxes else (0.0, 0.0, 0.0, 0.0)

        # Section at this offset
        section_idx = bisect.bisect_right(section_starts, char_start) - 1
        section = section_offsets[max(0, section_idx)][1]

        sentences.append(
            SentenceV2(
                text=sent_stripped,
                page=pd_obj.page,
                char_start=char_start,
                char_end=char_end,
                line_start=line_start,
                line_end=line_end,
                bbox=bbox,
                section=section,
            )
        )

    return sentences


# ---------------------------------------------------------------------------
# Stage 3: Sentence list → ChunkV2 (with table-awareness)
# ---------------------------------------------------------------------------

def chunk_sentences_v2(
    sentences_by_page: dict[int, list[SentenceV2]],
    pages: dict[int, PageData],
    pdf_filename: str,
    nota_id: str,
    target_chars: int = TARGET_CHARS,
    overlap_sents: int = OVERLAP_SENTS,
) -> list[ChunkV2]:
    """
    Chunk sentences with char-offset preservation + table awareness.

    Table sentences (i.e. inside a table bbox) are extracted into one chunk
    per table-row to preserve structure.
    """
    chunks: list[ChunkV2] = []
    meta_name = _PDF_META_NAME.get(pdf_filename, pdf_filename.strip())

    # 1) Generate one chunk per table row (structured)
    for page_no, pd_obj in pages.items():
        for tr in pd_obj.table_rows:
            txt = tr["text"]
            if len(txt) < MIN_BLOCK_CHARS:
                continue
            # Char-range for table cells: try to locate text in page_text_full
            char_start = pd_obj.text.find(txt)
            if char_start < 0:
                # Cell text may have been recombined by pdfplumber differently from PDF flow
                char_start = 0
                char_end = len(txt)
                line_start, line_end = 1, 1
            else:
                char_end = char_start + len(txt)
                line_start = (
                    pd_obj.char_spans[char_start].line_idx + 1
                    if char_start < len(pd_obj.char_spans)
                    else 1
                )
                line_end = (
                    pd_obj.char_spans[char_end - 1].line_idx + 1
                    if char_end - 1 < len(pd_obj.char_spans)
                    else line_start
                )

            sha = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]
            table_id = f"t{tr['table_idx']}_r{tr['row_idx']}_c{tr['col_idx']}"
            chunks.append(
                ChunkV2(
                    text=txt,
                    pdf_file=meta_name,
                    nota_id=nota_id,
                    page=page_no,
                    page_end=page_no,
                    char_start=char_start,
                    char_end=char_end,
                    line_start=line_start,
                    line_end=line_end,
                    bbox=tr["bbox"],
                    sha256=sha,
                    section="TABLE",
                    is_in_table=True,
                    table_id=table_id,
                    n_sentences=1,
                    char_count=len(txt),
                )
            )

    # 2) Generate prose chunks from sentences (skip those entirely inside a table bbox)
    flat_sentences: list[SentenceV2] = []
    for page_no in sorted(sentences_by_page.keys()):
        page_sents = sentences_by_page[page_no]
        page_table_bboxes = pages[page_no].table_bboxes
        for s in page_sents:
            in_table = any(_bbox_inside(s.bbox, tb) for tb in page_table_bboxes)
            if not in_table:
                flat_sentences.append(s)

    current: list[SentenceV2] = []
    current_chars = 0

    def _flush(buf: list[SentenceV2]) -> None:
        if not buf:
            return
        text = " ".join(s.text for s in buf)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        first, last = buf[0], buf[-1]
        bboxes = [s.bbox for s in buf if s.bbox != (0.0, 0.0, 0.0, 0.0)]
        bbox = _bbox_union(bboxes) if bboxes else (0.0, 0.0, 0.0, 0.0)
        chunks.append(
            ChunkV2(
                text=text,
                pdf_file=meta_name,
                nota_id=nota_id,
                page=first.page,
                page_end=last.page,
                char_start=first.char_start,
                char_end=last.char_end,
                line_start=first.line_start,
                line_end=last.line_end,
                bbox=bbox,
                sha256=sha,
                section=first.section,
                is_in_table=False,
                table_id="",
                n_sentences=len(buf),
                char_count=len(text),
            )
        )

    for sent in flat_sentences:
        sent_len = len(sent.text)
        if current and (current_chars + 1 + sent_len > target_chars):
            _flush(current)
            current = current[-overlap_sents:] if overlap_sents > 0 else []
            current_chars = sum(len(s.text) for s in current) + max(0, len(current) - 1)
        current.append(sent)
        current_chars += sent_len + (1 if len(current) > 1 else 0)
    _flush(current)

    return chunks


# ---------------------------------------------------------------------------
# Stage 4-5: Embed + ChromaDB upsert
# ---------------------------------------------------------------------------

def _get_embedding_function(model_name: str):
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    # Force GPU if available, fp16 for speed
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        device=device,
        normalize_embeddings=True,
    )


def ingest_chunks_v2(
    chunks: list[ChunkV2],
    pdf_filename: str,
    nota_id: str,
    pdf_stem: str,
    pdf_sha256: str,
    client,
    embedding_fn,
    collection_cache: dict[str, Any],
) -> int:
    """Upsert v2 chunks into ChromaDB collection nota_{id}_v2."""
    if not chunks:
        return 0

    # Audit V4 2026-05-12: honour CHROMA_COLLECTION_SUFFIX env var so
    # ingestion and retrieval are guaranteed to point at the same collection.
    # Previously hardcoded "_v2"; retriever/api side already read the env.
    suffix = os.getenv("CHROMA_COLLECTION_SUFFIX", "_v2")
    collection_name = f"nota_{nota_id}{suffix}"
    if collection_name not in collection_cache:
        collection_cache[collection_name] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine", "schema_version": "v2"},
        )
    collection = collection_cache[collection_name]

    total = 0
    ids_batch: list[str] = []
    docs_batch: list[str] = []
    metas_batch: list[dict[str, Any]] = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{pdf_stem}_{i:04d}_v2"
        ids_batch.append(chunk_id)
        docs_batch.append(chunk.text)
        metas_batch.append({
            "chunk_id": chunk_id,
            "pdf_file": chunk.pdf_file,
            "pdf_sha256": pdf_sha256,
            "nota_id": chunk.nota_id,
            "page": chunk.page,
            "page_end": chunk.page_end,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "bbox_x0": chunk.bbox[0],
            "bbox_y0": chunk.bbox[1],
            "bbox_x1": chunk.bbox[2],
            "bbox_y1": chunk.bbox[3],
            "section": chunk.section,
            "is_in_table": chunk.is_in_table,
            "table_id": chunk.table_id,
            "sha256": chunk.sha256,
            "n_sentences": chunk.n_sentences,
            "char_count": chunk.char_count,
            "schema_version": "v2",
        })

        if len(ids_batch) >= CHROMA_BATCH:
            collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
            total += len(ids_batch)
            ids_batch, docs_batch, metas_batch = [], [], []

    if ids_batch:
        collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
        total += len(ids_batch)

    return total


# ---------------------------------------------------------------------------
# Per-PDF orchestrator
# ---------------------------------------------------------------------------

def _pdf_sha256(pdf_path: Path) -> str:
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        for buf in iter(lambda: f.read(8192), b""):
            h.update(buf)
    return h.hexdigest()


def process_pdf_v2(
    pdf_path: Path,
    nota_id: str,
    client,
    embedding_fn,
    collection_cache: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    import fitz

    t0 = time.perf_counter()
    pdf_filename = pdf_path.name
    pdf_stem = pdf_path.stem
    pdf_sha = _pdf_sha256(pdf_path)

    # Stage 1: extract per-page data
    doc = fitz.open(str(pdf_path))
    n_pages = len(doc)
    doc.close()

    pages: dict[int, PageData] = {}
    for page_idx in range(n_pages):
        pages[page_idx + 1] = extract_page_data(pdf_path, page_idx)

    n_blocks_total = sum(1 for p in pages.values() for _ in p.text.split("\n") if _)
    n_table_rows = sum(len(p.table_rows) for p in pages.values())
    logger.info(f"[{pdf_filename}] pages={n_pages} table_cells={n_table_rows}")

    # Stage 2: page → sentences (with offsets)
    sentences_by_page: dict[int, list[SentenceV2]] = {}
    for pno, pdata in pages.items():
        sentences_by_page[pno] = page_to_sentences(pdata)
    n_sentences = sum(len(v) for v in sentences_by_page.values())
    logger.info(f"[{pdf_filename}] sentences={n_sentences}")

    # Stage 3: chunk
    chunks = chunk_sentences_v2(sentences_by_page, pages, pdf_filename, nota_id)
    logger.info(f"[{pdf_filename}] chunks={len(chunks)} (table={sum(1 for c in chunks if c.is_in_table)})")

    # Stage 4-5: embed + upsert
    n_upserted = ingest_chunks_v2(
        chunks=chunks,
        pdf_filename=pdf_filename,
        nota_id=nota_id,
        pdf_stem=pdf_stem,
        pdf_sha256=pdf_sha,
        client=client,
        embedding_fn=embedding_fn,
        collection_cache=collection_cache,
    )

    elapsed = time.perf_counter() - t0
    return {
        "pdf_file": pdf_filename.strip(),
        "nota_id": nota_id,
        "pdf_sha256": pdf_sha,
        "n_pages": n_pages,
        "n_sentences": n_sentences,
        "n_chunks": len(chunks),
        "n_table_chunks": sum(1 for c in chunks if c.is_in_table),
        "n_upserted": n_upserted,
        "elapsed_s": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AIFA RAG ingestion v2 (granular)")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--reset", action="store_true",
                        help="Delete v2 collections before ingesting (v1 untouched)")
    parser.add_argument("--model", default=EMBEDDING_MODEL)
    parser.add_argument("--single", help="Process only one PDF (filename)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("aifa_ingest_v2")

    if not args.pdf_dir.is_dir():
        logger.error("PDF directory not found: %s", args.pdf_dir)
        sys.exit(1)

    # Audit V4 2026-05-12: exclude PDFs whose embedded text is unusable
    # (Wingdings/non-UTF8 encoding produces mojibake chunks that pollute
    # the vector store with garbage). Currently only nota-97-all-1.pdf
    # (a scheda di follow-up clinico, not normative text used by the
    # rule engine) falls in this category.
    _EXCLUDED_PDFS = {"nota-97-all-1.pdf"}

    pdfs_to_process: list[tuple[Path, str]] = []
    for filename, nota_id in PDF_NOTA_MAP.items():
        if args.single and filename.strip() != args.single.strip():
            continue
        if filename in _EXCLUDED_PDFS:
            logger.info("Skipping %s (audit V4: mojibake encoding)", filename)
            continue
        pdf_path = args.pdf_dir / filename
        if pdf_path.exists():
            pdfs_to_process.append((pdf_path, nota_id))
        else:
            logger.warning("PDF not found (skipping): %s", pdf_path)

    if not pdfs_to_process:
        logger.error("No PDF files found in %s", args.pdf_dir)
        sys.exit(1)

    import chromadb
    client = chromadb.PersistentClient(path=str(args.db_dir))

    if args.reset:
        existing = [c.name for c in client.list_collections() if c.name.endswith("_v2")]
        for cname in existing:
            client.delete_collection(cname)
            logger.info("Deleted collection: %s", cname)

    embedding_fn = _get_embedding_function(args.model)
    collection_cache: dict[str, Any] = {}

    manifest: dict[str, Any] = {
        "ingestion_run": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": "v2",
        "embedding_model": args.model,
        "target_chars": TARGET_CHARS,
        "overlap_sentences": OVERLAP_SENTS,
        "files": [],
    }

    for pdf_path, nota_id in pdfs_to_process:
        try:
            stats = process_pdf_v2(
                pdf_path=pdf_path,
                nota_id=nota_id,
                client=client,
                embedding_fn=embedding_fn,
                collection_cache=collection_cache,
                logger=logger,
            )
            manifest["files"].append(stats)
        except Exception as e:
            logger.exception("Failed processing %s: %s", pdf_path, e)
            manifest["files"].append({
                "pdf_file": pdf_path.name,
                "nota_id": nota_id,
                "error": str(e),
            })

    # Total stats
    total_chunks = sum(f.get("n_chunks", 0) for f in manifest["files"])
    total_table_chunks = sum(f.get("n_table_chunks", 0) for f in manifest["files"])
    total_elapsed = sum(f.get("elapsed_s", 0) for f in manifest["files"])
    manifest["total_chunks"] = total_chunks
    manifest["total_table_chunks"] = total_table_chunks
    manifest["total_elapsed_s"] = round(total_elapsed, 2)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info(
        "Done: %d chunks (%d table cells) in %.1fs → %s",
        total_chunks, total_table_chunks, total_elapsed, MANIFEST_PATH,
    )


if __name__ == "__main__":
    main()
