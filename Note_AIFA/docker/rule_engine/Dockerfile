# ── AIFA Rule Engine — Service Dockerfile ─────────────────────────────────────
# Pure Python / CPU service. No GPU required.
# Exposes POST /evaluate and GET /health on port 8000.

FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Copy & install the rule engine package ────────────────────────────────────
COPY aifa_rule_engine/pyproject.toml          aifa_rule_engine/pyproject.toml
COPY aifa_rule_engine/aifa_rule_engine/       aifa_rule_engine/aifa_rule_engine/
COPY aifa_rule_engine/rules/                  aifa_rule_engine/rules/

RUN pip install --no-cache-dir ./aifa_rule_engine

# ── Runtime environment ───────────────────────────────────────────────────────
ENV AIFA_RULES_DIR=/app/aifa_rule_engine/rules
ENV PYTHONUNBUFFERED=1

# ── Drop privileges (audit fix 2026-05-06, H12) ───────────────────────────────
# Run the service as a non-root user. /app is owned by root after COPY but
# read-only at runtime, so the unprivileged user only needs execute access.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "aifa_rule_engine.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
