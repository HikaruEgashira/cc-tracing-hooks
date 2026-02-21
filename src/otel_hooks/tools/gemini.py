"""Gemini CLI tool configuration (.gemini/settings.json).

Hooks format is similar to Claude Code with grouped hook arrays.

Reference:
  - https://geminicli.com/docs/hooks/
  - https://geminicli.com/docs/hooks/reference/
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, _extract_transcript_path, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"


@register_tool
class GeminiConfig:
    @property
    def name(self) -> str:
        return "gemini"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".gemini" / "settings.json"
        return Path.cwd() / ".gemini" / "settings.json"

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        groups = settings.get("hooks", {}).get("SessionEnd", [])
        for group in groups:
            for hook in group.get("hooks", []):
                if HOOK_COMMAND in hook.get("command", ""):
                    return True
        return False

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.setdefault("hooks", {})
        session_end = hooks.setdefault("SessionEnd", [])
        for group in session_end:
            for hook in group.get("hooks", []):
                if HOOK_COMMAND in hook.get("command", ""):
                    return settings
        session_end.append({
            "hooks": [{"type": "command", "command": HOOK_COMMAND}],
        })
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        groups = settings.get("hooks", {}).get("SessionEnd", [])
        if not groups:
            return settings
        settings["hooks"]["SessionEnd"] = [
            g for g in groups
            if not any(HOOK_COMMAND in h.get("command", "") for h in g.get("hooks", []))
        ]
        if not settings["hooks"]["SessionEnd"]:
            del settings["hooks"]["SessionEnd"]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        # Gemini uses session_id like Claude but transcript_path is always empty
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return None
        # Distinguish from Claude: Gemini payloads have timestamp field
        if "timestamp" not in payload:
            return None
        tp = _extract_transcript_path(payload)
        return HookEvent.trace(
            source_tool=self.name,
            session_id=session_id,
            transcript_path=tp or None,
        )
