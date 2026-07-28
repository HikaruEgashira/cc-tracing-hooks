# Kiro Hooks Specification

> Source: https://kiro.dev/docs/cli/hooks/
> Snapshot: 2026-07-28

## Config Location

| Scope | Path |
|-------|------|
| Workspace | `.kiro/hooks/` (directory; each JSON file defines a hook set) |
| User | `~/.kiro/hooks/` (directory; each JSON file defines a hook set) |

otel-hooks writes to `otel-hooks.json` in the relevant directory.

## Config Schema

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "string (required)",
      "description": "string (optional)",
      "trigger": "string (required)",
      "matcher": "regex string (optional)",
      "action": {
        "type": "command|agent",
        "command": "string (command type)",
        "prompt": "string (agent type)"
      },
      "timeout": 60,
      "enabled": true
    }
  ]
}
```

## Hook Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Identifier for telemetry/logging |
| `description` | string | No | — | Human-readable documentation |
| `trigger` | string | Yes | — | Event type (see below) |
| `matcher` | regex | No | always-match | Filter by tool name or file path |
| `action` | object | Yes | — | Execution instructions |
| `timeout` | integer (seconds) | No | 60 | Command timeout (0 = disabled) |
| `timeout_ms` | integer (ms) | No | 30000 | Hook execution timeout (alternative to `timeout`; added 2026-07-28) |
| `cache_ttl_seconds` | integer | No | 0 | Cache successful hook results; 0 = no caching (added 2026-07-28) |
| `enabled` | boolean | No | true | Toggle hook without deletion |

### Action Types

- `command` — `{ "type": "command", "command": "shell command" }`
- `agent` — `{ "type": "agent", "prompt": "agent prompt text" }` (timeout ignored)

## Hook Events (11 total)

| Trigger | Activation | Matcher Type | Blockable |
|---------|------------|--------------|-----------|
| `AgentSpawn` | Agent activates (added 2026-07-28) | N/A | No |
| `SessionStart` | Session begins | N/A | No |
| `UserPromptSubmit` | User submits prompt | N/A | Yes |
| `Stop` | Agent completes turn | N/A | Yes (block decision via `{"decision": "block", "reason": "..."}`) |
| `PreToolUse` | Before tool executes | Tool name (regex) | Yes |
| `PostToolUse` | After tool executes | Tool name (regex) | No |
| `PreTaskExec` | Before spec task starts | N/A | Yes |
| `PostTaskExec` | After spec task finishes | N/A | No |
| `PostFileCreate` | File created by agent | File path (regex) | No |
| `PostFileSave` | File saved by agent | File path (regex) | No |
| `PostFileDelete` | File deleted by agent | File path (regex) | No |

## Common Input Fields (all events)

```json
{
  "hook_event_name": "string",
  "cwd": "string",
  "session_id": "string"
}
```

## Per-Event Additional Fields

### UserPromptSubmit

- `prompt`: string (user's input text)

### Stop

- `assistant_response`: string (the assistant's last message text)

## Tool-Related Events (PreToolUse, PostToolUse)

Additional fields:

```json
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_response": "object (PostToolUse only)"
}
```

## Tool Matcher Format

| Pattern | Description |
|---------|-------------|
| `fs_read` / `read` | Canonical name or alias |
| `fs_write` / `write` | File write |
| `execute_bash` / `shell` | Shell execution |
| `use_aws` / `aws` | AWS operations |
| `@git` | All git MCP tools |
| `@git/status` | Specific MCP tool |
| `@postgres/query` | Specific MCP tool |
| `*` | All tools |
| `@builtin` | Built-in tools only |
| (no matcher) | All tools |

## Exit Codes (command actions only)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout added to context for SessionStart/UserPromptSubmit |
| 2 | Block execution (PreToolUse, UserPromptSubmit, PreTaskExec only) — stderr returned to agent |
| Other | Warning displayed; execution continues |

## Constraints

- `timeout` applies to command actions only (not agent actions)
- `timeout: 0` disables the limit
- Blocking supported for: PreToolUse, UserPromptSubmit, PreTaskExec, Stop (via JSON `{"decision": "block", "reason": "..."}` output)
- `SessionStart` hooks are never cached
- Matcher field filters by tool name (PreToolUse/PostToolUse) or file path (PostFileCreate/PostFileSave/PostFileDelete) using regex
