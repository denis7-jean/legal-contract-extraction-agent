"""FastAPI request and response models for the legal extraction API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionRequest(BaseModel):
    """Request body for a single contract extraction."""

    model_config = ConfigDict(strict=True, frozen=True)

    contract_text: str = Field(min_length=100)
    contract_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class BatchExtractionRequest(BaseModel):
    """Request body for batch contract extraction (up to 50 contracts)."""

    model_config = ConfigDict(strict=True, frozen=True)

    contracts: list[ExtractionRequest] = Field(min_length=1, max_length=50)


class HealthResponse(BaseModel):
    """Response body for the /health liveness probe."""

    model_config = ConfigDict(strict=True, frozen=True)

    status: Literal["ok", "degraded"]
    version: str = "1.0.0"
    phoenix_connected: bool
