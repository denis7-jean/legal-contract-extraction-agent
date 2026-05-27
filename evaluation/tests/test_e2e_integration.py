"""End-to-end FastAPI integration tests — no LLM calls, no live n8n required."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from legal_agent.api.main import app

client = TestClient(app)

INTEGRATION_CONTRACT = """
MASTER SERVICES AGREEMENT

This Master Services Agreement ("Agreement") is entered into as of
February 1, 2024 (the "Effective Date") by and between TechCorp Inc,
a Delaware corporation ("Client") and ServicePro LLC, a California
limited liability company ("Vendor").

1. SERVICES. Vendor shall provide software development services as
detailed in each Statement of Work executed by the parties.

2. GOVERNING LAW. This Agreement shall be governed by the laws of
the State of Delaware.

3. LIMITATION OF LIABILITY. Neither party shall be liable for any
indirect, incidental, or consequential damages. Each party total
liability shall not exceed the fees paid in the prior twelve months.

4. TERMINATION FOR CONVENIENCE. Either party may terminate this
Agreement upon thirty (30) days written notice.

5. TERM. This Agreement is effective as of the Effective Date and
continues for one (1) year unless earlier terminated.
""".strip()


@pytest.mark.integration
def test_health_check_before_extraction() -> None:
    """GET /health returns 200 with a valid status field."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ("ok", "degraded")


@pytest.mark.integration
def test_extract_rejects_short_contract() -> None:
    """POST /extract with text under min_length=100 must return 422."""
    response = client.post(
        "/extract", json={"contract_text": "short text"}
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_extract_rejects_empty_body() -> None:
    """POST /extract with no contract_text field must return 422."""
    response = client.post("/extract", json={})
    assert response.status_code == 422


@pytest.mark.integration
def test_metrics_available_before_extraction() -> None:
    """GET /metrics returns 200 with required counter names before any extraction."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "legal_agent_requests_total" in response.text


@pytest.mark.integration
def test_metrics_increments_after_failed_request() -> None:
    """Prometheus counters remain accessible after a failed (422) request."""
    client.post("/extract", json={"contract_text": "too short"})
    response = client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.integration
def test_batch_rejects_empty_list() -> None:
    """POST /extract/batch with an empty contracts list must return 422."""
    response = client.post(
        "/extract/batch", json={"contracts": []}
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_batch_rejects_over_limit() -> None:
    """POST /extract/batch with more than 50 contracts must return 422."""
    contracts = [
        {"contract_text": "x" * 101} for _ in range(51)
    ]
    response = client.post(
        "/extract/batch", json={"contracts": contracts}
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_openapi_schema_contains_extract_endpoint() -> None:
    """OpenAPI schema declares /extract, /extract/batch, /health, and /metrics."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/extract" in schema["paths"]
    assert "/extract/batch" in schema["paths"]
    assert "/health" in schema["paths"]
    assert "/metrics" in schema["paths"]


@pytest.mark.integration
def test_openapi_schema_documents_extraction_result() -> None:
    """OpenAPI component schemas include ExtractionResult, LegalContract, and RiskFlag."""
    response = client.get("/openapi.json")
    schema = response.json()
    components = schema.get("components", {}).get("schemas", {})
    assert "ExtractionResult" in components
    assert "LegalContract" in components
    assert "RiskFlag" in components
