"""
Centralized ChromaDB collection helper for evaluation metrics.

Resolves the V1/V2 collection mismatch bug (audit fix 2026-05-04 P0.1):
the orchestrator pipeline writes chunk_ids with a `_v2` suffix when
CHROMA_COLLECTION_SUFFIX=_v2 is set (default in `tools/full_cleanroom_v2.sh`),
but several metric scripts hard-coded `f"nota_{nota_id}"` (V1 collection),
producing silent empty lookups → metric values stuck at 0.0.

Usage:
    from evaluation.metrics._chroma_helpers import get_chroma_collection
    col = get_chroma_collection("97")  # returns nota_97_v2 by default
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {}
_CLIENT: Any | None = None
_EMB_FN: Any | None = None

# Default suffix is "_v2": current production pipeline ingest_v2 + orchestrator
# read CHROMA_COLLECTION_SUFFIX="_v2". Metric scripts inherit the same default
# so a fresh-cloned repo "just works" without setting env vars.
_DEFAULT_SUFFIX = "_v2"
_DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _get_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    import chromadb
    db_path = _project_root() / "rag_pipeline" / "chroma_db"
    _CLIENT = chromadb.PersistentClient(path=str(db_path))
    return _CLIENT


def _get_embedding_fn():
    global _EMB_FN
    if _EMB_FN is not None:
        return _EMB_FN
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    model = os.getenv("EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    _EMB_FN = SentenceTransformerEmbeddingFunction(model_name=model)
    return _EMB_FN


def get_chroma_collection(nota_id: str, suffix: str | None = None):
    """Return the ChromaDB collection for a given nota_id.

    Honours CHROMA_COLLECTION_SUFFIX env var. Defaults to "_v2".
    Returns None on lookup failure (and prints a warning).

    Thread-safe singleton cache (one client + per-collection cache).
    """
    if suffix is None:
        suffix = os.getenv("CHROMA_COLLECTION_SUFFIX", _DEFAULT_SUFFIX)
    name = f"nota_{nota_id}{suffix}"

    with _LOCK:
        if name in _CACHE:
            return _CACHE[name]
        try:
            client = _get_client()
            emb_fn = _get_embedding_fn()
            col = client.get_collection(name=name, embedding_function=emb_fn)
            _CACHE[name] = col
            return col
        except Exception as exc:
            print(f"  WARN: ChromaDB collection '{name}' unavailable: {exc}",
                  file=sys.stderr)
            _CACHE[name] = None
            return None


def infer_nota_id(pdf_file: str) -> str | None:
    """Heuristic: map pdf filename to nota_id (01/13/66/97)."""
    name = pdf_file.lower()
    for n in ("01", "13", "66", "97"):
        if f"_{n}" in name or f"-{n}" in name:
            return n
    return None
