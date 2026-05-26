"""Session-scoped DeepEval metric fixtures and CUAD dataset fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, HallucinationMetric
from evaluation.sample_contracts import (  # noqa: F401 — re-exported for backwards compat
    SAMPLE_CLEAN_CONTRACT,
    SAMPLE_HIGH_RISK_CONTRACT,
    SAMPLE_MFN_CONTRACT,
)

EVAL_DATASET_PATH: Path = Path(__file__).parent.parent / "data" / "eval_dataset.json"


# ── Metric fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="session")
def hallucination_metric() -> HallucinationMetric:
    """Zero-tolerance hallucination metric for legal entity extraction."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping LLM metrics")
    return HallucinationMetric(threshold=0.0, model="gpt-4o")


@pytest.fixture(scope="session")
def relevance_metric() -> AnswerRelevancyMetric:
    """Answer relevancy metric — must score ≥0.85."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping LLM metrics")
    return AnswerRelevancyMetric(threshold=0.85, model="gpt-4o")


@pytest.fixture(scope="session")
def faithfulness_metric() -> FaithfulnessMetric:
    """Faithfulness metric — must score ≥0.90."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping LLM metrics")
    return FaithfulnessMetric(threshold=0.90, model="gpt-4o")


# ── CUAD dataset fixtures ────────────────────────────────────────────


@pytest.fixture(scope="session")
def cuad_records() -> list[dict[str, object]]:
    """Load all 20 CUAD eval records from data/eval_dataset.json.

    Skips the session with a clear message if the file does not exist,
    so pure pytest runs (no LLM) never fail due to missing data file.
    """
    if not EVAL_DATASET_PATH.exists():
        pytest.skip(
            f"Eval dataset not found at {EVAL_DATASET_PATH}. "
            "Run: python scripts/prepare_cuad_data.py"
        )
    raw = json.loads(EVAL_DATASET_PATH.read_text(encoding="utf-8"))
    return list(raw["records"])  # type: ignore[return-value]


@pytest.fixture(scope="session")
def cuad_records_with_governing_law(
    cuad_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Subset of CUAD records that have a ground-truth governing_law value."""
    return [
        r for r in cuad_records
        if r.get("ground_truth", {}).get("governing_law")  # type: ignore[union-attr]
    ]


@pytest.fixture(scope="session")
def cuad_records_with_effective_date(
    cuad_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Subset of CUAD records that have a ground-truth effective_date value."""
    return [
        r for r in cuad_records
        if r.get("ground_truth", {}).get("effective_date")  # type: ignore[union-attr]
    ]

