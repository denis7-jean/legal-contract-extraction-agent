"""FastAPI TestClient integration tests — no LLM calls, no live Phoenix required."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from legal_agent.api.main import app

client = TestClient(app)


@pytest.mark.integration
def test_health_endpoint_returns_200() -> None:
    """GET /health returns HTTP 200 with a valid HealthResponse body."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "version" in data
    assert "phoenix_connected" in data


@pytest.mark.integration
def test_health_endpoint_schema() -> None:
    """HealthResponse fields have the expected types."""
    response = client.get("/health")
    data = response.json()
    assert isinstance(data["phoenix_connected"], bool)
    assert isinstance(data["version"], str)


@pytest.mark.integration
def test_metrics_endpoint_returns_200() -> None:
    """GET /metrics returns HTTP 200."""
    response = client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.integration
def test_metrics_content_type_is_prometheus() -> None:
    """GET /metrics content-type is text/plain (Prometheus exposition format)."""
    response = client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.integration
def test_metrics_contains_required_counters() -> None:
    """Prometheus metric names are present in the /metrics response body."""
    response = client.get("/metrics")
    body = response.text
    assert "legal_agent_requests_total" in body
    assert "legal_agent_errors_total" in body
    assert "legal_agent_processing_time_seconds" in body


@pytest.mark.integration
def test_extract_endpoint_rejects_short_text() -> None:
    """POST /extract with text shorter than min_length=100 must return 422."""
    response = client.post(
        "/extract",
        json={"contract_text": "too short"},
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_extract_endpoint_rejects_missing_body() -> None:
    """POST /extract with no contract_text field must return 422."""
    response = client.post("/extract", json={})
    assert response.status_code == 422


@pytest.mark.integration
def test_docs_endpoint_available() -> None:
    """GET /docs returns HTTP 200 — OpenAPI docs are served."""
    response = client.get("/docs")
    assert response.status_code == 200
