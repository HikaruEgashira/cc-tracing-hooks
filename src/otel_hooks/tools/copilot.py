"""GitHub Copilot tool configuration (.github/hooks/otel-hooks.json).

Works with both GitHub Copilot CLI and VS Code Copilot agent.

Reference:
  - https://docs.github.com/en/copilot/reference/hooks-configuration
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "OTEL_HOOKS_SOURCE_TOOL=copilot otel-hooks hook"
HOOKS_FILE = "otel-hooks.json"
_HOOK_EVENTS = ("userPromptSubmitted", "preToolUse", "postToolUse", "sessionEnd")
_EVENT_ALIASES = {
    "userPromptSubmitted": "user_prompt_submitted",
    "UserPromptSubmitted": "user_prompt_submitted",
    "UserPromptSubmit": "user_prompt_submitted",
    "preToolUse": "pre_tool_use",
    "PreToolUse": "pre_tool_use",
    "postToolUse": "post_tool_use",
    "PostToolUse": "post_tool_use",
    "sessionEnd": "session_end",
    "SessionEnd": "session_end",
}


def _to_str_map(raw: dict[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in raw.items() if v is not None and str(v)}


@register_tool
class CopilotConfig:
    @property
    def name(self) -> str:
        return "copilot"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / ".github" / "hooks" / HOOKS_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope), default={"version": 1, "hooks": {}})

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", {})
        return all(
            any("otel-hooks hook" in hook.get("bash", "") for hook in hooks.get(event_name, []))
            for event_name in _HOOK_EVENTS
        )

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        base_cmd = command or "otel-hooks hook"
        cmd = f"OTEL_HOOKS_SOURCE_TOOL=copilot {base_cmd}"
        settings.setdefault("version", 1)
        hooks = settings.setdefault("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.setdefault(event_name, [])
            if any("otel-hooks hook" in hook.get("bash", "") for hook in group):
                continue
            group.append(
                {
                    "type": "command",
                    "bash": cmd,
                    "comment": "otel-hooks: emit observability data",
                }
            )
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.get(event_name, [])
            if not group:
                continue
            hooks[event_name] = [
                hook for hook in group if "otel-hooks hook" not in hook.get("bash", "")
            ]
            if not hooks[event_name]:
                del hooks[event_name]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        event_raw = payload.get("hook_event_name")
        if not isinstance(event_raw, str):
            return None
        event = _EVENT_ALIASES.get(event_raw)
        if not event:
            return None

        session_id = payload.get("session_id")
        sid = session_id if isinstance(session_id, str) else ""

        if event == "user_prompt_submitted":
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

        if event == "pre_tool_use":
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

        if event == "post_tool_use":
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
                    "reason": payload.get("session_end_reason") or payload.get("sessionEndReason"),
                    "cwd": payload.get("cwd"),
                }
            ),
        )
