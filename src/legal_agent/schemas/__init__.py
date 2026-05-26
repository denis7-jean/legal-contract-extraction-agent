"""Pydantic schema models for the legal extraction domain."""
from __future__ import annotations

from legal_agent.schemas.legal import ExtractionResult, LegalContract, Party, RiskFlag, RiskLevel

__all__ = ["ExtractionResult", "LegalContract", "Party", "RiskFlag", "RiskLevel"]
