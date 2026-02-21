"""Kiro CLI tool configuration (.kiro/agents/default.json).

Reference:
  - https://kiro.dev/docs/cli/hooks/
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "OTEL_HOOKS_SOURCE_TOOL=kiro otel-hooks hook"
AGENT_FILE = "default.json"
_HOOK_EVENTS = ("userPromptSubmit", "preToolUse", "postToolUse", "stop")


def _to_str_map(raw: dict[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in raw.items() if v is not None and str(v)}


@register_tool
class KiroConfig:
    @property
    def name(self) -> str:
        return "kiro"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".kiro" / "agents" / AGENT_FILE
        return Path.cwd() / ".kiro" / "agents" / AGENT_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", {})
        return all(
            any(HOOK_COMMAND in hook.get("command", "") for hook in hooks.get(event_name, []))
            for event_name in _HOOK_EVENTS
        )

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.setdefault("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.setdefault(event_name, [])
            if any(HOOK_COMMAND in hook.get("command", "") for hook in group):
                continue
            group.append({"command": HOOK_COMMAND})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.get(event_name, [])
            if not group:
                continue
            hooks[event_name] = [
                hook for hook in group if HOOK_COMMAND not in hook.get("command", "")
            ]
            if not hooks[event_name]:
                del hooks[event_name]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        event = payload.get("hook_event_name")
        if not isinstance(event, str) or event not in _HOOK_EVENTS:
            return None

        session_id = payload.get("session_id")
        sid = session_id if isinstance(session_id, str) else ""

        if event == "userPromptSubmit":
            prompt = payload.get("prompt")
            return HookEvent.metric(
                source_tool=self.name,
                session_id=sid,
                metric_name="prompt_submitted",
                metric_attributes=_to_str_map(
                    {
                        "cwd": payload.get("cwd"),
                        "prompt_len": len(prompt) if isinstance(prompt, str) else "",
                    }
                ),
            )

        if event == "preToolUse":
            tool_name = payload.get("tool_name") or payload.get("toolName")
            return HookEvent.metric(
                source_tool=self.name,
                session_id=sid,
                metric_name="tool_started",
                metric_attributes=_to_str_map(
                    {
                        "tool_name": tool_name,
                        "cwd": payload.get("cwd"),
                    }
                ),
            )

        if event == "postToolUse":
            tool_name = payload.get("tool_name") or payload.get("toolName")
            return HookEvent.metric(
                source_tool=self.name,
                session_id=sid,
                metric_name="tool_completed",
                metric_attributes=_to_str_map(
                    {
                        "tool_name": tool_name,
                        "cwd": payload.get("cwd"),
                    }
                ),
            )

        return HookEvent.metric(
            source_tool=self.name,
            session_id=sid,
            metric_name="session_ended",
            metric_attributes=_to_str_map(
                {
                    "cwd": payload.get("cwd"),
                }
            ),
        )
