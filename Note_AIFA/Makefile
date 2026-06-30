# ── AIFA CDSS — Makefile ──────────────────────────────────────────────────────
# Targets for building, running, and testing the CDSS on the new machine.
#
# Prerequisites:
#   - Docker Engine installed
#   - NVIDIA Container Toolkit installed (for GPU targets)
#   - cp .env.example .env  (and fill in OPENAI_API_KEY if using GPT)

COMPOSE        = docker compose
COMPOSE_GPU    = $(COMPOSE)
RULE_ENG_VENV  = aifa_rule_engine/.venv
PYTHON         = python3

.PHONY: help help-full setup build up down ingest test logs clean gpu-check \
        install-local ingest-local test-local \
        run-rule-engine run-rag-pipeline up-local down-local \
        eval-generate eval-rule-engine eval-pipeline eval-retrieval \
        verify-cleanroom demo demo-install

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  AIFA CDSS — Available targets"
	@echo "  ──────────────────────────────────────────────────────────────"
	@echo "  Docker targets (recommended on new PC):"
	@echo "    make setup        Check host prerequisites (Docker + NVIDIA)"
	@echo "    make build        Build Docker images"
	@echo "    make up           Start rule_engine + rag_pipeline services"
	@echo "    make down         Stop all services"
	@echo "    make ingest       Run PDF ingestion into ChromaDB (one-time)"
	@echo "    make test         Run rule engine tests inside Docker"
	@echo "    make logs         Follow live logs from all services"
	@echo "    make clean        Remove containers, volumes, and images"
	@echo ""
	@echo "  Local (venv) targets — development only:"
	@echo "    make install-local   Install rule engine + rag deps into .venv"
	@echo "    make test-local      Run pytest locally (fast, no Docker)"
	@echo "    make ingest-local    Run ingest.py locally (GPU not guaranteed)"
	@echo "    make up-local        Start both services locally (no Docker needed)"
	@echo "    make down-local      Stop locally running services"
	@echo "    make run-rule-engine Run Rule Engine foreground on :8000"
	@echo "    make run-rag-pipeline Run Orchestrator foreground on :8001"
	@echo ""
	@echo "  Evaluation (Phase 4):"
	@echo "    make eval-generate    Generate expected Rule Engine outputs (one-time)"
	@echo "    make eval-rule-engine Run Rule Engine regression (122 gold standard cases)"
	@echo "    make eval-pipeline    Evaluate full pipeline (requires make up)"
	@echo "    make eval-retrieval   Compute Track 2 retrieval metrics (offline, from pipeline_report.json)"
	@echo "    make verify-cleanroom End-to-end reproducibility (wipe + ingest + test + eval)"
	@echo ""
	@echo "  Utility:"
	@echo "    make gpu-check    Verify NVIDIA Container Toolkit is working"
	@echo ""

help-full:
	@echo ""
	@echo "  AIFA CDSS — Full target listing"
	@echo "  ──────────────────────────────────────────────────────────────"
	@grep -E '^[a-zA-Z][a-zA-Z0-9_.-]*:' $(MAKEFILE_LIST) \
	  | grep -v '^.PHONY' \
	  | awk -F':' '{print "    " $$1}' | sort -u
	@echo ""
	@echo "  See RUNBOOK.md for the cleanroom workflow."
	@echo ""

# ── Prerequisites check ───────────────────────────────────────────────────────
setup:
	@echo "==> Checking Docker..."
	@docker info > /dev/null 2>&1 && echo "  ✓ Docker is running" || (echo "  ✗ Docker not running — install Docker Engine" && exit 1)
	@echo "==> Checking NVIDIA Container Toolkit..."
	@docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1 \
		&& echo "  ✓ NVIDIA Container Toolkit is working" \
		|| echo "  ✗ GPU not accessible — install NVIDIA Container Toolkit"
	@echo "==> Checking .env file..."
	@test -f .env && echo "  ✓ .env exists" || (echo "  ✗ .env missing — run: cp .env.example .env" && exit 1)
	@echo "==> Setup check complete."

gpu-check:
	docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi

# ── Docker targets ────────────────────────────────────────────────────────────
build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d rule_engine rag_pipeline
	@echo ""
	@echo "  Services started:"
	@echo "    Rule Engine:  http://localhost:$${RULE_ENGINE_HOST_PORT:-8000}/health"
	@echo "    Orchestrator: http://localhost:$${RAG_HOST_PORT:-8001}/health"

