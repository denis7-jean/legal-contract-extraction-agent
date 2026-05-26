"""Arize Phoenix + OpenTelemetry tracing setup, tool decorator, and span helpers."""
from __future__ import annotations

import contextlib
import functools
import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from opentelemetry import trace

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_logger = logging.getLogger(__name__)
_tracing_configured: bool = False

P = ParamSpec("P")
R = TypeVar("R")

# Span attribute name constants — used by trace_tool, agent_request_span, and tests.
ATTR_TOOL_NAME = "tool.name"
ATTR_TOOL_INPUT = "tool.input"
ATTR_TOOL_OUTPUT = "tool.output"
ATTR_AGENT_CONFIG_ID = "agent.config_id"
ATTR_AGENT_PROMPT_LENGTH = "agent.prompt_length"
ATTR_AGENT_MODEL = "agent.model"


def configure_tracing() -> None:
    """Initialize Arize Phoenix tracing from PHOENIX_COLLECTOR_ENDPOINT.

    Reads the endpoint from the environment and registers the global tracer
    provider via phoenix.otel.register. Safe to call multiple times — no-ops
    after the first successful call.
    """
    global _tracing_configured
    if _tracing_configured:
        return
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    if not endpoint:
        _logger.warning("PHOENIX_COLLECTOR_ENDPOINT not set — tracing disabled")
        return
    try:
        from phoenix.otel import register as _phoenix_register
        _phoenix_register(endpoint=endpoint, project_name="legal-agent")
        _tracing_configured = True
        _logger.info("Arize Phoenix tracing configured: %s", endpoint)
    except Exception as exc:
        _logger.warning("Tracing setup failed: %s", exc)


def create_test_tracer_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create an isolated TracerProvider with InMemorySpanExporter for tests.

    Returns a (provider, exporter) tuple. The exporter's .get_finished_spans()
    method returns all spans emitted since the last .clear() call.
    This never touches the global TracerProvider — safe to call in tests.

    Returns:
        Tuple of (TracerProvider, InMemorySpanExporter).
    """
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter as _InMemorySpanExporter,
    )
    exporter = _InMemorySpanExporter()
    provider = _TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def trace_tool(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Wrap an async tool function in an OpenTelemetry span named after the tool.

    Args:
        fn: The async tool function to wrap.

    Returns:
        Wrapped async function preserving the original signature.
    """
    @functools.wraps(fn)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(f"tool.{fn.__name__}") as span:
            span.set_attribute(ATTR_TOOL_NAME, fn.__name__)
            _first: object = args[0] if args else ""
            span.set_attribute(ATTR_TOOL_INPUT, str(_first)[:500])
            result = await fn(*args, **kwargs)
            span.set_attribute(ATTR_TOOL_OUTPUT, str(result)[:500])
            return result

    return _wrapper


@contextlib.asynccontextmanager
async def agent_request_span(
    text_excerpt: str,
    contract_id: str,
) -> AsyncGenerator[None, None]:
    """Async context manager wrapping a full agent request in a parent OTLP span.

    Args:
        text_excerpt: First ~200 chars of the contract text, stored as span metadata.
        contract_id:  UUID of the contract being processed.

    Yields:
        None — used purely for span lifetime management.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute(ATTR_AGENT_CONFIG_ID, contract_id)
        span.set_attribute(ATTR_AGENT_PROMPT_LENGTH, len(text_excerpt))
        span.set_attribute("contract.text_excerpt", text_excerpt)
        yield
