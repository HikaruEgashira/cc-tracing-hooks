"""Lightweight hook event model — replaces the openhook dependency."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class EventType(StrEnum):
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    PROMPT_SUBMIT = "prompt.submit"
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    FILE_WRITE = "file.write"


@dataclass(frozen=True)
class HookEvent:
    source: str
    type: EventType
    session_id: str
    data: dict[str, Any] = field(default_factory=dict)
    context: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    @property
    def transcript_path(self) -> Path | None:
        tp = self.data.get("transcript_path")
        if not tp:
            return None
        return Path(tp)

    @property
    def is_trace(self) -> bool:
        return self.transcript_path is not None


# ---------------------------------------------------------------------------
# Legacy payload detection (replaces openhook.compat.from_legacy)
# ---------------------------------------------------------------------------

_METRIC_EVENT_MAP: dict[str, EventType] = {
    "userPromptSubmitted": EventType.PROMPT_SUBMIT,
    "userPromptSubmit": EventType.PROMPT_SUBMIT,
    "UserPromptSubmit": EventType.PROMPT_SUBMIT,
    "UserPromptExpansion": EventType.PROMPT_SUBMIT,
    "preToolUse": EventType.TOOL_START,
    "PreToolUse": EventType.TOOL_START,
    "postToolUse": EventType.TOOL_END,
    "PostToolUse": EventType.TOOL_END,
    "PostToolBatch": EventType.TOOL_END,
    "sessionEnd": EventType.SESSION_END,
    "SessionEnd": EventType.SESSION_END,
    "stop": EventType.SESSION_END,
    "Stop": EventType.SESSION_END,
    # New events from upstream specs
    "sessionStart": EventType.SESSION_START,
    "SessionStart": EventType.SESSION_START,
    "Setup": EventType.SESSION_START,
    "errorOccurred": EventType.SESSION_END,
    "ErrorOccurred": EventType.SESSION_END,
    "agentSpawn": EventType.SESSION_START,
    "AgentSpawn": EventType.SESSION_START,
    # Claude Code new events (2026-06-09 spec sync)
    "MessageDisplay": EventType.SESSION_END,
    # Copilot new events (2026-05-18 spec sync)
    "agentStop": EventType.SESSION_END,
    "AgentStop": EventType.SESSION_END,
    "notification": EventType.SESSION_END,
    "Notification": EventType.SESSION_END,
    "permissionRequest": EventType.TOOL_START,
    "PermissionRequest": EventType.TOOL_START,
    "postToolUseFailure": EventType.TOOL_END,
    "PostToolUseFailure": EventType.TOOL_END,
    # preToolUseFailure: removed from Copilot spec (2026-07-14); kept for backward compat
    "preToolUseFailure": EventType.TOOL_END,
    "PreToolUseFailure": EventType.TOOL_END,
    # Cline SDK hooks (2026-06-30 spec sync — new SDK-based event model)
    "session_start": EventType.SESSION_START,
    "run_start": EventType.SESSION_START,
    "before_agent_start": EventType.SESSION_START,
    "iteration_start": EventType.SESSION_START,
    "turn_start": EventType.SESSION_START,
    "session_shutdown": EventType.SESSION_END,
    "run_end": EventType.SESSION_END,
    "iteration_end": EventType.SESSION_END,
    "turn_end": EventType.SESSION_END,
    "stop_error": EventType.SESSION_END,
    "tool_call_before": EventType.TOOL_START,
    "tool_call_after": EventType.TOOL_END,
    "preCompact": EventType.SESSION_END,
    "PreCompact": EventType.SESSION_END,
    "subagentStart": EventType.SESSION_START,
    "SubagentStart": EventType.SESSION_START,
    "subagentStop": EventType.SESSION_END,
    "SubagentStop": EventType.SESSION_END,
    # Kiro new events (2026-07-07 spec sync — v1 hooks schema)
    "PreTaskExec": EventType.SESSION_START,
    "PostTaskExec": EventType.SESSION_END,
    "PostFileCreate": EventType.FILE_WRITE,
    "PostFileSave": EventType.FILE_WRITE,
    "PostFileDelete": EventType.FILE_WRITE,
}


def _detect_source(payload: dict[str, Any]) -> str:
    if "source_tool" in payload:
        return str(payload["source_tool"])
    if "conversation_id" in payload:
        return "cursor"
    if "taskId" in payload:
        return "cline"
    if "thread-id" in payload:
        return "codex"
    if "hook_event_name" in payload:
        event_name = str(payload["hook_event_name"])
        # Kiro-specific events (not shared with other tools)
        _KIRO_SPECIFIC = frozenset({
            "PreTaskExec", "PostTaskExec",
            "PostFileCreate", "PostFileSave", "PostFileDelete",
        })
        # Old camelCase Kiro events kept for backwards compatibility
        if event_name in _KIRO_SPECIFIC or event_name in ("userPromptSubmit", "stop", "agentSpawn"):
            return "kiro"
        return "copilot"
    if "sessionId" in payload or "transcriptPath" in payload:
        return "claude-code"
    if "session_id" in payload and "timestamp" in payload:
        return "gemini"
    return "unknown"


def _extract_session_id(payload: dict[str, Any]) -> str:
    for key in ("conversation_id", "sessionId", "session_id", "taskId", "thread-id"):
        val = payload.get(key)
        if val:
            return str(val)
    nested = payload.get("session")
    if isinstance(nested, dict) and "id" in nested:
        return str(nested["id"])
    return ""


def _extract_transcript_path(payload: dict[str, Any]) -> str | None:
    for key in ("transcriptPath", "transcript_path"):
        val = payload.get(key)
        if val:
            return str(val)
    nested = payload.get("transcript")
    if isinstance(nested, dict) and "path" in nested:
        return str(nested["path"])
    return None


def from_legacy(payload: dict[str, Any]) -> HookEvent:
    """Convert a legacy tool payload into a HookEvent."""
    source = _detect_source(payload)
    session_id = _extract_session_id(payload)

    event_name = str(payload.get("hook_event_name", ""))
    event_type = _METRIC_EVENT_MAP.get(event_name, EventType.SESSION_END)

    data: dict[str, Any] = {}
    tp = _extract_transcript_path(payload)
    if tp:
        data["transcript_path"] = tp

    if event_type in (EventType.TOOL_START, EventType.TOOL_END):
        tool_name = payload.get("tool_name")
        if tool_name:
            data["tool_name"] = str(tool_name)

    context: str | None = None
    cwd = payload.get("cwd")
    if cwd:
        context = f"file://{cwd}"

    return HookEvent(
        source=source,
        type=event_type,
        session_id=session_id,
        data=data,
        context=context,
        extensions={"legacy_payload": payload},
    )
