"""Codex CLI tool configuration (~/.codex/config.toml).

Reference:
  - https://github.com/openai/codex/blob/main/docs/config.md
  - https://developers.openai.com/codex/config-reference

Codex [otel] schema (from config.schema.json):
  exporter is a tagged enum (OtelExporterKind):
    - "none" | "statsig"
    - { "otlp-http": { endpoint, headers: {k: v}, ... } }
    - { "otlp-grpc": { endpoint, headers: {k: v}, ... } }
"""

import base64
from pathlib import Path
from typing import Any, Dict, Optional

from . import HookEvent, Scope, register_tool

CONFIG_PATH = Path.home() / ".codex" / "config.toml"


def _read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _write_toml(data: Dict[str, Any], path: Path) -> None:
    import tomli_w

    from otel_hooks.file_io import atomic_write

    atomic_write(path, tomli_w.dumps(data).encode("utf-8"))


def _parse_headers(raw: str) -> Dict[str, str]:
    """Parse 'Key=Value' or 'Key=Value,Key2=Value2' into a dict."""
    headers: Dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            headers[k.strip()] = v.strip()
    return headers


def _langfuse_otlp_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/public/otel/v1/traces"


def _langfuse_auth_header(public_key: str, secret_key: str) -> str:
    creds = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return f"Basic {creds}"


def _get_exporter_config(settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the otlp-http exporter config from the nested structure."""
    exporter = settings.get("otel", {}).get("exporter", {})
    if isinstance(exporter, dict):
        return exporter.get("otlp-http") or exporter.get("otlp-grpc")
    return None


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
        return _get_exporter_config(settings) is not None

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return _get_exporter_config(settings) is not None

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings.pop("otel", None)
        return settings

    def set_env(self, settings: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
        return settings

    def get_env(self, settings: Dict[str, Any], key: str) -> Optional[str]:
        cfg = _get_exporter_config(settings)
        if cfg is None:
            return None
        mapping = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "endpoint",
            "OTEL_EXPORTER_OTLP_HEADERS": "headers",
        }
        val = cfg.get(mapping.get(key, ""))
        if isinstance(val, dict):
            return ",".join(f"{k}={v}" for k, v in val.items())
        return val

    def enable_otlp(self, settings: Dict[str, Any], endpoint: str, headers: str = "") -> Dict[str, Any]:
        exporter_cfg: Dict[str, Any] = {"endpoint": endpoint, "protocol": "json"}
        if headers:
            exporter_cfg["headers"] = _parse_headers(headers)
        settings["otel"] = {"exporter": {"otlp-http": exporter_cfg}}
        return settings

    def enable_langfuse(self, settings: Dict[str, Any], public_key: str, secret_key: str,
                        base_url: str = "https://cloud.langfuse.com") -> Dict[str, Any]:
        endpoint = _langfuse_otlp_endpoint(base_url)
        auth = _langfuse_auth_header(public_key, secret_key)
        settings["otel"] = {
            "exporter": {
                "otlp-http": {
                    "endpoint": endpoint,
                    "protocol": "json",
                    "headers": {"Authorization": auth},
                },
            },
        }
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        # Codex uses notify with thread-id; hooks not yet implemented
        thread_id = payload.get("thread-id")
        if not isinstance(thread_id, str) or not thread_id:
            return None
        return HookEvent.trace(source_tool=self.name, session_id=thread_id, transcript_path=None)
