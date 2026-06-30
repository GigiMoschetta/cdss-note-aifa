"""
AIFA RAG Pipeline — Phase 1: Structure-Aware, Sentence-Preserving Ingestion
============================================================================

Pipeline stages
---------------
Stage 1 — Layout-aware PDF parsing     : PyMuPDF page.get_text("blocks")
Stage 2 — Sentence tokenisation        : NLTK Italian punkt, char-offset page tracking
Stage 3 — Sentence-preserving chunking : target ~1800 chars, sentence-level overlap
Stage 4 — Embedding                    : sentence-transformers (local, offline)
Stage 5 — ChromaDB upsert              : per-nota_id collection, cosine similarity
Stage 6 — Ingestion manifest           : JSON report written to rag_pipeline/

Usage
-----
    # dry design review (no install needed):
    python ingest.py --help

    # full ingestion (requires: pip install -r requirements_rag.txt):
    python ingest.py

    # reset collections before re-ingesting:
    python ingest.py --reset

    # custom paths:
    python ingest.py --pdf-dir /path/to/pdfs --db-dir /path/to/chroma_db
"""
from __future__ import annotations

import argparse
import bisect
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent                  # rag_pipeline/
DEFAULT_PDF_DIR = _HERE.parent                 # Note_AIFA/  (PDFs live here)
DEFAULT_DB_DIR  = _HERE / "chroma_db"          # rag_pipeline/chroma_db/
MANIFEST_PATH   = _HERE / "ingestion_manifest.json"

EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# Chunking parameters
TARGET_CHARS   = 1800   # ~400-500 tokens for the chosen model
OVERLAP_SENTS  = 2      # number of trailing sentences carried into next chunk
MIN_BLOCK_CHARS = 15    # noise-block filter (single words, page numbers, etc.)

# ChromaDB batch upsert size
CHROMA_BATCH = 100

# ---------------------------------------------------------------------------
# Section header detection — lightweight regex for Italian regulatory PDFs
# ---------------------------------------------------------------------------

# Matches known section header patterns found in AIFA regulatory documents.
# Used to tag each Block (and by extension Sentence/Chunk) with its section.
_SECTION_HEADER_RE = re.compile(
    r"""(?x)
    ^(?:
        [Pp]ercorso \s+ [A-D]               |   # Nota 97 pathways: Percorso A/B/C/D
        [Aa]llegato \s+ \d+                 |   # Annexes: Allegato 1/2/3
        [Tt]ab(?:ella)? \.? \s* \d+         |   # Tables: Tab.4 / Tabella 1
        [Nn]ota \s+ \d{1,2}                 |   # Note headers: Nota 97
        [Cc]ontroindicazioni                |   # Contraindications
        [Pp]osologia                        |   # Dosing
        [Ii]ndicazioni                      |   # Indications
        [Aa]vvertenze                       |   # Warnings
        [Pp]remessa                         |   # Preamble
        [Dd]efinizioni?                     |   # Definitions
        [A-ZÀÈÌÒÙÉ]{4,}(?:\s+[A-ZÀÈÌÒÙÉ]{2,}){0,4}  # All-caps headings (≥4 chars)
    )$
    """,
    re.UNICODE,
)
_MAX_SECTION_HEADER_CHARS = 80  # headers are short, single-line blocks


def _detect_section(text: str) -> str | None:
    """Return the section name if *text* looks like a section header, else None.

    Rules:
    - Must be short (≤ _MAX_SECTION_HEADER_CHARS characters).
    - Must not span multiple lines (no embedded newlines).
    - Must match one of the Italian regulatory section patterns.
    """
    text = text.strip()
    if len(text) > _MAX_SECTION_HEADER_CHARS or "\n" in text:
        return None
    if _SECTION_HEADER_RE.match(text):
        return text
    return None

# ---------------------------------------------------------------------------
# PDF → nota_id mapping (filesystem unified 2026-05-06: no more trailing-space hack).
# ---------------------------------------------------------------------------

PDF_NOTA_MAP: dict[str, str] = {
    "Nota_01.pdf":        "01",
    "Nota_66.pdf":        "66",
    "nota-13.pdf":        "13",
    "nota-97.pdf":        "97",
    "nota-97-all-1.pdf":  "97",
    "nota-97-all-2.pdf":  "97",
    "nota-97-all-3.pdf":  "97",
}

# Backward-compat: legacy "Nota_66 .pdf" (with trailing space) still resolves to "66"
PDF_NOTA_MAP["Nota_66 .pdf"] = "66"

