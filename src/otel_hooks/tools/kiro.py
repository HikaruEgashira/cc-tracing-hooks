"""Kiro CLI tool configuration (.kiro/agents/default.json).

Hooks are defined in agent configuration files with a stop trigger.

Reference:
  - https://kiro.dev/docs/cli/hooks/
  - https://kiro.dev/docs/cli/custom-agents/configuration-reference/
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool

HOOK_COMMAND = "otel-hooks hook"
AGENT_FILE = "default.json"


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
        stop_hooks = settings.get("hooks", {}).get("stop", [])
        return any(HOOK_COMMAND in h.get("command", "") for h in stop_hooks)

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.setdefault("hooks", {})
        stop = hooks.setdefault("stop", [])
        if any(HOOK_COMMAND in h.get("command", "") for h in stop):
            return settings
        stop.append({"command": HOOK_COMMAND})
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
