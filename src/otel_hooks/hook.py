# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Tracing hook entrypoint."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from otel_hooks.tools import SupportKind, parse_hook_event
from otel_hooks.domain.transcript import build_turns, decode_jsonl_lines
from otel_hooks.providers.factory import create_provider
from otel_hooks.runtime.state import (
    DEFAULT_STATE_DIR,
    FileLock,
    StatePaths,
    build_state_paths,
    load_session_state,
    load_state,
    read_new_jsonl_lines,
    save_state,
    state_key,
    write_session_state,
)


def _log(log_file: Path, level: str, message: str) -> None:
    try:
        from otel_hooks.file_io import append_line

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        append_line(log_file, f"{ts} [{level}] {message}\n")
    except Exception:
        pass


def _resolve_state_paths(config: dict[str, Any]) -> StatePaths:
    configured = config.get("state_dir")
    if configured:
        try:
            base = Path(str(configured)).expanduser().resolve()
            return build_state_paths(base)
        except Exception:
            pass
    return build_state_paths(DEFAULT_STATE_DIR)


def read_hook_payload() -> dict[str, Any]:
    try:
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except Exception:
        return {}


def run_hook(
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    provider_factory=create_provider,
) -> int:
    start = time.time()
    debug_enabled = bool(config.get("debug", False))
    runtime_state_paths = _resolve_state_paths(config)
    log_file = runtime_state_paths.state_dir / "otel_hook.log"

    def debug(msg: str) -> None:
        if debug_enabled:
            _log(log_file, "DEBUG", msg)

    def info(msg: str) -> None:
        _log(log_file, "INFO", msg)

    def warn(msg: str) -> None:
        _log(log_file, "WARN", msg)

    if not config.get("enabled", False):
        return 0

    provider_name = config.get("provider", "")
    if not provider_name:
        return 0

    event = parse_hook_event(payload, warn_fn=warn)

    if event is None:
        debug("No matching adapter for payload; exiting.")
        return 0

    if event.kind is SupportKind.TRACE:
        if event.transcript_path is not None and not event.transcript_path.exists():
            debug("Transcript file not found; exiting.")
            return 0
        if event.transcript_path is None:
            debug(f"No transcript path for {event.source_tool}; session-only trace not yet supported.")
            return 0

    provider = provider_factory(provider_name, config)
    if not provider:
        return 0

    emitted = 0
    try:
        if event.kind is SupportKind.METRICS:
            try:
                provider.emit_metric(
                    event.metric_name,
                    event.metric_value,
                    event.metric_attributes or {},
                    event.source_tool,
                    event.session_id,
                )
                emitted = 1
            except Exception as e:
                debug(f"emit_metric failed: {e}")
            try:
                provider.flush()
            except Exception:
                pass
            duration = time.time() - start
            info(
                f"Processed metric {event.metric_name} in {duration:.2f}s "
                f"(session={event.session_id or '-'}, provider={provider_name})"
            )
            return 0

        with FileLock(runtime_state_paths.lock_file):
            state = load_state(runtime_state_paths.state_file)
            key = state_key(event.session_id, str(event.transcript_path))
            ss = load_session_state(state, key)

            lines, ss = read_new_jsonl_lines(event.transcript_path, ss)
            if not lines:
                write_session_state(state, key, ss)
                save_state(state, runtime_state_paths.state_file)
                return 0

            msgs = decode_jsonl_lines(lines)
            turns = build_turns(msgs)
            if not turns:
                write_session_state(state, key, ss)
                save_state(state, runtime_state_paths.state_file)
                return 0

            for turn in turns:
                turn_num = ss.turn_count + emitted + 1
                try:
                    provider.emit_turn(
                        event.session_id,
                        turn_num,
                        turn,
                        event.transcript_path,
                        event.source_tool,
                    )
                except Exception as e:
                    debug(f"emit_turn failed: {e}")
                    continue
                emitted += 1

            ss.turn_count += emitted
            write_session_state(state, key, ss)
            save_state(state, runtime_state_paths.state_file)

        try:
            provider.flush()
        except Exception:
            pass

        duration = time.time() - start
        info(
            f"Processed {emitted} turns in {duration:.2f}s "
            f"(session={event.session_id}, provider={provider_name})"
        )
        return 0
    except Exception as e:
        debug(f"Unexpected failure: {e}")
        return 0
    finally:
        try:
            provider.shutdown()
        except Exception:
            pass


def main() -> int:
    try:
        from otel_hooks.config import load_config

        config = load_config()
    except Exception:
        config = {}
    payload = read_hook_payload()
    return run_hook(payload, config)


if __name__ == "__main__":
    sys.exit(main())