# Normalised filename stored in chunk metadata (strip trailing spaces)
_PDF_META_NAME: dict[str, str] = {k: k.strip() for k in PDF_NOTA_MAP}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """A single text block extracted from a PDF page."""
    text: str
    page: int     # 1-indexed
    section: str = field(default="")  # current section at extraction time


@dataclass
class Sentence:
    """A sentence with page and section provenance."""
    text: str
    page: int     # 1-indexed
    section: str = field(default="")


@dataclass
class Chunk:
    """A semantically coherent text chunk ready for embedding."""
    text: str
    page: int       # page of the first sentence in the chunk
    page_end: int   # page of the last sentence in the chunk
    n_sentences: int
    char_count: int
    section: str = field(default="")  # section of the first sentence


# ---------------------------------------------------------------------------
# Stage 1: Layout-aware PDF → Block list
# ---------------------------------------------------------------------------

def extract_blocks(pdf_path: Path) -> list[Block]:
    """Extract text blocks from a PDF using PyMuPDF layout analysis.

    Uses page.get_text("blocks") which returns tuples:
        (x0, y0, x1, y1, text, block_no, block_type)
    block_type == 0  →  text block (skip images, which are type 1)

    Blocks are sorted top-to-bottom, left-to-right within each page.
    Noise blocks shorter than MIN_BLOCK_CHARS are filtered out.
    """
    import fitz  # PyMuPDF

    blocks: list[Block] = []
    current_section: str = ""
    doc = fitz.open(str(pdf_path))
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_no = page_idx + 1  # 1-indexed
            raw_blocks = page.get_text("blocks")
            # Sort by vertical then horizontal position
            raw_blocks = sorted(raw_blocks, key=lambda b: (b[1], b[0]))
            for b in raw_blocks:
                if b[6] != 0:          # skip non-text blocks
                    continue
                text = b[4].strip()
                if len(text) < MIN_BLOCK_CHARS:
                    continue
                # Update current section if this block is a header
                detected = _detect_section(text)
                if detected:
                    current_section = detected
                blocks.append(Block(text=text, page=page_no, section=current_section))
    finally:
        doc.close()

    return blocks


# ---------------------------------------------------------------------------
# Stage 2: Block list → Sentence list (NLTK, Italian punkt)
# ---------------------------------------------------------------------------

def blocks_to_sentences(blocks: list[Block]) -> list[Sentence]:
    """Tokenise blocks into sentences while preserving page provenance.

    Algorithm:
    1. Concatenate all block texts into a single document string, recording
       the character offset and page number of each block start.
    2. Run NLTK sent_tokenize (Italian punkt) on the full string to avoid
       sentence boundary errors at block seams.
    3. For each sentence, determine its originating page with a binary search
       on the char-offset array.
    """
    from nltk.tokenize import sent_tokenize

    if not blocks:
        return []

    # Build full document string with char-start tracking
    parts: list[str] = []
    char_starts: list[int] = []   # char offset of each block start
    pages: list[int] = []         # page of each block
    sections: list[str] = []      # section of each block

    cursor = 0
    for blk in blocks:
        char_starts.append(cursor)
        pages.append(blk.page)
        sections.append(blk.section)
        parts.append(blk.text)
        cursor += len(blk.text) + 1  # +1 for the joining newline

    full_text = "\n".join(parts)

    raw_sentences = sent_tokenize(full_text, language="italian")

    sentences: list[Sentence] = []
    search_cursor = 0
    for sent in raw_sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            continue
        # Find the position of this sentence in the full text
        pos = full_text.find(sent_stripped, search_cursor)
        if pos == -1:
            # Fallback: use last known page and section
            pg   = pages[-1]    if pages    else 1
            sect = sections[-1] if sections else ""
        else:
            # Binary search: which block does this char offset belong to?
            idx  = bisect.bisect_right(char_starts, pos) - 1
            pg   = pages[max(0, idx)]
            sect = sections[max(0, idx)]
            search_cursor = pos + len(sent_stripped)
        sentences.append(Sentence(text=sent_stripped, page=pg, section=sect))

    return sentences


# ---------------------------------------------------------------------------
# Stage 3: Sentence list → Chunk list (sentence-preserving, overlap)
# ---------------------------------------------------------------------------

