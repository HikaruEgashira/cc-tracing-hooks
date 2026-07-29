"""Kiro CLI tool configuration (.kiro/hooks/).

Reference:
  - https://kiro.dev/docs/cli/hooks/
"""

from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool
from .json_io import load_json, save_json

HOOKS_DIR = "hooks"
HOOK_FILE = "otel-hooks.json"
_HOOK_EVENTS = (
    "AgentSpawn",
    "SessionStart",
    "UserPromptSubmit",
    "Stop",
    "PreToolUse",
    "PostToolUse",
    "PreTaskExec",
    "PostTaskExec",
    "PostFileCreate",
    "PostFileSave",
    "PostFileDelete",
)


@register_tool
class KiroConfig:
    @property
    def name(self) -> str:
        return "kiro"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".kiro" / HOOKS_DIR / HOOK_FILE
        return Path.cwd() / ".kiro" / HOOKS_DIR / HOOK_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", [])
        if not isinstance(hooks, list):
            return False
        registered = {
            hook.get("trigger")
            for hook in hooks
            if isinstance(hook, dict)
            and "otel-hooks hook" in hook.get("action", {}).get("command", "")
        }
        return all(event in registered for event in _HOOK_EVENTS)

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        base_cmd = command or "otel-hooks hook"
        cmd = f"{base_cmd} --tool kiro"
        settings.setdefault("version", "v1")
        hooks = settings.setdefault("hooks", [])
        existing = {
            hook.get("trigger")
            for hook in hooks
            if isinstance(hook, dict)
            and "otel-hooks hook" in hook.get("action", {}).get("command", "")
        }
        for trigger in _HOOK_EVENTS:
            if trigger not in existing:
                hooks.append({
                    "name": "otel-hooks",
                    "trigger": trigger,
                    "action": {"type": "command", "command": cmd},
                })
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", [])
        settings["hooks"] = [
            hook for hook in hooks
            if not (
                isinstance(hook, dict)
                and "otel-hooks hook" in hook.get("action", {}).get("command", "")
            )
        ]
        return settings
