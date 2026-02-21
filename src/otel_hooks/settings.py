"""Read/write Claude Code settings for hook and env management.

Backward-compatible shim — delegates to tools.claude internally.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .tools import Scope
from .tools.claude import ClaudeConfig, HOOK_COMMAND

__all__ = [
    "Scope", "HOOK_COMMAND",
    "LANGFUSE_ENV_KEYS", "OTLP_ENV_KEYS", "DATADOG_ENV_KEYS", "COMMON_ENV_KEYS", "ENV_KEYS",
    "env_keys_for_provider", "settings_path", "load_settings", "save_settings",
    "is_hook_registered", "is_enabled", "get_provider",
    "register_hook", "unregister_hook", "set_env", "get_env", "get_env_status",
]

LANGFUSE_ENV_KEYS = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
]

OTLP_ENV_KEYS = [
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_HEADERS",
]

DATADOG_ENV_KEYS = [
    "DD_SERVICE",
    "DD_ENV",
]

COMMON_ENV_KEYS = [
    "OTEL_HOOKS_PROVIDER",
    "OTEL_HOOKS_ENABLED",
]

ENV_KEYS = COMMON_ENV_KEYS + LANGFUSE_ENV_KEYS + OTLP_ENV_KEYS + DATADOG_ENV_KEYS

_claude = ClaudeConfig()


def env_keys_for_provider(provider: str) -> list[str]:
    if provider == "langfuse":
        return LANGFUSE_ENV_KEYS
    if provider == "otlp":
        return OTLP_ENV_KEYS
    if provider == "datadog":
        return DATADOG_ENV_KEYS
    return []


def settings_path(scope: Scope) -> Path:
    return _claude.settings_path(scope)


def load_settings(scope: Scope) -> Dict[str, Any]:
    return _claude.load_settings(scope)


def save_settings(settings: Dict[str, Any], scope: Scope) -> None:
    _claude.save_settings(settings, scope)


def is_hook_registered(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> bool:
    if settings is None:
        settings = load_settings(scope)
    return _claude.is_hook_registered(settings)


def is_enabled(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> bool:
    if settings is None:
        settings = load_settings(scope)
    return _claude.is_enabled(settings)


def get_provider(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> Optional[str]:
    if settings is None:
        settings = load_settings(scope)
    env = settings.get("env", {})
    provider = env.get("OTEL_HOOKS_PROVIDER", "").lower()
    return provider or None


def register_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    return _claude.register_hook(settings)


def unregister_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    return _claude.unregister_hook(settings)


def set_env(settings: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
    return _claude.set_env(settings, key, value)


def get_env(settings: Dict[str, Any], key: str) -> Optional[str]:
    return _claude.get_env(settings, key)


def get_env_status(settings: Optional[Dict[str, Any]] = None, scope: Scope = Scope.GLOBAL) -> Dict[str, Optional[str]]:
    if settings is None:
        settings = load_settings(scope)
    env = settings.get("env", {})
    return {k: env.get(k) for k in ENV_KEYS}
