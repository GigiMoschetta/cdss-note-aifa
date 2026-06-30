# ── AIFA RAG Pipeline — Service Dockerfile ────────────────────────────────────
# CUDA-enabled image for GPU-accelerated sentence-transformers inference.
# Target: NVIDIA RTX 3060 (Ampere, Compute Capability 8.6), CUDA 12.8.
#
# Host requirements:
#   - NVIDIA driver >= 550 (CUDA 12.8 toolkit compatibility)
#   - NVIDIA Container Toolkit installed and configured
#
# Pinned versions match Note_AIFA/requirements.lock (torch==2.10.0+cu128).
#
# ⚠️  CRITICAL INSTALL ORDER:
#   1. Install PyTorch CUDA wheel FIRST (from PyTorch index, not PyPI).
#   2. Install sentence-transformers SECOND — it detects the existing GPU torch.
#   If reversed, sentence-transformers pulls a CPU-only torch from PyPI and
#   GPU acceleration is silently lost even though the NVIDIA runtime is active.

FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-dev \
        python3-pip \
        python3.12-venv \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf python3.12 /usr/bin/python3 \
    && ln -sf python3    /usr/bin/python \
    && python3 -m pip install --upgrade pip

# ── Step 1: PyTorch with CUDA 12.8 support ────────────────────────────────────
# Must be installed BEFORE sentence-transformers to ensure GPU torch is used.
# Pinned to match requirements.lock (torch==2.10.0+cu128).
RUN pip3 install --no-cache-dir \
    torch==2.10.0+cu128 \
    --index-url https://download.pytorch.org/whl/cu128

# ── Step 2: RAG pipeline dependencies ─────────────────────────────────────────
# sentence-transformers detects the pre-installed GPU torch automatically.
COPY rag_pipeline/requirements_rag.txt ./requirements_rag.txt
RUN pip3 install --no-cache-dir -r requirements_rag.txt

# ── Step 3: Orchestrator dependencies (Phase 2) ────────────────────────────────
COPY rag_pipeline/requirements_orchestrator.txt ./requirements_orchestrator.txt
RUN pip3 install --no-cache-dir -r requirements_orchestrator.txt

# ── Pre-bake NLTK punkt_tab tokenizer data ────────────────────────────────────
# Avoids runtime download on first container start (which would fail without internet).
RUN python3 -c "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('punkt', quiet=True)"

# ── Copy source code ──────────────────────────────────────────────────────────
COPY rag_pipeline/ rag_pipeline/
# Rule engine package is needed by the orchestrator to import EvaluationResult models
COPY aifa_rule_engine/ aifa_rule_engine/
RUN pip3 install --no-cache-dir ./aifa_rule_engine

# ── Directories for persistent data (mounted as Docker volumes) ───────────────
RUN mkdir -p /app/rag_pipeline/chroma_db /app/model_cache

# ── Environment ───────────────────────────────────────────────────────────────
# Model cache: embedding model is downloaded here on first run, then reused.
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache
ENV HF_HOME=/app/model_cache
ENV TRANSFORMERS_CACHE=/app/model_cache
ENV CUDA_VISIBLE_DEVICES=0

# ── Drop privileges (audit fix 2026-05-06, H12) ───────────────────────────────
# Run as non-root. The unprivileged user must be able to write the chroma_db
# (mounted volume) and model_cache (downloaded at runtime).
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default: start the orchestrator API (overridden in compose for ingestion job)
CMD ["uvicorn", "rag_pipeline.orchestrator.main:app", \
     "--host", "0.0.0.0", "--port", "8001"]