def chunk_sentences(
    sentences: list[Sentence],
    target_chars: int = TARGET_CHARS,
    overlap_sents: int = OVERLAP_SENTS,
) -> list[Chunk]:
    """Accumulate sentences into chunks without splitting mid-sentence.

    Algorithm:
    - Accumulate sentences until adding the next would exceed target_chars.
    - Flush current accumulator to a Chunk.
    - Seed the next chunk with the last `overlap_sents` sentences (overlap).

    Guarantees:
    - No sentence is split across chunks.
    - Sentence-level overlap ensures continuity for retrieval.
    - Single sentences longer than target_chars are emitted as solo chunks.
    """
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current: list[Sentence] = []
    current_chars = 0

    def flush(buf: list[Sentence]) -> None:
        if not buf:
            return
        text = " ".join(s.text for s in buf)
        chunks.append(Chunk(
            text=text,
            page=buf[0].page,
            page_end=buf[-1].page,
            n_sentences=len(buf),
            char_count=len(text),
            section=buf[0].section,  # section of the first sentence
        ))

    for sent in sentences:
        sent_len = len(sent.text)

        if current and (current_chars + 1 + sent_len > target_chars):
            flush(current)
            # Overlap: seed next chunk with the last overlap_sents sentences
            current = current[-overlap_sents:] if overlap_sents > 0 else []
            current_chars = sum(len(s.text) for s in current) + max(0, len(current) - 1)

        current.append(sent)
        current_chars += sent_len + (1 if len(current) > 1 else 0)

    flush(current)
    return chunks


# ---------------------------------------------------------------------------
# Stage 4-5: Embed + upsert into ChromaDB
# ---------------------------------------------------------------------------

def _get_embedding_function(model_name: str):
    """Build a ChromaDB-compatible embedding function using sentence-transformers."""
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(model_name=model_name)


