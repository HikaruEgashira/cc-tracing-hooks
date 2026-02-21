"""OpenCode tool configuration (opencode.json).

Reference:
  - https://opencode.ai/docs/config/
  - https://opencode.ai/docs/plugins/
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool

HOOK_COMMAND = "otel-hooks hook"


@register_tool
class OpenCodeConfig:
    @property
    def name(self) -> str:
        return "opencode"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / "opencode.json"

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
        hooks = settings.get("experimental", {}).get("hook", {}).get("session_completed", [])
        return any(HOOK_COMMAND in " ".join(h.get("command", [])) for h in hooks)

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        experimental = settings.setdefault("experimental", {})
        hook = experimental.setdefault("hook", {})
        session_completed = hook.setdefault("session_completed", [])
        if any(HOOK_COMMAND in " ".join(h.get("command", [])) for h in session_completed):
            return settings
        session_completed.append({"command": ["otel-hooks", "hook"]})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("experimental", {}).get("hook", {}).get("session_completed", [])
        if not hooks:
            return settings
        settings["experimental"]["hook"]["session_completed"] = [
            h for h in hooks if HOOK_COMMAND not in " ".join(h.get("command", []))
        ]
        if not settings["experimental"]["hook"]["session_completed"]:
            del settings["experimental"]["hook"]["session_completed"]
        return settings
