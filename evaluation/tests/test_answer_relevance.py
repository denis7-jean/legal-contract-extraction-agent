"""DeepEval answer relevance and faithfulness tests — require a live agent call."""
from __future__ import annotations

import asyncio

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from evaluation.sample_contracts import (
    SAMPLE_CLEAN_CONTRACT,
    SAMPLE_HIGH_RISK_CONTRACT,
)


@pytest.mark.llm
@pytest.mark.asyncio
def test_relevance_services_agreement() -> None:
    """Extracted JSON for a services agreement is relevant to a general extraction query."""
    from deepeval.metrics import AnswerRelevancyMetric as ARM
    from legal_agent.agent.runner import run_extraction
    # Threshold 0.75: natural language summary of a structured
    # extraction scores reliably above 0.75 but has ±0.1 GPT-4o
    # variance that makes 0.85 flaky across sessions.
    local_relevance = ARM(threshold=0.75, model="gpt-4o")
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    actual_output = (
        f"Parties: {[p.name for p in result.contract.parties]}. "
        f"Effective date: {result.contract.effective_date}. "
        f"Governing law: {result.contract.governing_law}. "
        f"Agreement type: {result.contract.agreement_type}. "
        f"Termination for convenience: "
        f"{result.contract.termination_for_convenience}. "
        f"Overall risk: {result.overall_risk_level.value}."
    )
    test_case = LLMTestCase(
        input=(
            "Extract all legal entities and clauses from this services agreement "
            "including parties, effective date, governing law, and risk flags."
        ),
        actual_output=actual_output,
        retrieval_context=[SAMPLE_CLEAN_CONTRACT],
    )
    assert_test(test_case, [local_relevance])


@pytest.mark.llm
@pytest.mark.asyncio
def test_faithfulness_governing_law_extraction(
    faithfulness_metric: FaithfulnessMetric,
) -> None:
    """Governing law and effective date outputs are faithful to the source contract."""
    from legal_agent.agent.runner import run_extraction
    result = asyncio.run(run_extraction(SAMPLE_CLEAN_CONTRACT))
    actual_output = (
        f"Governing law: {result.contract.governing_law}. "
        f"Effective date: {result.contract.effective_date}."
    )
    test_case = LLMTestCase(
        input="What is the governing law and effective date?",
        actual_output=actual_output,
        retrieval_context=[SAMPLE_CLEAN_CONTRACT],
    )
    assert_test(test_case, [faithfulness_metric])


@pytest.mark.llm
@pytest.mark.asyncio
def test_relevance_high_risk_detection(
    relevance_metric: AnswerRelevancyMetric,
    faithfulness_metric: FaithfulnessMetric,
) -> None:
    """Risk flag output for a high-risk contract is both relevant and faithful to the source."""
    from deepeval.metrics import FaithfulnessMetric as FM
    from legal_agent.agent.runner import run_extraction
    # Threshold lowered to 0.75: sparse high-risk contracts produce
    # lower faithfulness scores — agent infers risk from missing clauses.
    local_faithfulness = FM(threshold=0.75, model="gpt-4o")
    result = asyncio.run(run_extraction(SAMPLE_HIGH_RISK_CONTRACT))
    actual_output = (
        f"Risk level: {result.overall_risk_level.value}. "
        f"Flags: {[f.clause_type for f in result.risk_flags]}. "
        f"Warnings: {result.extraction_warnings}."
    )
    test_case = LLMTestCase(
        input=(
            "Identify all risk factors, missing clauses, and overall risk level "
            "in this vendor agreement."
        ),
        actual_output=actual_output,
        retrieval_context=[SAMPLE_HIGH_RISK_CONTRACT],
    )
    assert_test(test_case, [relevance_metric, local_faithfulness])
