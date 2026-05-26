"""Pydantic models for the legal extraction domain — schemas only, no logic."""
from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """Severity levels for identified contract risk flags."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskFlag(BaseModel):
    """A single identified risk associated with a contract clause."""

    model_config = ConfigDict(strict=True, frozen=True)

    clause_type: str
    risk_level: RiskLevel
    reason: str
    suggested_action: str


class Party(BaseModel):
    """A named party in a legal contract with an inferred role."""

    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    role: Literal[
        "buyer",
        "seller",
        "licensor",
        "licensee",
        "employer",
        "employee",
        "lender",
        "borrower",
        "lessor",
        "lessee",
        "unknown",
    ]


class LegalContract(BaseModel):
    """Structured representation of extracted legal contract entities."""

    model_config = ConfigDict(strict=True, frozen=True)

    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    document_name: str
    parties: list[Party] = Field(min_length=1)
    effective_date: str | None
    expiration_date: str | None
    governing_law: str | None
    agreement_type: str
    renewal_term: str | None
    limitation_of_liability: str | None
    termination_for_convenience: bool
    most_favored_nation: bool
    raw_text_excerpt: str


class ExtractionResult(BaseModel):
    """Full output of the legal extraction agent for a single contract."""

    model_config = ConfigDict(strict=True, frozen=True)

    contract: LegalContract
    is_successful: bool
    risk_flags: list[RiskFlag]
    overall_risk_level: RiskLevel
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_warnings: list[str]
    model_used: str
    processing_time_ms: int
