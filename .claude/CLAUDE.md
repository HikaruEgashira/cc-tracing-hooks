# otel-hooks

CLI/hook tool that records AI coding tool operations as OpenTelemetry traces. v0.7.1

## Architecture

```
src/otel_hooks/
├── cli.py              # CLI entrypoint (otel-hooks command)
├── config.py           # Global/Project/env config merge
├── file_io.py          # atomic_write — all file writes go through here
├── hook.py             # Tracing hook entrypoint
├── domain/
│   └── transcript.py   # Turn dataclass, build_turns(), JSONL decode
├── runtime/
│   └── state.py        # SessionState, FileLock, incremental JSONL read
├── providers/
│   ├── __init__.py     # Provider Protocol: emit_turn / flush / shutdown
│   ├── factory.py      # create_provider()
│   ├── common.py       # Shared provider utilities
│   ├── langfuse.py
│   ├── otlp.py
│   └── datadog.py
├── tools/
│   ├── __init__.py     # ToolConfig Protocol, @register_tool, parse_hook_event()
│   ├── json_io.py      # JSON settings I/O helper
│   ├── claude.py
│   ├── cursor.py
│   ├── gemini.py
│   ├── cline.py
│   ├── codex.py
│   ├── copilot.py
│   ├── kiro.py
│   └── opencode.py
```

## Key Interfaces

- **Provider Protocol** (`providers/__init__.py`): `emit_turn(session_id, turn_num, turn, transcript_path, source_tool)`, `flush()`, `shutdown()`
- **ToolConfig Protocol** (`tools/__init__.py`): `@register_tool` decorator. `parse_event(payload) -> HookEvent | None` for tool detection
- **config.py**: Global (`~/.config/otel-hooks/config.json`) → Project (`.otel-hooks.json`) → env vars

## Data Flow

```
stdin JSON → parse_hook_event() → HookEvent(source_tool, session_id, transcript_path)
           → read_new_jsonl_lines() (incremental via SessionState)
           → decode_jsonl_lines() → build_turns() → [Turn]
           → Provider.emit_turn() → flush/shutdown
```

Config: `config.load_config()` → merged settings → `create_provider(name, config)`

## Tests

7 test files under `tests/`: integration, payload adapter, domain, provider, runtime state, registry, factory
