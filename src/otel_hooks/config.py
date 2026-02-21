"""otel-hooks unified configuration.

Config files:
  - Global:  ~/.config/otel-hooks/config.json
  - Project: .otel-hooks.json (repository root)

Merge order: global → project → environment variables (highest priority).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .tools import Scope


def config_path(scope: Scope) -> Path:
    if scope is Scope.PROJECT or scope is Scope.LOCAL:
        return Path.cwd() / ".otel-hooks.json"
    return Path.home() / ".config" / "otel-hooks" / "config.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# Mapping: config key → (section, field) → env var name
_ENV_OVERRIDES: list[tuple[str, str]] = [
    ("provider", "OTEL_HOOKS_PROVIDER"),
    ("enabled", "OTEL_HOOKS_ENABLED"),
    ("debug", "OTEL_HOOKS_DEBUG"),
    ("max_chars", "OTEL_HOOKS_MAX_CHARS"),
]

_PROVIDER_ENV: Dict[str, list[tuple[str, str]]] = {
    "langfuse": [
        ("public_key", "LANGFUSE_PUBLIC_KEY"),
        ("secret_key", "LANGFUSE_SECRET_KEY"),
        ("base_url", "LANGFUSE_BASE_URL"),
    ],
    "otlp": [
        ("endpoint", "OTEL_EXPORTER_OTLP_ENDPOINT"),
        ("headers", "OTEL_EXPORTER_OTLP_HEADERS"),
    ],
    "datadog": [
        ("service", "DD_SERVICE"),
        ("env", "DD_ENV"),
    ],
}


def load_config() -> Dict[str, Any]:
    """Load merged config: global → project → env vars."""
    global_cfg = _read_json(config_path(Scope.GLOBAL))
    project_cfg = _read_json(config_path(Scope.PROJECT))

    # Merge: project overrides global
    merged: Dict[str, Any] = {**global_cfg}
    for k, v in project_cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v

    # Environment variables override everything
    _apply_env_overrides(merged)

    return merged



def _apply_env_overrides(merged: Dict[str, Any]) -> None:
    """Environment variables override all config sources."""
    for config_key, env_var in _ENV_OVERRIDES:
        val = os.environ.get(env_var)
        if val:
            if config_key == "enabled":
                merged[config_key] = val.lower() == "true"
            elif config_key == "max_chars":
                try:
                    merged[config_key] = int(val)
                except ValueError:
                    pass
            elif config_key == "debug":
                merged[config_key] = val.lower() == "true"
            else:
                merged[config_key] = val

    provider = merged.get("provider", "")
    if provider and provider in _PROVIDER_ENV:
        section = merged.setdefault(provider, {})
        for field, env_var in _PROVIDER_ENV[provider]:
            val = os.environ.get(env_var)
            if val:
                section[field] = val


def save_config(data: Dict[str, Any], scope: Scope) -> None:
    """Save config to the specified scope."""
    path = config_path(scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    tmp.replace(path)


def get_provider_config(config: Dict[str, Any], provider: str) -> Dict[str, str]:
    """Extract provider-specific config as flat key-value pairs."""
    return config.get(provider, {})


def env_keys_for_provider(provider: str) -> list[tuple[str, str]]:
    """Return (config_field, env_var_name) pairs for a provider."""
    return _PROVIDER_ENV.get(provider, [])
