"""Claude Code tool configuration.

Reference:
  - https://code.claude.com/docs/en/hooks
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, _extract_transcript_path, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"


@register_tool
class ClaudeConfig:
    @property
    def name(self) -> str:
        return "claude"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT, Scope.LOCAL]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".claude" / "settings.json"
        if scope is Scope.PROJECT:
            return Path.cwd() / ".claude" / "settings.json"
        return Path.cwd() / ".claude" / "settings.local.json"

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        stop_hooks = settings.get("hooks", {}).get("Stop", [])
        for group in stop_hooks:
            for hook in group.get("hooks", []):
                if HOOK_COMMAND in hook.get("command", ""):
                    return True
        return False

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        cmd = command or HOOK_COMMAND
        hooks = settings.setdefault("hooks", {})
        stop = hooks.setdefault("Stop", [])
        for group in stop:
            for hook in group.get("hooks", []):
                if cmd in hook.get("command", ""):
                    return settings
        stop.append({"hooks": [{"type": "command", "command": cmd}]})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        stop = settings.get("hooks", {}).get("Stop", [])
        if not stop:
            return settings
        settings["hooks"]["Stop"] = [
            group for group in stop
            if not any(HOOK_COMMAND in hook.get("command", "") for hook in group.get("hooks", []))
        ]
        if not settings["hooks"]["Stop"]:
            del settings["hooks"]["Stop"]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        session_id = (
            payload.get("sessionId")
            or payload.get("session_id")
            or payload.get("session", {}).get("id")
        )
        if not isinstance(session_id, str) or not session_id:
            return None
        if not any(k in payload for k in ("sessionId", "session_id")) and not isinstance(
            payload.get("session"), dict
        ):
            return None
        return HookEvent.trace(
            source_tool=self.name,
            session_id=session_id,
            transcript_path=_extract_transcript_path(payload),
        )
