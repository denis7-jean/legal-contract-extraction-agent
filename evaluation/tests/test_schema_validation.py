"""Schema validation tests — confirms ExtractionResult schema is always well-formed."""
from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from evaluation.sample_contracts import (
    SAMPLE_CLEAN_CONTRACT,
    SAMPLE_HIGH_RISK_CONTRACT,
    SAMPLE_MFN_CONTRACT,
)
from legal_agent.schemas.legal import ExtractionResult, LegalContract, RiskLevel

_SAMPLE_CONTRACTS: list[str] = [
    SAMPLE_CLEAN_CONTRACT,
    SAMPLE_HIGH_RISK_CONTRACT,
    SAMPLE_MFN_CONTRACT,
]


@pytest.mark.llm
@pytest.mark.asyncio
def test_extraction_result_always_valid_schema() -> None:
    """ExtractionResult from all sample contracts is schema-valid and round-trips through JSON."""
    import time
    from pydantic_ai.exceptions import ModelHTTPError
    from legal_agent.agent.runner import run_extraction
    try:
        for contract_text in _SAMPLE_CONTRACTS:
            result = asyncio.run(run_extraction(contract_text))
            assert isinstance(result, ExtractionResult)
            assert isinstance(result.contract.parties, list)
            assert len(result.contract.parties) >= 1
            assert 0.0 <= result.confidence_score <= 1.0
            assert isinstance(result.overall_risk_level, RiskLevel)
            assert isinstance(result.risk_flags, list)
            assert isinstance(result.is_successful, bool)
            ExtractionResult.model_validate_json(result.model_dump_json())
            time.sleep(3)  # avoid 429 rate limit between consecutive calls
    except ModelHTTPError as exc:
        if "429" in str(exc):
            pytest.skip(f"OpenAI rate limit hit during schema validation: {exc}")
        raise


@pytest.mark.llm
def test_schema_rejects_empty_parties() -> None:
    """Field(min_length=1) on parties is enforced — ValidationError on empty list."""
    with pytest.raises(ValidationError):
        LegalContract(
            document_name="Test Contract",
            parties=[],
            effective_date=None,
            expiration_date=None,
            governing_law=None,
            agreement_type="Test",
            renewal_term=None,
            limitation_of_liability=None,
            termination_for_convenience=False,
            most_favored_nation=False,
            raw_text_excerpt="Test excerpt.",
        )


@pytest.mark.llm
@pytest.mark.asyncio
def test_confidence_score_bounds() -> None:
    """Agent-returned confidence_score is always within [0.0, 1.0]."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    assert result.confidence_score >= 0.0
    assert result.confidence_score <= 1.0


@pytest.mark.llm
@pytest.mark.asyncio
def test_risk_level_is_valid_enum() -> None:
    """overall_risk_level and every risk flag's risk_level are valid RiskLevel values."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_HIGH_RISK_CONTRACT))
    assert result.overall_risk_level in list(RiskLevel)
    assert all(f.risk_level in list(RiskLevel) for f in result.risk_flags)


@pytest.mark.llm
@pytest.mark.asyncio
def test_processing_time_recorded() -> None:
    """Agent records a non-negative integer processing_time_ms in every response."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    assert result.processing_time_ms >= 0
    assert isinstance(result.processing_time_ms, int)

