"""PydanticAI tool functions for the legal extraction agent."""
from __future__ import annotations

import re

from legal_agent.observability.tracing import trace_tool
from legal_agent.schemas.legal import ExtractionResult
from legal_agent.services.validators import run_full_validation

_JURISDICTION_ALIASES: dict[str, str] = {
    "NY": "State of New York",
    "CA": "State of California",
    "DE": "State of Delaware",
    "TX": "State of Texas",
    "England": "England and Wales",
    "UK": "England and Wales",
}


@trace_tool
async def extract_entities(contract_text: str) -> dict[str, object]:
    """Run fast heuristic pre-pass on contract text to provide structured hints to the LLM.

    Extracts lightweight signals (text excerpt, char count, regex pattern flags) that
    help the LLM focus its extraction before reading the full contract.

    Args:
        contract_text: Raw unstructured contract text.

    Returns:
        Dict of extracted hints: text_excerpt, char_count, and three boolean flags.
    """
    has_date = bool(re.search(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}", contract_text))
    has_jurisdiction = bool(re.search(r"(?i)(state of|laws of|governed by)", contract_text))
    has_party = bool(re.search(r"(?i)(between|party|parties|agreement by)", contract_text))
    return {
        "text_excerpt": contract_text[:1000],
        "char_count": len(contract_text),
        "has_date_pattern": has_date,
        "has_jurisdiction_hint": has_jurisdiction,
        "has_party_hint": has_party,
    }


@trace_tool
async def validate_clauses(extraction_result_json: str) -> dict[str, object]:
    """Validate extracted clauses and compute risk flags.

    Args:
        extraction_result_json: JSON string of a complete ExtractionResult.
    Returns:
        Dict with risk_flags, overall_risk_level, warnings, and any error.
    """
    from pydantic import ValidationError
    try:
        result = ExtractionResult.model_validate_json(extraction_result_json)
        flags, overall_risk, warnings = run_full_validation(result.contract)
        return {
            "risk_flags": [f.model_dump() for f in flags],
            "overall_risk_level": overall_risk.value,
            "warnings": warnings,
            "error": None,
        }
    except ValidationError as exc:
        # Return structured error — do not raise. The agent will see
        # the error field and can request a corrected extraction.
        return {
            "risk_flags": [],
            "overall_risk_level": "unknown",
            "warnings": [],
            "error": (
                f"Invalid ExtractionResult JSON: {exc.error_count()} "
                f"validation errors. Call extract_entities first and "
                f"ensure all required fields are populated before "
                f"calling validate_clauses."
            ),
        }


@trace_tool
async def lookup_jurisdiction_aliases(raw_jurisdiction: str) -> dict[str, object]:
    """Map common jurisdiction abbreviations to their canonical legal forms.

    Uses a hardcoded lookup table. Returns the raw value unchanged if no alias
    is found.

    Args:
        raw_jurisdiction: Raw jurisdiction string extracted from the contract.

    Returns:
        Dict with canonical (str) and was_aliased (bool).
    """
    canonical = _JURISDICTION_ALIASES.get(raw_jurisdiction)
    if canonical is not None:
        return {"canonical": canonical, "was_aliased": True}
    return {"canonical": raw_jurisdiction, "was_aliased": False}
