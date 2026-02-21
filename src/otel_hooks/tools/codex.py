"""Codex CLI tool configuration (~/.codex/config.toml).

Reference:
  - https://github.com/openai/codex/blob/main/docs/config.md
  - https://developers.openai.com/codex/config-reference
"""

import base64
import os
from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool

CONFIG_PATH = Path.home() / ".codex" / "config.toml"


def _read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _dump_toml(data: Dict[str, Any]) -> str:
    """Serialize a simple dict to TOML (flat keys + one level of tables)."""
    lines: list[str] = []
    # Top-level scalar keys first
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(f"{k} = {_toml_value(v)}")
    # Then table sections
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"\n[{k}]")
            for sk, sv in v.items():
                lines.append(f"{sk} = {_toml_value(sv)}")
    return "\n".join(lines) + "\n"


def _toml_value(v: Any) -> str:
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    return f'"{v}"'


def _write_toml(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(_dump_toml(data), encoding="utf-8")
    tmp.replace(path)


def _langfuse_otlp_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/public/otel/v1/traces"


def _langfuse_auth_header(public_key: str, secret_key: str) -> str:
    creds = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return f"Basic {creds}"


@register_tool
class CodexConfig:
    @property
    def name(self) -> str:
        return "codex"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL]

    def settings_path(self, scope: Scope) -> Path:
        return CONFIG_PATH

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return _read_toml(CONFIG_PATH)

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        _write_toml(settings, CONFIG_PATH)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        # Codex uses native OTLP, no hooks needed
        return "otel" in settings

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return "otel" in settings

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        # No hooks for Codex; configure [otel] section instead
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings.pop("otel", None)
        return settings

    def enable_otlp(self, settings: Dict[str, Any], endpoint: str, headers: str = "") -> Dict[str, Any]:
        settings["otel"] = {
            "exporter": "otlp-http",
            "endpoint": endpoint,
        }
        if headers:
            settings["otel"]["headers"] = headers
        return settings

    def enable_langfuse(self, settings: Dict[str, Any], public_key: str, secret_key: str,
                        base_url: str = "https://cloud.langfuse.com") -> Dict[str, Any]:
        endpoint = _langfuse_otlp_endpoint(base_url)
        auth = _langfuse_auth_header(public_key, secret_key)
        settings["otel"] = {
            "exporter": "otlp-http",
            "endpoint": endpoint,
            "headers": f"Authorization={auth}",
        }
        return settings
