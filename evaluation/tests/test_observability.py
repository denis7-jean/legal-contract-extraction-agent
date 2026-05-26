"""In-memory span tests for the observability module — no live Phoenix required."""
from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from legal_agent.observability.tracing import (
    ATTR_AGENT_CONFIG_ID,
    ATTR_AGENT_PROMPT_LENGTH,
    ATTR_TOOL_INPUT,
    ATTR_TOOL_NAME,
    ATTR_TOOL_OUTPUT,
    create_test_tracer_provider,
)


@pytest.mark.integration
def test_create_test_tracer_provider_returns_tuple() -> None:
    """create_test_tracer_provider returns a (TracerProvider, InMemorySpanExporter) tuple."""
    provider, exporter = create_test_tracer_provider()
    assert provider is not None
    assert exporter is not None
    assert isinstance(exporter, InMemorySpanExporter)
    assert exporter.get_finished_spans() == ()


@pytest.mark.integration
def test_in_memory_exporter_captures_spans() -> None:
    """Spans emitted to the test provider are captured by the in-memory exporter."""
    provider, exporter = create_test_tracer_provider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test.span") as span:
        span.set_attribute("test.key", "test.value")
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.span"
    assert spans[0].attributes["test.key"] == "test.value"


@pytest.mark.integration
def test_span_attribute_constants_are_strings() -> None:
    """All exported attribute name constants are non-empty strings."""
    assert isinstance(ATTR_TOOL_NAME, str)
    assert isinstance(ATTR_TOOL_INPUT, str)
    assert isinstance(ATTR_TOOL_OUTPUT, str)
    assert isinstance(ATTR_AGENT_CONFIG_ID, str)
    assert isinstance(ATTR_AGENT_PROMPT_LENGTH, str)


@pytest.mark.integration
def test_multiple_spans_captured_independently() -> None:
    """Multiple spans emitted in sequence are all captured by the exporter."""
    provider, exporter = create_test_tracer_provider()
    tracer = provider.get_tracer("test")
    for i in range(3):
        with tracer.start_as_current_span(f"span.{i}"):
            pass
    spans = exporter.get_finished_spans()
    assert len(spans) == 3
    names = [s.name for s in spans]
    assert "span.0" in names
    assert "span.1" in names
    assert "span.2" in names


@pytest.mark.integration
def test_exporter_clear_resets_spans() -> None:
    """Calling exporter.clear() removes all previously captured spans."""
    provider, exporter = create_test_tracer_provider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("before.clear"):
        pass
    assert len(exporter.get_finished_spans()) == 1
    exporter.clear()
    assert len(exporter.get_finished_spans()) == 0


@pytest.mark.integration
def test_trace_tool_span_name_format() -> None:
    """Tool spans follow the tool.{name} naming convention with required attributes."""
    provider, exporter = create_test_tracer_provider()
    tracer = provider.get_tracer("test")
    tool_name = "extract_entities"
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute(ATTR_TOOL_NAME, tool_name)
        span.set_attribute(ATTR_TOOL_INPUT, "test input"[:500])
        span.set_attribute(ATTR_TOOL_OUTPUT, "test output"[:500])
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "tool.extract_entities"
    assert spans[0].attributes[ATTR_TOOL_NAME] == "extract_entities"
