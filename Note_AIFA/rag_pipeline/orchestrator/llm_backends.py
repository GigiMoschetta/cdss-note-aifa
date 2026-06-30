"""
LLM Backend Strategy
====================

Abstract `LLMBackend` plus two concrete implementations (`OllamaBackend`,
`OpenAIBackend`). Pulled out of `cdss_orchestrator.py` (refactor RE-M5) so
the orchestrator no longer carries duplicated `_call_*` methods and so
backends can be swapped/mocked independently in tests.

Determinism contract (audit-mandated):
    - temperature = 0.0
    - seed        = 42
on both backends, mirrored exactly so that switching providers does not
change the reproducibility properties of the pipeline.

Robustness fixes 2026-05-06 (audit P1.NEW2):
    - Single client per backend instance (connection pooling — was instantiated
      per call previously, ~1-2ms overhead and no TCP reuse).
    - Async timeout on `complete()` so a hung LLM cannot block a 116-case batch
      indefinitely. Configurable via env (LLM_COMPLETE_TIMEOUT_S, default 180s).
    - Defensive `.get()` on Ollama response dict — if the model returns an
      error envelope without "content", we degrade gracefully instead of
      raising KeyError.
"""
from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger("orchestrator.llm")


# Default per-call timeout for LLM completions. Override via env var.
# 180s leaves margin for cold-load Ollama (~120s) without dragging the
# overnight batch when a single call hangs.
_DEFAULT_TIMEOUT_S = float(os.getenv("LLM_COMPLETE_TIMEOUT_S", "180"))


class LLMTimeoutError(Exception):
    """Raised when an LLM completion exceeds the configured timeout."""


class LLMBackend(ABC):
    """Abstract LLM backend. Returns (text, prompt_tokens, completion_tokens)."""

    name: str

    def __init__(self, model: str, timeout_s: float | None = None) -> None:
        self.model = model
        self.timeout_s = timeout_s if timeout_s is not None else _DEFAULT_TIMEOUT_S

    @abstractmethod
    async def _complete_inner(self, prompt: str) -> tuple[str, int, int]:
        """Backend-specific completion (no timeout wrapping)."""

    async def complete(self, prompt: str) -> tuple[str, int, int]:
        """Run a single completion with a per-call timeout. Subclasses override
        `_complete_inner`; this method enforces deadlines uniformly."""
        try:
            return await asyncio.wait_for(self._complete_inner(prompt), timeout=self.timeout_s)
        except TimeoutError as exc:
            log.warning(
                "LLM completion timed out after %.1fs (backend=%s, model=%s)",
                self.timeout_s, self.name, self.model,
            )
            raise LLMTimeoutError(
                f"{self.name} completion exceeded {self.timeout_s:.0f}s timeout"
            ) from exc


class OpenAIBackend(LLMBackend):
    """OpenAI Chat Completions backend (default model: gpt-4o-mini).

    Uses the official `seed` parameter (Chat Completions API) for stable
    outputs across runs; combined with temperature=0 this matches the
    determinism guarantee of the Ollama path.
    """

    name = "openai"

    def __init__(self, model: str, timeout_s: float | None = None) -> None:
        super().__init__(model, timeout_s=timeout_s)
        # Lazy: defer AsyncOpenAI() construction until first call so test
        # collection in CI does not require OPENAI_API_KEY to be set.
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI()
        return self._client

    async def _complete_inner(self, prompt: str) -> tuple[str, int, int]:
        client = self._ensure_client()
        response = await client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            seed=42,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return text, usage.prompt_tokens, usage.completion_tokens


class OllamaBackend(LLMBackend):
    """Ollama local-model backend (default model: llama3.1:8b Q4_K_M).

    Hardware-tuned options for RTX 3060 12 GB + i7-13700K:
      - temperature=0.0 + seed=42 → deterministic output
      - num_gpu=999 → full GPU offload (4.9 GB ≪ 12 GB VRAM)
      - num_ctx=16384 → context window (quantized KV stays on GPU)
      - num_predict=1300 → cap completion length
      - keep_alive="30m" → avoid model reload across cases
    """

    name = "ollama"

    def __init__(self, model: str, timeout_s: float | None = None) -> None:
        super().__init__(model, timeout_s=timeout_s)
        # Lazy: import + client construction is deferred to first call so test
        # collection in CI doesn't require ollama package to be importable.
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import ollama
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self._client = ollama.AsyncClient(host=base_url)
        return self._client

    async def _complete_inner(self, prompt: str) -> tuple[str, int, int]:
        client = self._ensure_client()
        response = await client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.0,
                "seed": 42,
                "num_ctx": 16384,
                "num_predict": 1300,
                "num_gpu": 999,
            },
            keep_alive="30m",
        )
        # Defensive: a malformed or error response (e.g. {"error": "..."}) may
        # lack "message" or "content". Return empty string + zero tokens
        # instead of raising KeyError opaquely.
        # Audit fix V3-NEW-LLM (2026-05-07): the ollama-python client (>=0.4)
        # returns a Pydantic ChatResponse object, NOT a dict. The previous
        # `isinstance(response, dict)` guard silently zero-ed every completion
        # because it skipped the field extraction altogether. We now duck-type
        # both shapes (mapping-style .get and attribute-style getattr) so the
        # code keeps working across client versions.
        def _read(obj: Any, key: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        msg = _read(response, "message")
        text = _read(msg, "content", "") or ""
        prompt_tokens = _read(response, "prompt_eval_count", 0) or 0
        completion_tokens = _read(response, "eval_count", 0) or 0
        return text, prompt_tokens, completion_tokens


def build_backend(backend: str, model: str) -> LLMBackend:
    """Factory: instantiate a concrete backend by name."""
    if backend == "openai":
        return OpenAIBackend(model)
    if backend == "ollama":
        return OllamaBackend(model)
    raise ValueError(f"Unknown LLM backend: {backend}")