down:
	$(COMPOSE) down

ingest:
	@echo "==> Running PDF ingestion (this may take several minutes on first run)..."
	$(COMPOSE) --profile ingestion run --rm ingestion
	@echo "==> Ingestion complete. Manifest written to rag_pipeline/ingestion_manifest.json"

test:
	$(COMPOSE) run --rm rule_engine \
		python -m pytest tests/ -v --tb=short

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v --rmi local
	@echo "==> Containers, volumes, and local images removed."
	@echo "    Note: chroma_data and model_cache named volumes are also deleted."

# ── Local (venv) targets — faster for development iterations ──────────────────
install-local:
	@echo "==> Creating virtual environment..."
	$(PYTHON) -m venv $(RULE_ENG_VENV)
	$(RULE_ENG_VENV)/bin/pip install --upgrade pip
	$(RULE_ENG_VENV)/bin/pip install -e "aifa_rule_engine[dev]"
	@echo "==> Installing RAG pipeline dependencies..."
	$(RULE_ENG_VENV)/bin/pip install -r rag_pipeline/requirements_rag.txt
	@echo ""
	@echo "  Done. Activate with:"
	@echo "    source $(RULE_ENG_VENV)/bin/activate"

test-local:
	$(RULE_ENG_VENV)/bin/pytest aifa_rule_engine/tests/ rag_pipeline/orchestrator/tests/ -v --tb=short

ingest-local:
	$(RULE_ENG_VENV)/bin/python rag_pipeline/ingest.py --reset

# ── Local service targets (no Docker required) ────────────────────────────────
# Run both API services locally when Docker GPU is unavailable.
# Usage:
#   make up-local        → start both services in background (PIDs in .pids/)
#   make down-local      → stop them
#   make eval-pipeline   → (then run as usual)
#
# In a separate terminal you can also run each service manually:
#   make run-rule-engine   → Rule Engine on :8000  (foreground)
#   make run-rag-pipeline  → Orchestrator on :8001 (foreground)

PIDS_DIR = .pids

run-rule-engine:
	AIFA_RULES_DIR=aifa_rule_engine/rules \
	$(RULE_ENG_VENV)/bin/uvicorn aifa_rule_engine.api.main:app \
		--host 0.0.0.0 --port 8000

run-rag-pipeline:
	RULE_ENGINE_URL=http://localhost:8000 \
	CHROMA_DB_DIR=rag_pipeline/chroma_db \
	OLLAMA_BASE_URL=http://localhost:11434 \
	CHROMA_COLLECTION_SUFFIX=$${CHROMA_COLLECTION_SUFFIX:-_v2} \
	$(RULE_ENG_VENV)/bin/uvicorn rag_pipeline.orchestrator.main:app \
		--host 0.0.0.0 --port 8001

up-local:
	@mkdir -p $(PIDS_DIR)
	@# Audit fix V3-NEW-ENV (2026-05-07): launch uvicorn from one directory
	@# above Note_AIFA. When the cwd is Note_AIFA itself, the directory named
	@# `aifa_rule_engine` (project root, no __init__.py) is detected as a
	@# namespace package and shadows the editable install of the actual
	@# Python package one level deeper. The relative imports inside the
	@# rule_engine API (`from .. import ENGINE_VERSION`) then resolve to the
	@# empty namespace and fail with ImportError. Running from the project
	@# root removes this shadow because the namespace candidate becomes
	@# `Note_AIFA/aifa_rule_engine/` only via PYTHONPATH (not via cwd).
	@# Also use `python -m uvicorn` instead of the bin/uvicorn script: when
	@# the project tree is copied between locations the script shebang may
	@# still point at a stale venv path; `python -m` always resolves through
	@# the explicit venv binary chosen here.
	@echo "==> Starting Rule Engine on :8000..."
	@cd .. && AIFA_RULES_DIR=Note_AIFA/aifa_rule_engine/rules \
	Note_AIFA/$(RULE_ENG_VENV)/bin/python3 -m uvicorn aifa_rule_engine.api.main:app \
		--host 0.0.0.0 --port 8000 \
		> Note_AIFA/$(PIDS_DIR)/rule_engine.log 2>&1 & echo $$! > $(PIDS_DIR)/rule_engine.pid
	@sleep 2
	@echo "==> Starting RAG Orchestrator on :8001..."
	@# rag_pipeline lives at Note_AIFA/rag_pipeline/ (no editable install).
	@# PYTHONPATH points the interpreter at Note_AIFA so it can resolve the
	@# `rag_pipeline.orchestrator.main` module while we run from the project
	@# root cwd (the project-root cwd is what avoids the rule_engine namespace
	@# package shadow described above for the rule engine target).
	@cd .. && RULE_ENGINE_URL=http://localhost:8000 \
	CHROMA_DB_DIR=Note_AIFA/rag_pipeline/chroma_db \
	OLLAMA_BASE_URL=http://localhost:11434 \
	PYTHONPATH=Note_AIFA \
	CHROMA_COLLECTION_SUFFIX=$${CHROMA_COLLECTION_SUFFIX:-_v2} \
	Note_AIFA/$(RULE_ENG_VENV)/bin/python3 -m uvicorn rag_pipeline.orchestrator.main:app \
		--host 0.0.0.0 --port 8001 \
		> Note_AIFA/$(PIDS_DIR)/rag_pipeline.log 2>&1 & echo $$! > $(PIDS_DIR)/rag_pipeline.pid
	@sleep 3
	@echo ""
	@echo "  Services started:"
	@echo "    Rule Engine:  http://localhost:8000/health"
	@echo "    Orchestrator: http://localhost:8001/health"
	@echo ""
	@echo "  Logs:"
	@echo "    tail -f $(PIDS_DIR)/rule_engine.log"
	@echo "    tail -f $(PIDS_DIR)/rag_pipeline.log"
	@echo ""
	@echo "  Stop with: make down-local"

