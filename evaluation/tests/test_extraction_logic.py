"""Pure pytest tests for services/validators.py — zero LLM calls, zero network I/O."""
from __future__ import annotations

import pytest

from legal_agent.schemas.legal import ExtractionResult, LegalContract, Party, RiskLevel
from legal_agent.services.validators import (
    check_required_fields,
    compute_overall_risk,
    run_full_validation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(**overrides: object) -> LegalContract:
    """Build a fully populated LegalContract, applying keyword overrides."""
    defaults: dict[str, object] = {
        "document_name": "Test Services Agreement",
        "parties": [
            Party(name="Acme Corp", role="buyer"),
            Party(name="SupplyCo Ltd", role="seller"),
        ],
        "effective_date": "2024-01-15",
        "expiration_date": "2025-01-15",
        "governing_law": "State of Delaware",
        "agreement_type": "Services Agreement",
        "renewal_term": None,
        "limitation_of_liability": (
            "Liability capped at total fees paid in prior 12 months under this agreement."
        ),
        "termination_for_convenience": True,
        "most_favored_nation": False,
        "raw_text_excerpt": "This Services Agreement is entered into...",
    }
    defaults.update(overrides)
    return LegalContract(**defaults)  # type: ignore[arg-type]


def _make_extraction_result(contract: LegalContract) -> ExtractionResult:
    """Build a minimal valid ExtractionResult wrapping the given contract."""
    return ExtractionResult(
        contract=contract,
        is_successful=True,
        risk_flags=[],
        overall_risk_level=RiskLevel.LOW,
        confidence_score=0.95,
        extraction_warnings=[],
        model_used="gpt-4o",
        processing_time_ms=1234,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_contract() -> LegalContract:
    """A fully populated contract with no risk indicators."""
    return _make_contract()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_risk_flags_on_clean_contract(clean_contract: LegalContract) -> None:
    """A contract with all fields present and correct clauses produces no flags."""
    flags, risk, warnings = run_full_validation(clean_contract)
    assert flags == []
    assert risk == RiskLevel.LOW
    assert warnings == []


def test_missing_lol_generates_high_risk(clean_contract: LegalContract) -> None:
    """Absent limitation_of_liability clause produces a HIGH risk flag."""
    contract = clean_contract.model_copy(update={"limitation_of_liability": None})
    flags, _, _ = run_full_validation(contract)
    assert any(f.risk_level == RiskLevel.HIGH for f in flags)


def test_short_lol_generates_medium_risk(clean_contract: LegalContract) -> None:
    """A very short limitation_of_liability clause (< 50 chars) produces MEDIUM risk."""
    contract = clean_contract.model_copy(update={"limitation_of_liability": "Liability is capped."})
    flags, _, _ = run_full_validation(contract)
    assert any(
        f.clause_type == "limitation_of_liability" and f.risk_level == RiskLevel.MEDIUM
        for f in flags
    )


def test_missing_governing_law_generates_warning(clean_contract: LegalContract) -> None:
    """A contract missing governing_law produces at least one warning string."""
    contract = clean_contract.model_copy(update={"governing_law": None})
    warnings = check_required_fields(contract)
    assert len(warnings) > 0
    assert any("governing_law" in w for w in warnings)


def test_no_termination_clause_generates_medium_flag(clean_contract: LegalContract) -> None:
    """Absent termination_for_convenience clause produces a MEDIUM risk flag."""
    contract = clean_contract.model_copy(update={"termination_for_convenience": False})
    flags, _, _ = run_full_validation(contract)
    assert any(
        f.clause_type == "termination_for_convenience" and f.risk_level == RiskLevel.MEDIUM
        for f in flags
    )


def test_mfn_clause_generates_medium_flag(clean_contract: LegalContract) -> None:
    """Presence of an MFN clause produces a MEDIUM risk flag."""
    contract = clean_contract.model_copy(update={"most_favored_nation": True})
    flags, _, _ = run_full_validation(contract)
    assert any(
        f.clause_type == "most_favored_nation" and f.risk_level == RiskLevel.MEDIUM
        for f in flags
    )


def test_multiple_risks_escalate_to_highest(clean_contract: LegalContract) -> None:
    """HIGH risk flag dominates even when other flags are MEDIUM."""
    contract = clean_contract.model_copy(
        update={"limitation_of_liability": None, "termination_for_convenience": False}
    )
    _, overall, _ = run_full_validation(contract)
    assert overall == RiskLevel.HIGH


def test_compute_overall_risk_empty_flags() -> None:
    """No flags produces LOW overall risk."""
    assert compute_overall_risk([]) == RiskLevel.LOW


def test_jurisdiction_stays_none_without_hallucination(clean_contract: LegalContract) -> None:
    """Missing governing_law produces a warning mentioning 'governing_law'."""
    contract = clean_contract.model_copy(update={"governing_law": None})
    warnings = check_required_fields(contract)
    assert warnings, "expected at least one warning"
    assert "governing_law" in warnings[0]


def test_extraction_result_schema_round_trip(clean_contract: LegalContract) -> None:
    """ExtractionResult serialises to JSON and reconstructs identically."""
    result = _make_extraction_result(clean_contract)
    json_str = result.model_dump_json()
    reconstructed = ExtractionResult.model_validate_json(json_str)
    assert reconstructed == result
