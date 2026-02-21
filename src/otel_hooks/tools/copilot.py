"""GitHub Copilot tool configuration (.github/hooks/otel-hooks.json).

Works with both GitHub Copilot CLI and VS Code Copilot agent.

Reference:
  - https://docs.github.com/en/copilot/reference/hooks-configuration
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"
HOOKS_FILE = "otel-hooks.json"
_EVENTS = {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SessionEnd"}


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
        session_end = settings.get("hooks", {}).get("sessionEnd", [])
        return any(HOOK_COMMAND in h.get("bash", "") for h in session_end)

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings.setdefault("version", 1)
        hooks = settings.setdefault("hooks", {})
        session_end = hooks.setdefault("sessionEnd", [])
        if any(HOOK_COMMAND in h.get("bash", "") for h in session_end):
            return settings
        session_end.append(
            {
                "type": "command",
                "bash": HOOK_COMMAND,
                "comment": "otel-hooks: emit observability data",
            }
        )
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        session_end = settings.get("hooks", {}).get("sessionEnd", [])
        if not session_end:
            return settings
        settings["hooks"]["sessionEnd"] = [
            h for h in session_end if HOOK_COMMAND not in h.get("bash", "")
        ]
        if not settings["hooks"]["sessionEnd"]:
            del settings["hooks"]["sessionEnd"]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        event = payload.get("hook_event_name")
        if not isinstance(event, str) or event not in _EVENTS:
            return None

        session_id = payload.get("session_id")
        sid = session_id if isinstance(session_id, str) else ""

        if event == "UserPromptSubmit":
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

        if event == "PreToolUse":
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

        if event == "PostToolUse":
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
