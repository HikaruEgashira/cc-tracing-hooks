"""Datadog provider using ddtrace SDK."""

from __future__ import annotations

import json
from pathlib import Path

from ddtrace import tracer

from otel_hooks.domain.transcript import MAX_CHARS_DEFAULT, Turn
from otel_hooks.providers.common import build_turn_payload


class DatadogProvider:
    def __init__(self, service: str = "otel-hooks", env: str | None = None, *, max_chars: int = MAX_CHARS_DEFAULT) -> None:
        tracer.configure(service=service)
        if env:
            tracer.set_tags({"env": env})
        self._max_chars = max_chars

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path | None, source_tool: str = "") -> None:
        payload = build_turn_payload(turn, max_chars=self._max_chars)
        tags: dict[str, str] = {
            "session.id": session_id,
            "gen_ai.system": "otel-hooks",
            "gen_ai.request.model": payload.model,
            "gen_ai.prompt": payload.user_text,
            "gen_ai.completion": payload.assistant_text,
        }
        if transcript_path is not None:
            tags["transcript_path"] = str(transcript_path)
        if source_tool:
            tags["source_tool"] = source_tool
        with tracer.trace(
            "ai_session.turn",
            resource=f"{source_tool} - Turn {turn_num}" if source_tool else f"Turn {turn_num}",
            service="otel-hooks",
            span_type="llm",
        ) as root_span:
            root_span.set_tags(tags)

            with tracer.trace(
                "ai_session.generation",
                resource="Assistant Response",
                service="otel-hooks",
                span_type="llm",
            ) as gen_span:
                gen_span.set_tags(
                    {
                        "gen_ai.request.model": payload.model,
                        "gen_ai.prompt": payload.user_text,
                        "gen_ai.completion": payload.assistant_text,
                        "gen_ai.usage.tool_count": str(len(payload.tool_calls)),
                    }
                )

            for tc in payload.tool_calls:
                in_str = tc.input if isinstance(tc.input, str) else json.dumps(tc.input, ensure_ascii=False)
                with tracer.trace(
                    "ai_session.tool",
                    resource=tc.name,
                    service="otel-hooks",
                    span_type="tool",
                ) as tool_span:
                    tool_span.set_tags(
                        {
                            "tool.name": tc.name,
                            "tool.id": tc.id,
                            "tool.input": in_str,
                            "tool.output": tc.output or "",
                        }
                    )

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        with tracer.trace(
            "ai_session.metric",
            resource=metric_name,
            service="otel-hooks",
            span_type="custom",
        ) as metric_span:
            tags: dict[str, str] = {
                "metric.name": metric_name,
                "metric.value": str(metric_value),
                "gen_ai.system": "otel-hooks",
            }
            if source_tool:
                tags["source_tool"] = source_tool
            if session_id:
                tags["session.id"] = session_id
            if attributes:
                for k, v in attributes.items():
                    tags[f"metric.attr.{k}"] = v
            metric_span.set_tags(tags)

    def flush(self) -> None:
        tracer.flush()

    def shutdown(self) -> None:
        tracer.shutdown()
