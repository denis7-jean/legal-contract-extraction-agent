"""FastAPI application for the legal entity extraction service."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from legal_agent.agent.runner import run_extraction
from legal_agent.api.models import BatchExtractionRequest, ExtractionRequest, HealthResponse
from legal_agent.observability.tracing import configure_tracing
from legal_agent.schemas.legal import ExtractionResult

_logger = logging.getLogger(__name__)

REQUEST_COUNTER: Counter = Counter(
    "legal_agent_requests_total",
    "Total extraction requests received",
    ["endpoint", "status"],
)
ERROR_COUNTER: Counter = Counter(
    "legal_agent_errors_total",
    "Total extraction errors",
    ["endpoint", "error_type"],
)
PROCESSING_TIME: Histogram = Histogram(
    "legal_agent_processing_time_seconds",
    "Extraction processing time in seconds",
    ["endpoint"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)


def _check_phoenix_connection() -> bool:
    """Return True if the Phoenix collector endpoint responds with HTTP 200.

    Returns:
        True if reachable, False if the env var is unset or the request fails.
    """
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    if not endpoint:
        return False
    try:
        with urllib.request.urlopen(f"{endpoint}/healthz", timeout=2) as resp:
            return bool(resp.status == 200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure tracing once on application startup."""
    configure_tracing()
    yield


app = FastAPI(
    title="Legal Extraction Agent API",
    description="Extracts structured legal entities from contract text.",
    version="1.0.0",
    lifespan=_lifespan,
)


@app.middleware("http")
async def _log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log HTTP method, path, and response time for every request."""
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _logger.info("%s %s %dms", request.method, request.url.path, elapsed_ms)
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — reports Phoenix connectivity status."""
    phoenix_ok = _check_phoenix_connection()
    return HealthResponse(
        status="ok" if phoenix_ok else "degraded",
        phoenix_connected=phoenix_ok,
    )


@app.post("/extract", response_model=ExtractionResult)
async def extract(request: ExtractionRequest) -> ExtractionResult:
    """Extract structured legal entities from a single contract text.

    Args:
        request: ExtractionRequest containing the raw contract text.

    Returns:
        ExtractionResult with validated schema, risk flags, and confidence score.
    """
    try:
        with PROCESSING_TIME.labels(endpoint="/extract").time():
            result = await run_extraction(request.contract_text)
        REQUEST_COUNTER.labels(endpoint="/extract", status="success").inc()
        return result
    except Exception as exc:
        ERROR_COUNTER.labels(endpoint="/extract", error_type=type(exc).__name__).inc()
        REQUEST_COUNTER.labels(endpoint="/extract", status="error").inc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint — scraped by monitoring stack."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/extract/batch", response_model=list[ExtractionResult])
async def extract_batch(request: BatchExtractionRequest) -> list[ExtractionResult]:
    """Extract legal entities from a batch of contracts concurrently.

    Args:
        request: BatchExtractionRequest with 1–50 contracts.

    Returns:
        List of ExtractionResult objects in the same order as the input.
    """
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(run_extraction(c.contract_text)) for c in request.contracts]
    return [t.result() for t in tasks]
