"""
AIFA CDSS — Phase 2: RAG Orchestrator
======================================
Coordinates the Rule Engine, ChromaDB retrieval, and LLM generation.

Package structure:
    schemas.py          — CDSSResponse, RetrievedChunk (output models)
    retriever.py        — Two-stage ChromaDB retrieval (anchor-guided + semantic)
    prompt_builder.py   — Hardened prompt template assembly
    validators.py       — Post-generation quality checks
    cdss_orchestrator.py — CDSSOrchestrator: main pipeline class
    main.py             — FastAPI app (POST /explain endpoint)
"""
