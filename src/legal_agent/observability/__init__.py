"""Arize Phoenix + OpenTelemetry observability setup."""
from __future__ import annotations

from legal_agent.observability.tracing import agent_request_span, configure_tracing, trace_tool

__all__ = ["agent_request_span", "configure_tracing", "trace_tool"]