down-local:
	@echo "==> Stopping local services..."
	@if [ -f $(PIDS_DIR)/rag_pipeline.pid ]; then \
		kill $$(cat $(PIDS_DIR)/rag_pipeline.pid) 2>/dev/null && echo "  ✓ Orchestrator stopped" || echo "  (already stopped)"; \
		rm -f $(PIDS_DIR)/rag_pipeline.pid; \
	fi
	@if [ -f $(PIDS_DIR)/rule_engine.pid ]; then \
		kill $$(cat $(PIDS_DIR)/rule_engine.pid) 2>/dev/null && echo "  ✓ Rule Engine stopped" || echo "  (already stopped)"; \
		rm -f $(PIDS_DIR)/rule_engine.pid; \
	fi

# ── Phase 4: Evaluation targets ───────────────────────────────────────────────
eval-generate:
	@echo "==> Generating expected Rule Engine outputs for all gold standard cases..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.generate_expected_outputs
	@echo "==> Done. Files written to evaluation/gold_standard/*_expected_outputs.json"

eval-rule-engine:
	@echo "==> Running Rule Engine regression (122 gold standard cases)..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.evaluate_rule_engine \
		--json-report evaluation/results/rule_engine_report.json
	@echo "==> Report written to evaluation/results/rule_engine_report.json"

eval-pipeline:
	@echo "==> Running full pipeline evaluation (requires: make up)..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.evaluate_pipeline \
		--verbose \
		--timeout 200 \
		--json-report evaluation/results/pipeline_report.json
	@echo "==> Report written to evaluation/results/pipeline_report.json"

eval-retrieval:
	@echo "==> Computing Track 2 retrieval metrics from pipeline_report.json..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.evaluate_retrieval \
		--json-report evaluation/results/retrieval_report.json
	@echo "==> Report written to evaluation/results/retrieval_report.json"

# ── V2 refactor — granular citations + non-tautological metrics ──────────────
.PHONY: ingest-v2 derive-gold regenerate-expected-v2 eval-v2-metrics \
        eval-v2-summary eval-v2-full

ingest-v2:
	@echo "==> Ingesting PDFs with v2 schema (char-offset + tables)..."
	$(RULE_ENG_VENV)/bin/python rag_pipeline/ingest_v2.py --reset
	@echo "==> Done. Collections nota_*_v2 ready."

derive-gold:
	@echo "==> Deriving PDF-anchored gold from rules.yaml..."
	$(RULE_ENG_VENV)/bin/python tools/derive_gold_from_pdf.py
	@echo "==> Wrote evaluation/gold_standard/pdf_derived_anchors.json"

regenerate-expected-v2: derive-gold
	@echo "==> Regenerating expected_outputs_v2.json from PDF anchors..."
	$(RULE_ENG_VENV)/bin/python evaluation/scripts/regenerate_expected_outputs_v2.py
	@echo "==> Done."