def ingest_chunks(
    chunks: list[Chunk],
    pdf_filename: str,    # raw filesystem filename (e.g. "Nota_66 .pdf")
    nota_id: str,
    pdf_stem: str,        # used as chunk-id prefix
    client,               # chromadb.PersistentClient
    embedding_fn,
    collection_cache: dict[str, Any],
) -> int:
    """Upsert chunks into the appropriate ChromaDB collection.

    Collection naming: nota_01, nota_13, nota_66, nota_97
    Chunk IDs:         {pdf_stem}_{i:04d}  (e.g. nota-97-all-2_0007)

    Metadata per chunk (mirrors NormativeAnchor):
        chunk_id    : str  — unique identifier
        pdf_file    : str  — normalised filename (no trailing space)
        nota_id     : str  — "01" | "13" | "66" | "97"
        page        : int  — first page of chunk (1-indexed)
        page_end    : int  — last page of chunk (1-indexed)
        n_sentences : int
        char_count  : int
    """
    if not chunks:
        return 0

    collection_name = f"nota_{nota_id}"
    if collection_name not in collection_cache:
        collection_cache[collection_name] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    collection = collection_cache[collection_name]

    meta_name = _PDF_META_NAME[pdf_filename]  # normalised (stripped) filename

    # Batch upsert
    total = 0
    ids_batch:   list[str] = []
    docs_batch:  list[str] = []
    metas_batch: list[dict[str, Any]] = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{pdf_stem}_{i:04d}"
        ids_batch.append(chunk_id)
        docs_batch.append(chunk.text)
        metas_batch.append({
            "chunk_id":    chunk_id,
            "pdf_file":    meta_name,
            "nota_id":     nota_id,
            "page":        chunk.page,
            "page_end":    chunk.page_end,
            "section":     chunk.section,   # detected section header (may be "" if none detected)
            "n_sentences": chunk.n_sentences,
            "char_count":  chunk.char_count,
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

def process_pdf(
    pdf_path: Path,
    nota_id: str,
    client,
    embedding_fn,
    collection_cache: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Run all stages for a single PDF and return per-file stats."""
    t0 = time.perf_counter()
    pdf_filename = pdf_path.name  # raw filename (may have trailing space)
    pdf_stem = pdf_path.stem

    logger.info("[%s] Stage 1 — extracting blocks …", pdf_filename)
    blocks = extract_blocks(pdf_path)
    logger.info("[%s]   → %d blocks", pdf_filename, len(blocks))

    logger.info("[%s] Stage 2 — sentence tokenisation …", pdf_filename)
    sentences = blocks_to_sentences(blocks)
    logger.info("[%s]   → %d sentences", pdf_filename, len(sentences))

    logger.info("[%s] Stage 3 — chunking (target=%d chars, overlap=%d sents) …",
                pdf_filename, TARGET_CHARS, OVERLAP_SENTS)
    chunks = chunk_sentences(sentences)
    logger.info("[%s]   → %d chunks", pdf_filename, len(chunks))

    logger.info("[%s] Stage 4-5 — embedding + ChromaDB upsert …", pdf_filename)
    n_upserted = ingest_chunks(
        chunks=chunks,
        pdf_filename=pdf_filename,
        nota_id=nota_id,
        pdf_stem=pdf_stem,
        client=client,
        embedding_fn=embedding_fn,
        collection_cache=collection_cache,
    )

    elapsed = time.perf_counter() - t0
    stats: dict[str, Any] = {
        "pdf_file":       pdf_filename.strip(),
        "nota_id":        nota_id,
        "n_blocks":       len(blocks),
        "n_sentences":    len(sentences),
        "n_chunks":       len(chunks),
        "n_upserted":     n_upserted,
        "elapsed_s":      round(elapsed, 2),
    }
    logger.info("[%s] Done in %.1fs — %d chunks upserted.", pdf_filename, elapsed, n_upserted)
    return stats


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AIFA RAG ingestion pipeline — Phase 1",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--pdf-dir", type=Path, default=DEFAULT_PDF_DIR,
        help="Directory containing AIFA PDF source files.",
    )
    parser.add_argument(
        "--db-dir", type=Path, default=DEFAULT_DB_DIR,
        help="ChromaDB persistent storage directory.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete and recreate all nota_* collections before ingesting.",
    )
    parser.add_argument(
        "--model", default=EMBEDDING_MODEL,
        help="sentence-transformers model name.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("aifa_ingest")

    # Validate PDF directory
    if not args.pdf_dir.is_dir():
        logger.error("PDF directory not found: %s", args.pdf_dir)
        sys.exit(1)

    # Collect available PDFs
    pdfs_to_process: list[tuple[Path, str]] = []  # (path, nota_id)
    for filename, nota_id in PDF_NOTA_MAP.items():
        pdf_path = args.pdf_dir / filename
        if pdf_path.exists():
            pdfs_to_process.append((pdf_path, nota_id))
        else:
            logger.warning("PDF not found (skipping): %s", pdf_path)

    if not pdfs_to_process:
        logger.error("No PDF files found in %s — check PDF_NOTA_MAP.", args.pdf_dir)
        sys.exit(1)

    logger.info("Found %d PDF(s) to ingest.", len(pdfs_to_process))

    # Lazy imports (fail fast with a clear message if not installed)
    try:
        import chromadb
        import nltk
        from tqdm import tqdm
    except ImportError as exc:
        logger.error(
            "Missing dependency: %s\n"
            "Run: pip install -r requirements_rag.txt",
            exc,
        )
        sys.exit(1)

    # Ensure NLTK punkt data is present
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        logger.info("Downloading NLTK punkt_tab tokenizer …")
        nltk.download("punkt_tab", quiet=True)

    # ChromaDB client
    args.db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(args.db_dir))

    # Optional reset: delete each unique nota collection once
    if args.reset:
        unique_nota_ids = set(PDF_NOTA_MAP.values())
        for nota_id in sorted(unique_nota_ids):
            col_name = f"nota_{nota_id}"
            try:
                client.delete_collection(col_name)
                logger.info("Deleted collection: %s", col_name)
            except Exception:
                pass  # Collection didn't exist — that's fine

    # Embedding function (shared across all collections)
    logger.info("Loading embedding model: %s", args.model)
    embedding_fn = _get_embedding_function(args.model)

    # Process PDFs
    t_start = time.perf_counter()
    collection_cache: dict[str, Any] = {}
    all_stats: list[dict[str, Any]] = []

    for pdf_path, nota_id in tqdm(pdfs_to_process, desc="Ingesting PDFs", unit="pdf"):
        stats = process_pdf(
            pdf_path=pdf_path,
            nota_id=nota_id,
            client=client,
            embedding_fn=embedding_fn,
            collection_cache=collection_cache,
            logger=logger,
        )
        all_stats.append(stats)

    total_elapsed = time.perf_counter() - t_start

    # Stage 6: Ingestion manifest
    manifest: dict[str, Any] = {
        "generated_at":   time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(total_elapsed, 2),
        "embedding_model": args.model,
        "chunking_params": {
            "target_chars":    TARGET_CHARS,
            "overlap_sents":   OVERLAP_SENTS,
            "min_block_chars": MIN_BLOCK_CHARS,
        },
        "db_dir":   str(args.db_dir),
        "pdf_dir":  str(args.pdf_dir),
        "files":    all_stats,
        "totals": {
            "n_pdfs":      len(all_stats),
            "n_chunks":    sum(s["n_chunks"]    for s in all_stats),
            "n_upserted":  sum(s["n_upserted"]  for s in all_stats),
            "n_sentences": sum(s["n_sentences"] for s in all_stats),
        },
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info("Manifest written → %s", MANIFEST_PATH)

    totals = manifest["totals"]
    logger.info(
        "Ingestion complete: %d PDF(s), %d chunks, %.1fs total.",
        totals["n_pdfs"], totals["n_upserted"], total_elapsed,
    )


if __name__ == "__main__":
    main()
