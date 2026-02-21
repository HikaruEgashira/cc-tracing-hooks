"""Tool configuration registry for multi-tool support."""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Protocol, runtime_checkable


class Scope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    LOCAL = "local"


class SupportKind(str, Enum):
    TRACE = "trace"
    METRICS = "metrics"


@dataclass(frozen=True)
class HookEvent:
    source_tool: str
    kind: SupportKind
    session_id: str
    transcript_path: Path | None
    metric_name: str = ""
    metric_value: float = 0.0
    metric_attributes: dict[str, str] | None = None

    @classmethod
    def trace(cls, *, source_tool: str, session_id: str, transcript_path: Path | None) -> "HookEvent":
        return cls(
            source_tool=source_tool,
            kind=SupportKind.TRACE,
            session_id=session_id,
            transcript_path=transcript_path,
        )

    @classmethod
    def metric(
        cls,
        *,
        source_tool: str,
        metric_name: str,
        metric_value: float = 1.0,
        metric_attributes: dict[str, str] | None = None,
        session_id: str = "",
    ) -> "HookEvent":
        return cls(
            source_tool=source_tool,
            kind=SupportKind.METRICS,
            session_id=session_id,
            transcript_path=None,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_attributes=metric_attributes,
        )


@runtime_checkable
class ToolConfig(Protocol):
    """Protocol for tool-specific configuration backends."""

    @property
    def name(self) -> str: ...

    def settings_path(self, scope: Scope) -> Path: ...
    def load_settings(self, scope: Scope) -> Dict[str, Any]: ...
    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None: ...
    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]: ...
    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]: ...
    def scopes(self) -> list[Scope]: ...
    def is_hook_registered(self, settings: Dict[str, Any]) -> bool: ...
    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None: ...


TOOL_REGISTRY: Dict[str, type[ToolConfig]] = {}


def register_tool(cls: type[ToolConfig]) -> type[ToolConfig]:
    """Class decorator to register a tool config."""
    instance = cls()
    TOOL_REGISTRY[instance.name] = cls
    return cls


def get_tool(name: str) -> ToolConfig:
    """Get a tool config instance by name."""
    _ensure_registered()
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}. Available: {list(TOOL_REGISTRY.keys())}")
    return TOOL_REGISTRY[name]()


def available_tools() -> list[str]:
    """Return names of all registered tools."""
    _ensure_registered()
    return sorted(TOOL_REGISTRY.keys())


def _ensure_registered() -> None:
    """Import all tool modules to trigger @register_tool decorators."""
    if TOOL_REGISTRY:
        return
    package_name = __name__
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith("_") or module.name in {"json_io"}:
            continue
        importlib.import_module(f"{package_name}.{module.name}")


# Tools with more specific payload matching should be tried first.
# Claude matches broadly on session_id, so more specific tools go first.
_PARSE_ORDER: tuple[str, ...] = ("opencode", "cursor", "gemini", "kiro", "copilot", "cline", "codex", "claude")


def parse_hook_event(
    payload: Dict[str, Any], warn_fn: Callable[[str], None] | None = None
) -> HookEvent | None:
    """Parse tool payload into a normalized HookEvent via registered adapters."""
    _ensure_registered()
    source_tool = payload.get("source_tool")
    if isinstance(source_tool, str) and source_tool in TOOL_REGISTRY:
        hinted = TOOL_REGISTRY[source_tool]().parse_event(payload)
        if hinted is not None:
            return hinted

    seen: set[str] = set()
    for name in _PARSE_ORDER:
        if name in TOOL_REGISTRY:
            seen.add(name)
            event = TOOL_REGISTRY[name]().parse_event(payload)
            if event is not None:
                return event
    for name, cls in TOOL_REGISTRY.items():
        if name not in seen:
            event = cls().parse_event(payload)
            if event is not None:
                return event
    return None


def _extract_transcript_path(payload: Dict[str, Any]) -> Path | None:
    """Shared helper: extract transcript path from common payload keys."""
    transcript = (
        payload.get("transcriptPath")
        or payload.get("transcript_path")
        or payload.get("transcript", {}).get("path")
    )
    if not transcript:
        return None
    try:
        return Path(transcript).expanduser().resolve()
    except Exception:
        return None
