"""Read/write Claude Code settings for hook and env management."""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class Scope(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"


HOOK_COMMAND = "otel-hooks hook"

ENV_KEYS = [
    "TRACE_TO_LANGFUSE",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
]


def settings_path(scope: Scope) -> Path:
    if scope is Scope.GLOBAL:
        return Path.home() / ".claude" / "settings.json"
    return Path.cwd() / ".claude" / "settings.local.json"


def load_settings(scope: Scope) -> Dict[str, Any]:
    path = settings_path(scope)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_settings(settings: Dict[str, Any], scope: Scope) -> None:
    path = settings_path(scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    tmp.replace(path)


def is_hook_registered(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> bool:
    if settings is None:
        settings = load_settings(scope)
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    for group in stop_hooks:
        for hook in group.get("hooks", []):
            if HOOK_COMMAND in hook.get("command", ""):
                return True
    return False


def is_enabled(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> bool:
    if settings is None:
        settings = load_settings(scope)
    env = settings.get("env", {})
    return (
        env.get("TRACE_TO_LANGFUSE", "").lower() == "true"
        and is_hook_registered(settings)
    )


def register_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])

    for group in stop:
        for hook in group.get("hooks", []):
            if HOOK_COMMAND in hook.get("command", ""):
                return settings

    stop.append({
        "hooks": [{"type": "command", "command": HOOK_COMMAND}]
    })
    return settings


def unregister_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    stop = settings.get("hooks", {}).get("Stop", [])
    if not stop:
        return settings
    settings["hooks"]["Stop"] = [
        group for group in stop
        if not any(
            HOOK_COMMAND in hook.get("command", "")
            for hook in group.get("hooks", [])
        )
    ]
    if not settings["hooks"]["Stop"]:
        del settings["hooks"]["Stop"]
    return settings


def set_env(settings: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
    settings.setdefault("env", {})[key] = value
    return settings


def get_env(settings: Dict[str, Any], key: str) -> Optional[str]:
    return settings.get("env", {}).get(key)


def get_env_status(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> Dict[str, Optional[str]]:
    if settings is None:
        settings = load_settings(scope)
    env = settings.get("env", {})
    return {k: env.get(k) for k in ENV_KEYS}
