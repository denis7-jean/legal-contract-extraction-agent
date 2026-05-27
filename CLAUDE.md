# CLAUDE.md — Project context for claude-code

## Project identity
Name: Legal & Compliance Document Extraction Agent
Purpose: An agentic LLMOps pipeline that extracts structured legal entities and clauses from unstructured contract text into a strict Pydantic JSON schema, evaluated against the CUAD dataset.
Status: Active development. Domain pivoted from PC Config Agent. All PC-related code is obsolete — do not reference or regenerate it.

## Sprint map
Sprint 1 ✅  CUAD ETL pipeline (scripts/prepare_cuad_data.py → data/eval_dataset.json)
Sprint 2 ✅  Core implementation — schemas, services, PydanticAI agent, FastAPI API
Sprint 3 ✅  DeepEval hallucination / relevance / faithfulness test suite
Sprint 4 ✅  Arize Phoenix observability + Prometheus metrics (COMPLETE)
             - mypy clean, 24 not-llm passed, 14 integration passed
Sprint 5 🔄  n8n workflow + end-to-end integration test (IN PROGRESS)
             - n8n contract_extraction_workflow.json
             - Webhook trigger → FastAPI /extract → risk routing
             - Slack escalation on HIGH risk, DB persist on CLEAN
             - test_e2e_integration.py with FastAPI TestClient

## Repository layout
src/legal_agent/    # Importable package name: legal_agent  (installed via pip install -e ".")
  schemas/          # Pydantic models only — no logic
  services/         # Pure deterministic Python — zero LLM calls, zero network I/O
  agent/            # PydanticAI agent, tools, runner, prompts
  observability/    # Arize Phoenix + OpenTelemetry tracing
evaluation/
  golden_dataset/   # CUAD-derived JSONL ground truth
  tests/            # pytest + DeepEval test suites
scripts/            # — standalone executable scripts only. No __init__.py. Not an importable package.
  prepare_cuad_data.py  # ETL: CUAD → data/eval_dataset.json
data/
  eval_dataset.json     # Output of ETL script — gitignored, never hand-edited
n8n/                    # Workflow JSONs for dataset refresh orchestration
.github/workflows/      # eval-ci.yml and dataset-refresh.yml

## Ground truth dataset
Source: HuggingFace Hub — theatticusproject/cuad
Load with: from datasets import load_dataset; ds = load_dataset("theatticusproject/cuad")
The nine CUAD questions we extract are:
  "Parties", "Effective Date", "Expiration Date", "Governing Law",
  "Document Name", "Renewal Term", "Cap On Liability",
  "Termination For Convenience", "Most Favored Nation"
The ETL output lives at data/eval_dataset.json and follows the EvalDataset Pydantic schema.
Never modify data/eval_dataset.json by hand.

## Non-negotiable coding standards
These apply to every file claude-code generates. Deviation is a bug.
- Python 3.11+. Use `from __future__ import annotations` in every file.
- Full type annotations on every function parameter and return value. No `Any`. No untyped dicts — use TypedDict or Pydantic models.
- No bare `except:`. Always catch a specific exception type.
- All Pydantic models: `model_config = ConfigDict(strict=True, frozen=True)` unless there is an explicit documented reason to deviate.
- mypy strict must pass on all files in src/. Run mentally before outputting.
- Ruff line length: 100. No unused imports.
- Docstrings on every public function and class. Format: one-line summary, then Args/Returns if non-trivial.

## Evaluation-driven development (EDD) contract
This is the core architectural rule — never violate it:
1. evaluation/tests/test_*_logic.py files: pure pytest only. Zero LLM calls. Zero network I/O. Must run in under 60 seconds. These test services/ only.
2. evaluation/tests/test_hallucination.py and test_answer_relevance.py: use DeepEval. Always marked @pytest.mark.llm. These are the only files that may call the agent runner.
3. evaluation/ must never import from src/legal_agent/agent/ except in @pytest.mark.llm test files.
4. services/ must never import from agent/. One-way dependency only.
5. The CI eval gate (eval-ci.yml job: eval-gate) blocks all merges if any DeepEval metric fails.

## DeepEval targets (hard thresholds — CI will fail below these)
- HallucinationMetric: threshold=0.0 (zero tolerance on legal entities)
- AnswerRelevancyMetric: threshold=0.85
- FaithfulnessMetric: threshold=0.90
- Schema validation pass rate: 100% (every agent response must parse into ExtractionResult)
Critical entities for exact-match evaluation: document_name, parties[].name, effective_date, governing_law.

## Tech stack
Runtime: pydantic-ai, pydantic>=2.7, openai, arize-phoenix-otel, opentelemetry-sdk, datasets
Dev/eval: deepeval, pytest, pytest-asyncio, mypy, ruff, python-dotenv
Do not add dependencies outside this list without a comment explaining why.

## Environment variables
All secrets live in .env (gitignored). Copy from .env.example.
Required: OPENAI_API_KEY, PHOENIX_API_KEY, PHOENIX_COLLECTOR_ENDPOINT
Never hardcode secrets. Never print them to stdout.

## Commands reference
Install:           pip install -e ".[dev]"
Fast tests:        pytest evaluation/tests/test_*_logic.py -v
LLM eval tests:    pytest evaluation/ -m llm
Integration:       pytest evaluation/ -m integration
Type check:        mypy src/ --strict
Lint:              ruff check src/ evaluation/ scripts/
Run ETL:           python scripts/prepare_cuad_data.py
Start Phoenix:     python -m phoenix.server.main serve

## Sprint 4 — Observability contract
These rules apply to all Sprint 4 files. Deviation is a bug.

- Phoenix runs locally via: python -m phoenix.server.main serve
  It exposes the OTLP collector at localhost:6006/v1/traces
  and the UI at localhost:6006. Both must be reachable before
  running integration tests.

- configure_tracing() in tracing.py is already implemented and
  idempotent. Do not rewrite it. Do not add a second TracerProvider.

- @trace_tool is already implemented in tracing.py. Apply it to
  every tool in agent/tools.py if not already applied.

- Every span must record these minimum attributes:
    tool.name, tool.input (truncated 500 chars), tool.output
    (truncated 500 chars), agent.config_id, agent.prompt_length

- The FastAPI /metrics endpoint must return Prometheus text format
  (content-type: text/plain; version=0.0.4) with these counters:
    legal_agent_requests_total
    legal_agent_errors_total
    legal_agent_processing_time_seconds (histogram)
  Use the prometheus_client library. Add it to pyproject.toml deps.

- test_api_integration.py uses FastAPI TestClient only — no live
  Phoenix required, no LLM calls. Mark with @pytest.mark.integration.

- test_observability.py verifies span emission using an in-memory
  SpanExporter — no live Phoenix required for unit testing.

## What claude-code should never do
- Generate any PC hardware, GPU, CPU, or motherboard related code. That domain is abandoned.
- Use Optional[X] — use X | None instead (Python 3.10+ union syntax).
- Create God classes or functions longer than 60 lines. Decompose instead.
- Skip error handling on any HuggingFace dataset load or file I/O operation.
- Add print statements in src/ — use Python's logging module with a named logger.
- Invent CUAD question strings from memory — always refer to the nine listed above.
- Commit anything under data/ — that directory is gitignored and runtime-only.
- Call configure_tracing() more than once per process — the guard
  flag _tracing_configured handles idempotency already.
- Create a second TracerProvider or a second BatchSpanProcessor —
  one of each is registered at startup, never duplicated.
- Use print() for span debug output — use the named logger
  from Python logging module only.