eval-v2-metrics:
	@echo "==> Running all v2 non-tautological metrics (M1..M7 + Wilson CI)..."
	bash evaluation/scripts/run_all_metrics_v2.sh

eval-v2-summary:
	@echo "==> Generating OVERNIGHT_SUMMARY_v2.md..."
	$(RULE_ENG_VENV)/bin/python evaluation/scripts/generate_overnight_summary_v2.py

eval-v2-full: ingest-v2 derive-gold regenerate-expected-v2
	@echo "==> Full v2 evaluation: ingest + gold + pipeline + all metrics"
	@echo "    NB: requires CHROMA_COLLECTION_SUFFIX=_v2 and 'make up-local' running"
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.evaluate_pipeline \
		--verbose --timeout 200 --save-explanations \
		--json-report evaluation/results/pipeline_report.json
	$(MAKE) eval-retrieval
	$(MAKE) eval-rule-engine
	$(MAKE) eval-v2-metrics
	$(MAKE) eval-v2-summary

# ── V3.4 audit additional metrics ────────────────────────────────────────────
.PHONY: audit-eval verify-pdf eval-baselines eval-robustness \
        eval-pipeline-save eval-excerpt-match eval-ragas eval-ragas-subset \
        eval-per-case-reports eval-llm-deep

verify-pdf:
	@echo "==> Verifying PDF integrity (SHA256 check vs audit/pdf_checksums.json)..."
	$(RULE_ENG_VENV)/bin/python tools/verify_pdf_integrity.py --strict

eval-baselines:
	@echo "==> Running majority class baseline..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.baselines.majority_class
	@echo ""
	@echo "==> Running LLM-only baseline (requires Ollama)..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.baselines.llm_only

eval-robustness:
	@echo "==> Running idempotency test (20 cases × 3 runs)..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.robustness.idempotency
	@echo ""
	@echo "==> Running boundary perturbation test..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.robustness.boundary_perturbation

audit-eval:
	@echo "==> Running full V3.4 audit evaluation suite..."
	bash tools/run_full_audit_eval.sh

# ── LLM-quality deep audit (RAGAS + excerpt-match + per-case verifiable reports) ─
# Pre-condition: services running (`make up-local`) + pipeline already produced
# `evaluation/results/pipeline_report.json` and saved per-case explanations in
# `evaluation/results/pipeline_explanations/{case_id}.txt`.

# 1. Re-run the pipeline saving every per-case LLM explanation as a .txt file
eval-pipeline-save:
	@echo "==> Running pipeline with --save-explanations (saves per-case .txt) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.evaluate_pipeline \
		--verbose --timeout 200 --save-explanations \
		--json-report evaluation/results/pipeline_report.json

# 2. Deterministic excerpt-match (PDF excerpt verbatim ↔ LLM body / chunks; gold-anchor recall@k)
eval-excerpt-match:
	@echo "==> Computing excerpt-match metric (deterministic) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.excerpt_match \
		--pipeline-report   evaluation/results/pipeline_report.json \
		--explanations-dir  evaluation/results/pipeline_explanations \
		--gold-dir          evaluation/gold_standard \
		--output            evaluation/results/excerpt_match.json

# 3a. RAGAS — full 122 cases × 6 metrics (slow, ~10 hours on Llama 3.1 8B Q4_K_M)
eval-ragas:
	@echo "==> Running RAGAS on full 122 cases (this is slow) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.ragas_eval \
		--pipeline-report  evaluation/results/pipeline_report.json \
		--explanations-dir evaluation/results/pipeline_explanations \
		--gold-dir         evaluation/gold_standard \
		--output           evaluation/results/ragas_report.json

# 3b. RAGAS — stratified subset (20 cases × 6 metrics, ~2-3 hours) — DEFAULT METHODOLOGICAL CHOICE
#
# The full 122-case run is computationally expensive (~10 h on Llama 3.1 8B Q4_K_M)
# AND adds limited information once the deterministic faithfulness signals
# (faithfulness_verbatim, NLI lower-bound, M1 citation verbatim) are already
# present. We deliberately default to a stratified 20-case subset that covers
# all four Notes and all decision classes; the choice is declared in
# OVERNIGHT_SUMMARY_v2.md and LIMITATIONS.md, not a workaround.
RAGAS_SUBSET ?= N01-001,N01-003,N01-005,N01-011,N01-018,N13-003,N13-009,N13-011,N13-018,N13-029,N66-001,N66-004,N66-005,N66-020,N66-021,N97-003,N97-008,N97-026,N97-030,N97-036
eval-ragas-subset:
	@echo "==> Running RAGAS on stratified 20-case subset (declared methodological choice — see LIMITATIONS.md) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.ragas_eval \
		--pipeline-report  evaluation/results/pipeline_report.json \
		--explanations-dir evaluation/results/pipeline_explanations \
		--gold-dir         evaluation/gold_standard \
		--output           evaluation/results/ragas_report_subset.json \
		--case-ids         "$(RAGAS_SUBSET)"

