"""Cline tool configuration (.clinerules/hooks/).

Cline hooks are executable scripts that receive JSON via stdin and
return JSON via stdout. This tool creates a shell script wrapper.

Reference:
  - https://docs.cline.bot/customization/hooks
  - https://cline.bot/blog/cline-v3-36-hooks
"""

import os
from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, register_tool

HOOK_COMMAND = "otel-hooks hook"
HOOK_SCRIPT = "TaskComplete"


@register_tool
class ClineConfig:
    @property
    def name(self) -> str:
        return "cline"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / ".clinerules" / "hooks" / HOOK_SCRIPT

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        path = self.settings_path(scope)
        if not path.exists():
            return {}
        content = path.read_text(encoding="utf-8")
        return {"_script": content, "_exists": True}

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        path = self.settings_path(scope)
        if "_delete" in settings:
            if path.exists():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        script = settings.get("_script", "")
        tmp = path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o755)
        try:
            os.write(fd, script.encode("utf-8"))
        finally:
            os.close(fd)
        tmp.replace(path)
        os.chmod(path, 0o755)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        return HOOK_COMMAND in settings.get("_script", "")

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        cmd = command or HOOK_COMMAND
        if cmd in settings.get("_script", ""):
            return settings
        existing = settings.get("_script", "")
        if existing and cmd not in existing:
            settings["_script"] = existing.rstrip("\n") + f"\n{cmd}\n"
        else:
            settings["_script"] = f"#!/bin/sh\n# otel-hooks: emit tracing data on task completion\n{cmd}\n"
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        script = settings.get("_script", "")
        if not script:
            return settings
        lines = [line for line in script.splitlines() if HOOK_COMMAND not in line]
        remaining = "\n".join(lines).strip()
        if not remaining or remaining == "#!/bin/sh":
            settings["_delete"] = True
        else:
            settings["_script"] = remaining + "\n"
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        task_id = payload.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            return None
        return HookEvent.trace(source_tool=self.name, session_id=task_id, transcript_path=None)
