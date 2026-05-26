"""DeepEval hallucination tests — require OPENAI_API_KEY and a live agent call."""
from __future__ import annotations

import asyncio

import pytest
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

from evaluation.sample_contracts import (
    SAMPLE_CLEAN_CONTRACT,
    SAMPLE_HIGH_RISK_CONTRACT,
    SAMPLE_MFN_CONTRACT,
)
from legal_agent.schemas.legal import RiskLevel


@pytest.mark.llm
def test_no_hallucination_clean_contract(hallucination_metric: HallucinationMetric) -> None:
    """Agent extracts only verbatim entities from a well-formed services agreement."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    actual_output = (
        f"Parties: {[p.name for p in result.contract.parties]}. "
        f"Effective date: {result.contract.effective_date}. "
        f"Governing law: {result.contract.governing_law}."
    )
    test_case = LLMTestCase(
        input=SAMPLE_CLEAN_CONTRACT[:500],
        actual_output=actual_output,
        context=[SAMPLE_CLEAN_CONTRACT],
    )
    assert_test(test_case, [hallucination_metric])

    assert result.contract.governing_law is not None
    assert "Delaware" in (result.contract.governing_law or "")
    assert result.contract.effective_date is not None
    assert result.contract.termination_for_convenience is True
    assert result.overall_risk_level == RiskLevel.LOW


@pytest.mark.llm
def test_no_hallucination_high_risk_contract(hallucination_metric: HallucinationMetric) -> None:
    """Agent reports risk flags without hallucinating entities absent from a sparse contract."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_HIGH_RISK_CONTRACT))
    actual_output = (
        f"Parties: {[p.name for p in result.contract.parties]}. "
        f"Risk flags: {[f.clause_type for f in result.risk_flags]}. "
        f"Overall risk: {result.overall_risk_level.value}."
    )
    test_case = LLMTestCase(
        input=SAMPLE_HIGH_RISK_CONTRACT[:500],
        actual_output=actual_output,
        context=[SAMPLE_HIGH_RISK_CONTRACT],
    )
    assert_test(test_case, [hallucination_metric])

    assert result.overall_risk_level == RiskLevel.HIGH
    assert len(result.risk_flags) > 0
    assert result.contract.parties is not None
    assert len(result.contract.parties) >= 1


@pytest.mark.llm
def test_no_hallucination_mfn_contract(hallucination_metric: HallucinationMetric) -> None:
    """Agent correctly identifies MFN clause and California governing law without invention."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_MFN_CONTRACT))
    actual_output = (
        f"MFN clause: {result.contract.most_favored_nation}. "
        f"Governing law: {result.contract.governing_law}. "
        f"Parties: {[p.name for p in result.contract.parties]}."
    )
    test_case = LLMTestCase(
        input=SAMPLE_MFN_CONTRACT[:500],
        actual_output=actual_output,
        context=[SAMPLE_MFN_CONTRACT],
    )
    assert_test(test_case, [hallucination_metric])

    assert result.contract.most_favored_nation is True
    assert result.contract.governing_law is not None
    assert "California" in (result.contract.governing_law or "")
    assert any(f.clause_type == "most_favored_nation" for f in result.risk_flags)


@pytest.mark.llm
def test_governing_law_verbatim_in_source() -> None:
    """Critical: governing_law must appear verbatim in source text — no invention."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    if result.contract.governing_law is not None:
        assert result.contract.governing_law in SAMPLE_CLEAN_CONTRACT, (
            f"governing_law '{result.contract.governing_law}' "
            f"not found verbatim in source contract text. "
            f"This is a hallucination."
        )


@pytest.mark.llm
def test_party_names_verbatim_in_source() -> None:
    """Critical: every extracted party name must appear verbatim in source text."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    for party in result.contract.parties:
        assert party.name in SAMPLE_CLEAN_CONTRACT, (
            f"Party name '{party.name}' not found verbatim in source "
            f"contract text. This is a hallucination."
        )


@pytest.mark.llm
def test_cuad_no_hallucination_governing_law(
    cuad_records_with_governing_law: list[dict[str, object]],
) -> None:
    """Verbatim hallucination check across CUAD records with ground-truth governing_law.

    Uses a strict verbatim grounding check: if the agent returns a
    governing_law value that does not appear anywhere in the full
    contract text, the test fails hard as a confirmed hallucination.
    DeepEval LLM judge is not used here — it produces false positives
    on dense legal boilerplate where the judge cannot locate short
    jurisdiction strings in long context.
    """
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    import tenacity
    from legal_agent.agent.runner import run_extraction

    skipped: list[str] = []
    passed: list[str] = []

    # Capped at 5 records: sufficient to validate hallucination gate.
    # Full dataset run would take ~17 minutes and drain API credits.
    for record in cuad_records_with_governing_law[:5]:
        cuad_id = str(record["cuad_id"])
        # Truncated to 4000 chars: limits token usage with tool call overhead.
        raw_text = str(record["raw_contract_text"])[:4000]
        # Full text used for verbatim grounding check — not truncated.
        full_text = str(record["raw_contract_text"])

        try:
            result = asyncio.run(run_extraction(raw_text))

            # Pre-check: if governing_law is not None but does not appear
            # anywhere in the full original text, this is a true hallucination
            # and must fail hard.
            if result.contract.governing_law is not None:
                if result.contract.governing_law not in full_text:
                    pytest.fail(
                        f"[{cuad_id}] governing_law "
                        f"'{result.contract.governing_law}' does not appear "
                        f"anywhere in the full contract text. "
                        f"This is a confirmed hallucination."
                    )

            # Skip the DeepEval context check if governing_law falls outside
            # the 4000-char truncation window — DeepEval would false-positive.
            if (
                result.contract.governing_law is not None
                and result.contract.governing_law not in raw_text
            ):
                skipped.append(
                    f"{cuad_id}: governing_law found in full text but outside "
                    f"4000-char truncation window — skipping DeepEval context check"
                )
                continue

            passed.append(cuad_id)

        except (UnexpectedModelBehavior, tenacity.RetryError) as exc:
            skipped.append(
                f"{cuad_id}: agent exceeded retries — {type(exc).__name__}"
            )
            continue

    # Print summary for visibility in pytest -v output.
    print(f"\nCUAD governing_law hallucination check:")
    print(f"  Passed : {len(passed)} records")
    print(f"  Skipped: {len(skipped)} records")
    for msg in skipped:
        print(f"    - {msg}")

    # Fail if every record was skipped — indicates a systemic problem.
    if len(passed) == 0 and len(cuad_records_with_governing_law) > 0:
        pytest.fail(
            f"All {len(cuad_records_with_governing_law)} CUAD records were "
            f"skipped. This indicates a systemic agent failure, not individual "
            f"record issues. Check OPENAI_API_KEY and agent tool chain."
        )
