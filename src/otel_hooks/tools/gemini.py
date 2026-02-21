"""Gemini CLI tool configuration (.gemini/settings.json).

Hooks format is similar to Claude Code with grouped hook arrays.

Reference:
  - https://geminicli.com/docs/hooks/
  - https://geminicli.com/docs/hooks/reference/
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool

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
        path = self.settings_path(scope)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        path = self.settings_path(scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        tmp.replace(path)

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
