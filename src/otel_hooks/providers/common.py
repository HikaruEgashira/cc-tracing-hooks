"""Shared provider payload building logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from otel_hooks.domain.transcript import MAX_CHARS_DEFAULT, Turn, extract_text, get_content, get_model, iter_tool_uses, truncate_text


@dataclass
class ToolCall:
    id: str
    name: str
    input: Any
    output: str | None
    input_meta: dict[str, Any] | None
    output_meta: dict[str, Any] | None


@dataclass
class TurnPayload:
    user_text: str
    user_text_meta: dict[str, Any]
    assistant_text: str
    assistant_text_meta: dict[str, Any]
    model: str
    tool_calls: list[ToolCall]


def _tool_calls_from_assistants(assistant_msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for am in assistant_msgs:
        for tu in iter_tool_uses(get_content(am)):
            tid = tu.get("id") or ""
            calls.append(
                {
                    "id": str(tid),
                    "name": tu.get("name") or "unknown",
                    "input": tu.get("input")
                    if isinstance(tu.get("input"), (dict, list, str, int, float, bool))
                    else {},
                }
            )
    return calls


def build_turn_payload(turn: Turn, *, max_chars: int = MAX_CHARS_DEFAULT) -> TurnPayload:
    user_text_raw = extract_text(get_content(turn.user_msg))
    user_text, user_text_meta = truncate_text(user_text_raw, max_chars)

    last_assistant = turn.assistant_msgs[-1]
    assistant_text_raw = extract_text(get_content(last_assistant))
    assistant_text, assistant_text_meta = truncate_text(assistant_text_raw, max_chars)

    model = get_model(turn.assistant_msgs[0])
    raw_tool_calls = _tool_calls_from_assistants(turn.assistant_msgs)

    tool_calls: list[ToolCall] = []
    for c in raw_tool_calls:
        input_obj = c["input"]
        input_meta: dict[str, Any] | None = None
        if isinstance(input_obj, str):
            input_obj, input_meta = truncate_text(input_obj, max_chars)

        output: str | None = None
        output_meta: dict[str, Any] | None = None
        if c["id"] and c["id"] in turn.tool_results_by_id:
            out_raw = turn.tool_results_by_id[c["id"]]
            out_str = out_raw if isinstance(out_raw, str) else json.dumps(out_raw, ensure_ascii=False)
            output, output_meta = truncate_text(out_str, max_chars)

        tool_calls.append(
            ToolCall(
                id=c["id"],
                name=c["name"],
                input=input_obj,
                output=output,
                input_meta=input_meta,
                output_meta=output_meta,
            )
        )

    return TurnPayload(
        user_text=user_text,
        user_text_meta=user_text_meta,
        assistant_text=assistant_text,
        assistant_text_meta=assistant_text_meta,
        model=model,
        tool_calls=tool_calls,
    )
