"""Datadog provider using ddtrace SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ddtrace import tracer

from otel_hooks.hook import (
    Turn,
    extract_text,
    get_content,
    get_model,
    iter_tool_uses,
    truncate_text,
)


def _tool_calls_from_assistants(assistant_msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for am in assistant_msgs:
        for tu in iter_tool_uses(get_content(am)):
            tid = tu.get("id") or ""
            calls.append({
                "id": str(tid),
                "name": tu.get("name") or "unknown",
                "input": tu.get("input") if isinstance(tu.get("input"), (dict, list, str, int, float, bool)) else {},
            })
    return calls


class DatadogProvider:
    def __init__(self, service: str = "otel-hooks", env: str | None = None) -> None:
        tracer.configure(service=service)
        if env:
            tracer.set_tags({"env": env})

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path) -> None:
        user_text_raw = extract_text(get_content(turn.user_msg))
        user_text, _ = truncate_text(user_text_raw)
        last_assistant = turn.assistant_msgs[-1]
        assistant_text_raw = extract_text(get_content(last_assistant))
        assistant_text, _ = truncate_text(assistant_text_raw)
        model = get_model(turn.assistant_msgs[0])
        tool_calls = _tool_calls_from_assistants(turn.assistant_msgs)

        for c in tool_calls:
            if c["id"] and c["id"] in turn.tool_results_by_id:
                out_raw = turn.tool_results_by_id[c["id"]]
                out_str = out_raw if isinstance(out_raw, str) else json.dumps(out_raw, ensure_ascii=False)
                out_trunc, _ = truncate_text(out_str)
                c["output"] = out_trunc
            else:
                c["output"] = None

        with tracer.trace(
            f"claude_code.turn",
            resource=f"Turn {turn_num}",
            service="otel-hooks",
            span_type="llm",
        ) as root_span:
            root_span.set_tags({
                "session.id": session_id,
                "gen_ai.system": "claude-code",
                "gen_ai.request.model": model,
                "gen_ai.prompt": user_text,
                "gen_ai.completion": assistant_text,
                "transcript_path": str(transcript_path),
            })

            with tracer.trace(
                "claude_code.generation",
                resource="Claude Response",
                service="otel-hooks",
                span_type="llm",
            ) as gen_span:
                gen_span.set_tags({
                    "gen_ai.request.model": model,
                    "gen_ai.prompt": user_text,
                    "gen_ai.completion": assistant_text,
                    "gen_ai.usage.tool_count": str(len(tool_calls)),
                })

            for tc in tool_calls:
                in_obj = tc["input"]
                in_str = in_obj if isinstance(in_obj, str) else json.dumps(in_obj, ensure_ascii=False)
                with tracer.trace(
                    "claude_code.tool",
                    resource=tc["name"],
                    service="otel-hooks",
                    span_type="tool",
                ) as tool_span:
                    tool_span.set_tags({
                        "tool.name": tc["name"],
                        "tool.id": tc["id"],
                        "tool.input": in_str,
                        "tool.output": tc.get("output") or "",
                    })

    def flush(self) -> None:
        tracer.flush()

    def shutdown(self) -> None:
        tracer.shutdown()
