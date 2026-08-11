# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-08-11

## Config Location

Hooks can be defined in dedicated hook files or inline within settings files:

| Scope | Path |
|-------|------|
| Policy (Linux/macOS) | `/etc/github-copilot/policy.d/*.json` |
| Policy (Windows) | `C:\ProgramData\GitHub\Copilot\policy.d\*.json` |
| Policy (Windows Registry) | `HKLM\Software\Policies\GitHub\Copilot` (REG_SZ values) |
| Project (repository) — dedicated file | `.github/hooks/<name>.json` |
| Project (repository) — inline | `.github/copilot/settings.json` or `.github/copilot/settings.local.json` (under `hooks` key) |
| User (CLI) — dedicated file | `~/.copilot/hooks/` |
| User (CLI) — inline | `~/.copilot/settings.json` (under `hooks` key) |
| Plugin-contributed | `hooks.json` (provided by plugin) |

Load order: Policy → User → Project → Plugins. Hooks from all sources combine.

Cloud Agent: only `.github/hooks/*.json` files loaded; policy, user-level, and plugin hooks unavailable.
Cloud agents run in a Linux sandbox; only `bash` field honored (not `powershell`); network is restricted.

Policy hooks cannot be disabled by `disableAllHooks`. Policy files (POSIX) must be root-owned and not group/world-writable.

## Config Schema

```json
{
  "version": 1,
  "hooks": {
    "<hookEventName>": [
      {
        "type": "command",
        "bash": "string (script path)",
        "powershell": "string (script path)",
        "command": "string (cross-platform path)",
        "cwd": "string (optional)",
        "env": { "<key>": "<value>" },
        "timeoutSec": 30,
        "comment": "string (optional)"
      }
    ]
  },
  "disableAllHooks": true
}
```

### Hook Types

- `command` — shell script; `bash` (Linux/macOS), `powershell` (Windows), or cross-platform `command`
- `http` — POST JSON payload; fields: `url`, `headers`, `allowedEnvVars`, `timeoutSec`
- `prompt` — auto-submit text; fields: `prompt`

**Progress Messages** (command hooks): Hooks may emit transient status updates to stdout before the final JSON output:

```json
{"type": "progress", "message": "Checking policy..."}
{"type": "progress", "message": "Routing...", "temporary": true}
```

Lines with `"type": "progress"` are consumed and displayed as status; they are excluded from hook output parsing.

### Matcher Filtering

Optional regex patterns supported for: `notification`, `permissionRequest`, `postToolUse`, `preCompact`, `preToolUse`, `subagentStart`

## Hook Events (14 total)

| Event | Has Output | Description |
|-------|-----------|-------------|
| sessionStart | Yes | New or resumed session begins; can inject `additionalContext` |
| sessionEnd | No | Session completes or terminates |
| userPromptSubmitted | Yes | User submits a prompt; can return `modifiedPrompt` (SDK hooks only) |
| userPromptTransformed | Yes | After prompt transformation, before model receives it |
| preToolUse | Yes | Before tool execution (can deny) |
| postToolUse | Yes | After tool execution (can modify result) |
| postToolUseFailure | Yes | After a tool completes with a failure; can return `additionalContext` |
| errorOccurred | No | Error during execution |
| agentStop | Yes | Main agent finishes a turn (can block; 8-consecutive-block runaway guard) |
| notification | Yes | Async system notification (CLI only); can return `additionalContext` |
| permissionRequest | Yes | Before permission service runs (CLI only) |
| preCompact | No | Context compaction is about to begin |
| subagentStart | Yes | A subagent is spawned; can inject context (cannot block) |
| subagentStop | Yes | A subagent completes (can block) |

## Per-Event Input Schemas

### sessionStart

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "source": "new|resume|startup",
  "initialPrompt": "string"
}
```

Output:
```json
{
  "additionalContext": "string (optional, injected into session)"
}
```

### sessionEnd

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "reason": "complete|error|abort|timeout|user_exit"
}
```

### userPromptSubmitted

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string"
}
```

Output (SDK programmatic hooks only; command/HTTP hooks output is dropped):
```json
{
  "modifiedPrompt": "string"
}
```

### userPromptTransformed

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string",
  "transformedPrompt": "string"
}
```

Output:
```json
{
  "modifiedTransformedPrompt": "string"
}
```

### preToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)"
}
```

### postToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)",
  "toolResult": {
    "resultType": "success|failure|denied",
    "textResultForLlm": "string"
  }
}
```

### postToolUseFailure

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)",
  "error": "string"
}
```

Output:
```json
{
  "additionalContext": "string (optional, recovery guidance for the model)"
}
```

### errorOccurred

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "error": {
    "message": "string",
    "name": "string",
    "stack": "string (optional)"
  },
  "errorContext": "model_call|tool_execution|system|user_input",
  "recoverable": "boolean"
}
```

### agentStop

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "stopReason": "string",
  "stop_hook_active": "boolean (true when a previous Stop hook blocked)"
}
```

### subagentStart

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "agentDescription": "string (optional)"
}
```

### subagentStop

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "agentId": "string",
  "agentType": "string",
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "response": "string (subagent's final response text)",
  "stopReason": "string"
}
```

### preCompact

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "trigger": "manual|auto",
  "customInstructions": "string"
}
```

### notification

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "hook_event_name": "Notification",
  "message": "string",
  "title": "string (optional)",
  "notification_type": "shell_completed|shell_detached_completed|agent_completed|agent_idle|permission_prompt|elicitation_dialog"
}
```

Output:
```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

## Output (events with output)

### preToolUse

```json
{
  "permissionDecision": "allow|deny|ask",
  "permissionDecisionReason": "string",
  "modifiedArgs": "object (optional)"
}
```

Note: only `deny` is processed.

### postToolUse

```json
{
  "modifiedResult": {
    "resultType": "success",
    "textResultForLlm": "string"
  },
  "additionalContext": "string (optional)"
}
```

### subagentStart

```json
{
  "additionalContext": "string (optional, prepended to subagent prompt; cannot block)"
}
```

### agentStop

```json
{
  "decision": "block|allow",
  "reason": "string"
}
```

### subagentStop

```json
{
  "decision": "block|allow",
  "reason": "string",
  "modifiedResponse": "string (optional, replaces subagent response returned to parent)"
}
```

### permissionRequest

```json
{
  "behavior": "allow|deny",
  "message": "string",
  "interrupt": "boolean"
}
```

### notification

```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Warning — stderr surfaced but execution continues |
| Other | Logged failure — execution continues |

## Supported Tool Names (for `preToolUse` matcher)

`ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`, `rg`, `str_replace_editor`, `apply_patch`, `web_search`, `update_todo`

### Claude Tool Name Mappings (PascalCase matchers)

| Runtime name | Claude name |
|---|---|
| `bash`, `powershell` | `Bash` |
| `view` | `Read` |
| `create` | `Write` |
| `edit`, `str_replace_editor`, `apply_patch` | `Edit` |
| `grep`, `rg` | `Grep` |
| `glob` | `Glob` |
| `web_fetch` | `WebFetch` |
| `web_search` | `WebSearch` |
| `ask_user` | `AskUserQuestion` |
| `update_todo` | `TodoWrite` |
| `task` | `Agent` (`Task` also accepted) |

## Cloud Agent Execution Environment

| Property | Value |
|----------|-------|
| OS | Linux; only `bash` field honored |
| Working directory | `/workspace` (repo) or `/root` |
| Filesystem | Ephemeral; discarded when job ends |
| Network | Restricted; only GitHub/Copilot reachable |
| Environment | `GITHUB_COPILOT_API_TOKEN`, `GITHUB_COPILOT_GIT_TOKEN`, `COPILOT_AGENT_PROMPT`, `HOME=/root` set; `GITHUB_TOKEN` not set |
| Interactivity | Non-interactive; all tool permissions pre-granted |
| Config | Only `.github/hooks/*.json` loaded |

## Constraints

- Default timeout: 30 seconds (`timeoutSec`; the `timeout` field is a deprecated alias)
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- `transcriptPath` now included in `agentStop`, `subagentStart`, `subagentStop`, `preCompact`
- `preToolUse` is **fail-closed**: crashes, non-zero exits (other than 2), and timeouts all deny the tool call
- **Runaway guard**: After 8 consecutive `block` decisions from `agentStop`, the CLI overrides and ends the turn
- Hook output bounded at **10 MiB** per invocation; `additionalContext` capped at **10 KB** when multiple hooks return it
- HTTP hooks require HTTPS by default for permission events; HTTP allowed for localhost only with `COPILOT_HOOK_ALLOW_LOCALHOST=1`
