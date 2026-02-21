"""Claude Code tool configuration."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from . import Scope, register_tool

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
        stop_hooks = settings.get("hooks", {}).get("Stop", [])
        for group in stop_hooks:
            for hook in group.get("hooks", []):
                if HOOK_COMMAND in hook.get("command", ""):
                    return True
        return False

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        if not self.is_hook_registered(settings):
            return False
        env = settings.get("env", {})
        return env.get("OTEL_HOOKS_ENABLED", "").lower() == "true"

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.setdefault("hooks", {})
        stop = hooks.setdefault("Stop", [])
        for group in stop:
            for hook in group.get("hooks", []):
                if HOOK_COMMAND in hook.get("command", ""):
                    return settings
        stop.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
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

    def set_env(self, settings: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
        settings.setdefault("env", {})[key] = value
        return settings

    def get_env(self, settings: Dict[str, Any], key: str) -> Optional[str]:
        return settings.get("env", {}).get(key)
