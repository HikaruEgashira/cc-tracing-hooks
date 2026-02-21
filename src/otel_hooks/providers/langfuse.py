"""Langfuse provider using native SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langfuse import Langfuse, propagate_attributes

from otel_hooks.domain.transcript import Turn
from otel_hooks.providers.common import build_turn_payload


class LangfuseProvider:
    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path | None, source_tool: str = "") -> None:
        payload = build_turn_payload(turn)
        metadata: dict[str, Any] = {
            "source": "otel-hooks",
            "session_id": session_id,
            "turn_number": turn_num,
            "user_text": payload.user_text_meta,
        }
        if transcript_path is not None:
            metadata["transcript_path"] = str(transcript_path)
        if source_tool:
            metadata["source_tool"] = source_tool
        with propagate_attributes(
            session_id=session_id,
            trace_name=f"AI Session - Turn {turn_num}",
            tags=["otel-hooks"],
        ):
            with self._langfuse.start_as_current_span(
                name=f"AI Session - Turn {turn_num}",
                input={"role": "user", "content": payload.user_text},
                metadata=metadata,
            ) as trace_span:
                with self._langfuse.start_as_current_observation(
                    name="Assistant Response",
                    as_type="generation",
                    model=payload.model,
                    input={"role": "user", "content": payload.user_text},
                    output={"role": "assistant", "content": payload.assistant_text},
                    metadata={
                        "assistant_text": payload.assistant_text_meta,
                        "tool_count": len(payload.tool_calls),
                    },
                ):
                    pass

                for tc in payload.tool_calls:
                    with self._langfuse.start_as_current_observation(
                        name=f"Tool: {tc.name}",
                        as_type="tool",
                        input=tc.input,
                        metadata={
                            "tool_name": tc.name,
                            "tool_id": tc.id,
                            "input_meta": tc.input_meta,
                            "output_meta": tc.output_meta,
                        },
                    ) as tool_obs:
                        tool_obs.update(output=tc.output)

                trace_span.update(output={"role": "assistant", "content": payload.assistant_text})

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        sid = session_id or "metrics"
        metadata: dict[str, Any] = {
            "source": "otel-hooks",
            "metric_name": metric_name,
            "metric_value": metric_value,
            "attributes": attributes or {},
        }
        if source_tool:
            metadata["source_tool"] = source_tool
        with propagate_attributes(
            session_id=sid,
            trace_name=f"Metric - {metric_name}",
            tags=["otel-hooks", "metric"],
        ):
            with self._langfuse.start_as_current_span(
                name=f"Metric - {metric_name}",
                input={"value": metric_value},
                metadata=metadata,
            ):
                pass

    def flush(self) -> None:
        self._langfuse.flush()

    def shutdown(self) -> None:
        self._langfuse.shutdown()