# 4. Generate per-case verifiable Markdown + JSON artifacts under per_case_reports/
eval-per-case-reports:
	@echo "==> Generating per-case verifiable reports (Markdown + JSON per case) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.per_case_report \
		--pipeline-report     evaluation/results/pipeline_report.json \
		--explanations-dir    evaluation/results/pipeline_explanations \
		--rule-engine-report  evaluation/results/rule_engine_report.json \
		--retrieval-report    evaluation/results/retrieval_report.json \
		--excerpt-match       evaluation/results/excerpt_match.json \
		--ragas-report        evaluation/results/ragas_report_subset.json \
		--gold-dir            evaluation/gold_standard \
		--output-dir          evaluation/results/per_case_reports

# 5. One-shot: pipeline + excerpt + RAGAS subset + per-case reports
# (services must already be up via `make up-local`)
eval-llm-deep: eval-pipeline-save eval-excerpt-match eval-ragas-subset eval-per-case-reports
	@echo "==> LLM deep audit COMPLETE."
	@echo "    See evaluation/results/per_case_reports/INDEX.md"

# 6. Composite scores — Malasi 4.5 + CDSS extension (AnswerQuality, ContextualUtility,
#    EvidenceSupport, DecisionScore). Re-run after fixes to upstream metrics
#    (faithfulness_strict, NLI, excerpt_match, RAGAS) to refresh aggregate values
#    cited in the thesis. Pre-condition: upstream JSON reports must already exist
#    in evaluation/results/ (run eval-llm-deep + eval-fast-overnight or eval-full-overnight first).
eval-composite:
	@echo "==> Computing composite scores (AnswerQuality / ContextualUtility / EvidenceSupport / DecisionScore) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.composite_scores \
		--output evaluation/results/composite_scores.json
	@echo "    See evaluation/results/composite_scores.json"

# ── Tesi-grade overnight evaluation (single LLM, full metrics) ────────────────
.PHONY: eval-pdf-audit eval-full-overnight eval-resume eval-fast-overnight eval-composite

eval-pdf-audit:
	@echo "==> Running maniacal PDF→rule fidelity audit..."
	$(RULE_ENG_VENV)/bin/python tools/audit_rules_vs_pdf.py

# Full overnight: PDF audit + wipe + ingest + tests + rule eng + pipeline-save +
# all deterministic + RAGAS + QAEval + composites + per-case reports + summary.
# ~14-16 hours on RTX 3060 with Llama 3.1 8B Q4_K_M.
eval-full-overnight:
	@echo "==> OVERNIGHT EVALUATION (ETA ~14-16h) — leaving PC running"
	bash tools/run_full_overnight.sh

# Resume after a crash/interrupt: skip stages already marked .done
eval-resume:
	bash tools/run_full_overnight.sh --resume

# Fast version (skip RAGAS + QAEval) — ~3-4 hours
eval-fast-overnight:
	bash tools/run_full_overnight.sh --skip-ragas --skip-qaeval

# ── Clean-room end-to-end verification ───────────────────────────────────────
READINESS_TIMEOUT ?= 60
ORCHESTRATOR_URL ?= http://localhost:8001
HEALTH_ENDPOINT ?= /health

