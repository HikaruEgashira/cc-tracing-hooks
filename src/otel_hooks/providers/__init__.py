"""Provider interface for otel-hooks."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from otel_hooks.hook import Turn


@runtime_checkable
class Provider(Protocol):
    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path) -> None: ...
    def flush(self) -> None: ...
    def shutdown(self) -> None: ...
