"""Tool configuration registry for multi-tool support."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Protocol, runtime_checkable


class Scope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    LOCAL = "local"


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
    def is_enabled(self, settings: Dict[str, Any]) -> bool: ...


TOOL_REGISTRY: Dict[str, type] = {}


def register_tool(cls: type) -> type:
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
    return list(TOOL_REGISTRY.keys())


def _ensure_registered() -> None:
    """Import all tool modules to trigger @register_tool decorators."""
    if len(TOOL_REGISTRY) >= 8:
        return
    from . import claude as _claude  # noqa: F811,F401
    from . import cursor as _cursor  # noqa: F401
    from . import codex as _codex  # noqa: F401
    from . import opencode as _opencode  # noqa: F401
    from . import copilot as _copilot  # noqa: F401
    from . import gemini as _gemini  # noqa: F401
    from . import kiro as _kiro  # noqa: F401
    from . import cline as _cline  # noqa: F401
