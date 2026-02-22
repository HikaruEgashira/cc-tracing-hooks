"""OTLP provider using OpenTelemetry SDK."""

from __future__ import annotations

import json
from pathlib import Path

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from otel_hooks.domain.transcript import MAX_CHARS_DEFAULT, Turn
from otel_hooks.providers.common import build_turn_payload


class OTLPProvider:
    def __init__(self, endpoint: str, headers: dict[str, str] | None = None, *, max_chars: int = MAX_CHARS_DEFAULT) -> None:
        resource = Resource.create({"service.name": "otel-hooks"})
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers or {})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        self._provider = provider
        self._tracer = provider.get_tracer("otel-hooks")
        self._max_chars = max_chars

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path | None, source_tool: str = "") -> None:
        payload = build_turn_payload(turn, max_chars=self._max_chars)
        attrs: dict[str, str | int] = {
            "session.id": session_id,
            "gen_ai.system": "otel-hooks",
            "gen_ai.request.model": payload.model,
            "gen_ai.prompt": payload.user_text,
            "gen_ai.completion": payload.assistant_text,
        }
        if transcript_path is not None:
            attrs["transcript_path"] = str(transcript_path)
        if source_tool:
            attrs["source_tool"] = source_tool
        span_name = f"{source_tool} - Turn {turn_num}" if source_tool else f"AI Session - Turn {turn_num}"
        with self._tracer.start_as_current_span(
            span_name,
            attributes=attrs,
        ):
            with self._tracer.start_as_current_span(
                "Assistant Response",
                attributes={
                    "gen_ai.request.model": payload.model,
                    "gen_ai.prompt": payload.user_text,
                    "gen_ai.completion": payload.assistant_text,
                    "gen_ai.usage.tool_count": len(payload.tool_calls),
                },
            ):
                pass

            for tc in payload.tool_calls:
                in_str = tc.input if isinstance(tc.input, str) else json.dumps(tc.input, ensure_ascii=False)
                with self._tracer.start_as_current_span(
                    f"Tool: {tc.name}",
                    attributes={
                        "tool.name": tc.name,
                        "tool.id": tc.id,
                        "tool.input": in_str,
                        "tool.output": tc.output or "",
                    },
                ):
                    pass

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        attrs: dict[str, str | float] = {
            "metric.name": metric_name,
            "metric.value": metric_value,
            "gen_ai.system": "otel-hooks",
        }
        if source_tool:
            attrs["source_tool"] = source_tool
        if session_id:
            attrs["session.id"] = session_id
        if attributes:
            for k, v in attributes.items():
                attrs[f"metric.attr.{k}"] = v
        with self._tracer.start_as_current_span(
            f"Metric - {metric_name}",
            attributes=attrs,
        ):
            pass

    def flush(self) -> None:
        self._provider.force_flush()

    def shutdown(self) -> None:
        self._provider.shutdown()