verify-cleanroom:
	@echo "==> [0/6] Kill stale uvicorn services on :8000/:8001 (prevents orphan-cache bug)..."
	@for port in 8000 8001; do \
	    pids=$$(lsof -ti:$$port 2>/dev/null || true); \
	    if [ -n "$$pids" ]; then \
	        echo "  Killing stale process(es) on port $$port: $$pids"; \
	        kill $$pids 2>/dev/null || true; \
	        sleep 2; \
	        kill -9 $$pids 2>/dev/null || true; \
	    fi; \
	done
	@rm -f $(PIDS_DIR)/rule_engine.pid $(PIDS_DIR)/rag_pipeline.pid 2>/dev/null || true
	@echo "==> [1/6] Wipe ChromaDB + results..."
	rm -rf rag_pipeline/chroma_db/ evaluation/results/
	@echo "==> [2/6] Re-ingest PDFs (v2: anchored+sentence-aware)..."
	$(MAKE) ingest-v2
	@echo "==> [3/6] Run unit tests..."
	$(MAKE) test-local
	@echo "==> [4/6] Rule engine evaluation..."
	$(MAKE) eval-rule-engine
	@echo "==> [5/6] Starting services + readiness check..."
	$(MAKE) up-local
	@echo "Waiting for orchestrator at $(ORCHESTRATOR_URL)$(HEALTH_ENDPOINT)..."
	@ready=0; \
	for i in $$(seq 1 $(READINESS_TIMEOUT)); do \
	    if curl -sf $(ORCHESTRATOR_URL)$(HEALTH_ENDPOINT) > /dev/null 2>&1; then \
	        echo "Orchestrator ready after $$i seconds."; \
	        ready=1; \
	        break; \
	    fi; \
	    sleep 1; \
	done; \
	if [ $$ready -eq 0 ]; then \
	    echo "ERROR: Orchestrator not ready after $(READINESS_TIMEOUT)s. Aborting."; \
	    $(MAKE) down-local; \
	    exit 1; \
	fi
	$(MAKE) eval-pipeline
	$(MAKE) down-local
	@echo "==> [6/6] Retrieval metrics..."
	$(MAKE) eval-retrieval
	@echo "==> Clean-room verification COMPLETE (all gates passed)."

# ── NLI / Italian-similarity comparison (M3 + M3-bis ablation) ───────────────
.PHONY: eval-nli-compare eval-nli-old eval-nli-new eval-ssim-italian

# Default model IDs — override via env: NLI_OLD_ID=... NLI_NEW_ID=...
NLI_OLD_ID ?= MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
NLI_NEW_ID ?= MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
SSIM_IT_ID ?= nickprock/cross-encoder-italian-bert-stsb

eval-nli-old:
	@echo "==> NLI (old, multilingue): $(NLI_OLD_ID)"
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.semantic_faithfulness_v2 \
		--model-id "$(NLI_OLD_ID)" \
		--output evaluation/results/semantic_faithfulness_v2_mlaurer_old.json

eval-nli-new:
	@echo "==> NLI (new, multilingue 2mil7): $(NLI_NEW_ID)"
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.semantic_faithfulness_v2 \
		--model-id "$(NLI_NEW_ID)" \
		--output evaluation/results/semantic_faithfulness_v2_mlaurer_2mil7.json

eval-ssim-italian:
	@echo "==> Italian STSB cross-encoder similarity: $(SSIM_IT_ID)"
	$(RULE_ENG_VENV)/bin/python -m evaluation.metrics.semantic_similarity_italian \
		--model-id "$(SSIM_IT_ID)" \
		--output evaluation/results/semantic_similarity_italian.json

eval-nli-compare: eval-nli-old eval-nli-new eval-ssim-italian
	@echo "==> Building comparison summary..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.compare_nli_models
	@echo "==> See evaluation/results/nli_comparison_summary.md"

# ── Excellence Plan — Fase 5 evaluation extensions ──────────────────────────
.PHONY: eval-non-determinable eval-ales-sensitivity eval-boundary-report eval-extensions

eval-non-determinable:
	@echo "==> NON_DETERMINABILE precision/recall analysis (brief: dichiarazione esplicita di insufficienza dati)..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.non_determinable_analysis

eval-ales-sensitivity:
	@echo "==> ALES sensitivity (perturb each weight by ±0.10, ±0.05) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.ales_sensitivity

eval-boundary-report:
	@echo "==> Boundary perturbation summary (CHA2DS2-VASc, eta, VFG, peso) ..."
	$(RULE_ENG_VENV)/bin/python -m evaluation.scripts.boundary_report

eval-extensions: eval-non-determinable eval-ales-sensitivity eval-boundary-report
	@echo "==> All Excellence Plan Fase 5 reports generated."

# ── Demo Streamlit ───────────────────────────────────────────────────────────

demo-install:
	@echo "==> Installing demo dependencies into the rule engine venv..."
	$(RULE_ENG_VENV)/bin/pip install -r demo/requirements_demo.txt

demo:
	@echo "==> Avvio demo Streamlit (presuppone: make up-local + Ollama attivi)"
	$(RULE_ENG_VENV)/bin/streamlit run demo/app.py --server.port 8501
