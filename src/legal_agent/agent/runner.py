"""PydanticAI agent instantiation and async extraction runner."""
from __future__ import annotations

import logging
import time
import uuid

from pydantic_ai import Agent

from legal_agent.agent.prompts import SYSTEM_PROMPT
from legal_agent.agent.tools import extract_entities, lookup_jurisdiction_aliases, validate_clauses
from legal_agent.observability.tracing import agent_request_span, configure_tracing
from legal_agent.schemas.legal import ExtractionResult

_logger = logging.getLogger(__name__)

_agent: Agent[None, ExtractionResult] | None = None


def get_agent() -> Agent[None, ExtractionResult]:
    """Return the singleton PydanticAI agent, creating it on first call.

    Defers Agent() instantiation until first use so that importing
    this module does not require OPENAI_API_KEY to be set.
    This allows integration and API tests to import the FastAPI app
    without credentials.
    """
    global _agent
    if _agent is None:
        _agent = Agent(
            model="openai:gpt-4o",
            output_type=ExtractionResult,
            system_prompt=SYSTEM_PROMPT,
            tools=[extract_entities, validate_clauses, lookup_jurisdiction_aliases],
        )
    return _agent


async def run_extraction(contract_text: str) -> ExtractionResult:
    """Run full legal entity extraction on a raw contract text string.

    Configures tracing (no-op after first call), creates a parent OTLP span,
    and delegates to the PydanticAI agent which enforces ExtractionResult output.

    Args:
        contract_text: Raw unstructured contract text.

    Returns:
        Validated ExtractionResult with risk flags and confidence score.
    """
    start_ms = int(time.time() * 1000)
    contract_id = str(uuid.uuid4())
    configure_tracing()
    async with agent_request_span(contract_text[:200], contract_id):
        result = await get_agent().run(contract_text)
        elapsed_ms = int(time.time() * 1000) - start_ms
        _logger.info(
            "Extraction complete: contract=%s elapsed=%dms", contract_id, elapsed_ms
        )
        return result.output
