"""Cursor tool configuration (.cursor/hooks.json).

Reference:
  - https://cursor.com/ja/docs/agent/hooks
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, _extract_transcript_path, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"


@register_tool
class CursorConfig:
    @property
    def name(self) -> str:
        return "cursor"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / ".cursor" / "hooks.json"

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        stop_hooks = settings.get("hooks", {}).get("stop", [])
        return any(HOOK_COMMAND in h.get("command", "") for h in stop_hooks)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.setdefault("hooks", {})
        stop = hooks.setdefault("stop", [])
        if any(HOOK_COMMAND in h.get("command", "") for h in stop):
            return settings
        stop.append({"type": "command", "command": HOOK_COMMAND})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        stop = settings.get("hooks", {}).get("stop", [])
        if not stop:
            return settings
        settings["hooks"]["stop"] = [
            h for h in stop if HOOK_COMMAND not in h.get("command", "")
        ]
        if not settings["hooks"]["stop"]:
            del settings["hooks"]["stop"]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        if "conversation_id" not in payload:
            return None
        session_id = payload.get("conversation_id")
        if not isinstance(session_id, str) or not session_id:
            return None
        return HookEvent.trace(
            source_tool=self.name,
            session_id=session_id,
            transcript_path=_extract_transcript_path(payload),
        )
