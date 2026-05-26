# Legal & Compliance Document Extraction Agent

## Production-Grade LLMOps Pipeline

### Project identity

An end-to-end agentic pipeline that extracts structured legal entities
and clauses from unstructured contract text into a strict Pydantic JSON
schema — evaluated against CUAD, served via FastAPI, and orchestrated
by n8n.

---

### Architecture overview

Three fully decoupled layers. Each layer can be tested, deployed, and
scaled independently.

#### Layer 1 — Data & evaluation

- Ground truth: CUAD (theatticusproject/cuad-qa), 20-contract eval subset
- ETL: scripts/prepare_cuad_data.py → data/eval_dataset.json
- Evaluation: DeepEval (pytest) with four hard thresholds:

    Hallucination     0.0   (zero tolerance on legal entities)
    Answer relevancy  ≥0.85
    Faithfulness      ≥0.90
    Schema pass rate  100%  (every response must parse into ExtractionResult)

- CI gate: GitHub Actions eval-gate job blocks all merges on failure

#### Layer 2 — Core AI microservice (FastAPI + PydanticAI)

- FastAPI app at src/legal_agent/api/

    POST /extract        single contract text → ExtractionResult JSON
    POST /extract/batch  list of contracts → list[ExtractionResult]
    GET  /health         liveness probe for n8n and k8s
    GET  /metrics        Prometheus-compatible counters

- PydanticAI agent with three tools:

    extract_entities     NER pass for parties, dates, jurisdiction
    validate_clauses     deterministic clause presence check (no LLM)
    flag_risk            rule-based risk scoring on ExtractionResult

- Strict output: result_type=ExtractionResult enforced by PydanticAI
- Observability: Arize Phoenix via OTLP — every tool call is a span

#### Layer 3 — Automation & orchestration (n8n)

- Trigger: Google Drive upload webhook or scheduled cron
- Step 1: extract raw text from uploaded document
- Step 2: POST to FastAPI /extract endpoint
- Step 3: parse ExtractionResult JSON payload
- Step 4: Switch node on risk_flags field

    HIGH RISK → Slack/Email escalation with clause summary
    CLEAN     → persist to vector DB (pgvector/Pinecone) + relational DB

---

### Repository layout

```
src/legal_agent/
  schemas/        Pydantic models — LegalContract, ExtractionResult, RiskFlag
  services/       Pure deterministic Python — clause validators, risk scorer
  agent/          PydanticAI agent, tools, runner, system prompts
  api/            FastAPI app, routers, request/response models
  observability/  Arize Phoenix + OpenTelemetry setup

scripts/
  prepare_cuad_data.py   ETL v1.4.0 — CUAD → data/eval_dataset.json

data/
  eval_dataset.json      Runtime only — gitignored — never hand-edited

evaluation/
  golden_dataset/        CUAD-derived JSONL ground truth
  tests/
    test_extraction_logic.py    Pure pytest — services/ only — no LLM
    test_hallucination.py       DeepEval @pytest.mark.llm
    test_answer_relevance.py    DeepEval @pytest.mark.llm
    test_schema_validation.py   DeepEval @pytest.mark.llm
    test_api_integration.py     FastAPI TestClient — no LLM
  conftest.py

n8n/
  contract_extraction_workflow.json
  dataset_refresh_workflow.json

.github/workflows/
  eval-ci.yml
  dataset-refresh.yml
```

---

### Sprint map

```
Sprint 1 ✅  ETL pipeline — CUAD → eval_dataset.json (COMPLETE)
Sprint 2     Pydantic schemas + FastAPI skeleton + PydanticAI agent core
Sprint 3     DeepEval test suite wired to agent (hallucination gate)
Sprint 4     Arize Phoenix observability instrumentation
Sprint 5     n8n workflow + end-to-end integration test
Sprint 6     GitHub Actions CI/CD + deployment hardening
```

---

### Quick start

```bash
pip install -e ".[dev]"          # installs pinned deps incl. datasets==2.14.6
cp .env.example .env             # fill OPENAI_API_KEY, PHOENIX_*
python scripts/prepare_cuad_data.py          # regenerate eval dataset
pytest evaluation/tests/test_extraction_logic.py -v  # fast, no LLM
uvicorn legal_agent.api.main:app --reload    # start FastAPI dev server
pytest evaluation/ -m llm                   # full DeepEval eval suite
```

---

### Dependency pins (do not remove without reading comments in pyproject.toml)

| Package | Pin | Reason |
|---|---|---|
| `datasets==2.14.6` | exact | theatticusproject/cuad-qa requires legacy loader |
| `pyarrow>=12.0.0,<14.0.0` | range | pyarrow>=14 removed PyExtensionType |
| `numpy>=1.24.0,<2.0.0` | range | numpy>=2.0 removed numpy.core.multiarray |

All three pins can be removed together when cuad-qa migrates to Parquet.
