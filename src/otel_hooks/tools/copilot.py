"""GitHub Copilot tool configuration (.github/hooks/otel-hooks.json).

Works with both GitHub Copilot CLI and VS Code Copilot agent.

Reference:
  - https://docs.github.com/en/copilot/reference/hooks-configuration
  - https://docs.github.com/en/copilot/how-tos/copilot-cli/use-hooks
  - https://code.visualstudio.com/docs/copilot/customization/hooks
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool

HOOK_COMMAND = "otel-hooks hook"
HOOKS_FILE = "otel-hooks.json"


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
        path = self.settings_path(scope)
        if not path.exists():
            return {"version": 1, "hooks": {}}
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
        session_end.append({
            "type": "command",
            "bash": HOOK_COMMAND,
            "comment": "otel-hooks: emit tracing data",
        })
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
