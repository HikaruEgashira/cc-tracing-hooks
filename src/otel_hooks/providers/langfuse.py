"""Langfuse provider using native SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from langfuse import Langfuse, propagate_attributes

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


class LangfuseProvider:
    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path) -> None:
        user_text_raw = extract_text(get_content(turn.user_msg))
        user_text, user_text_meta = truncate_text(user_text_raw)
        last_assistant = turn.assistant_msgs[-1]
        assistant_text_raw = extract_text(get_content(last_assistant))
        assistant_text, assistant_text_meta = truncate_text(assistant_text_raw)
        model = get_model(turn.assistant_msgs[0])
        tool_calls = _tool_calls_from_assistants(turn.assistant_msgs)

        for c in tool_calls:
            if c["id"] and c["id"] in turn.tool_results_by_id:
                out_raw = turn.tool_results_by_id[c["id"]]
                out_str = out_raw if isinstance(out_raw, str) else json.dumps(out_raw, ensure_ascii=False)
                out_trunc, out_meta = truncate_text(out_str)
                c["output"] = out_trunc
                c["output_meta"] = out_meta
            else:
                c["output"] = None

        with propagate_attributes(
            session_id=session_id,
            trace_name=f"Claude Code - Turn {turn_num}",
            tags=["claude-code"],
        ):
            with self._langfuse.start_as_current_span(
                name=f"Claude Code - Turn {turn_num}",
                input={"role": "user", "content": user_text},
                metadata={
                    "source": "claude-code",
                    "session_id": session_id,
                    "turn_number": turn_num,
                    "transcript_path": str(transcript_path),
                    "user_text": user_text_meta,
                },
            ) as trace_span:
                with self._langfuse.start_as_current_observation(
                    name="Claude Response",
                    as_type="generation",
                    model=model,
                    input={"role": "user", "content": user_text},
                    output={"role": "assistant", "content": assistant_text},
                    metadata={
                        "assistant_text": assistant_text_meta,
                        "tool_count": len(tool_calls),
                    },
                ):
                    pass

                for tc in tool_calls:
                    in_obj = tc["input"]
                    if isinstance(in_obj, str):
                        in_obj, in_meta = truncate_text(in_obj)
                    else:
                        in_meta = None
                    with self._langfuse.start_as_current_observation(
                        name=f"Tool: {tc['name']}",
                        as_type="tool",
                        input=in_obj,
                        metadata={
                            "tool_name": tc["name"],
                            "tool_id": tc["id"],
                            "input_meta": in_meta,
                            "output_meta": tc.get("output_meta"),
                        },
                    ) as tool_obs:
                        tool_obs.update(output=tc.get("output"))

                trace_span.update(output={"role": "assistant", "content": assistant_text})

    def flush(self) -> None:
        self._langfuse.flush()

    def shutdown(self) -> None:
        self._langfuse.shutdown()
