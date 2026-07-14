# Cursor Hooks Specification

> Source: https://cursor.com/ja/docs/hooks (redirects to https://cursor.com/ja/docs/hooks)
> Snapshot: 2026-07-14

## Config Location

Priority (high → low): Enterprise → Team → Project → User

| Scope | Path |
|-------|------|
| Enterprise (macOS) | `/Library/Application Support/Cursor/hooks.json` |
| Enterprise (Linux/WSL) | `/etc/cursor/hooks.json` |
| Enterprise (Windows) | `C:\ProgramData\Cursor\hooks.json` |
| Team | Cloud-distributed (Enterprise only, via web dashboard) |
| Project | `<project>/.cursor/hooks.json` |
| User | `~/.cursor/hooks.json` |

All matching hooks from all sources execute. Conflicts resolved by priority.

## Config Schema

```json
{
  "version": 1,
  "hooks": {
    "<hookEventName>": [
      {
        "command": "string (required)",
        "type": "command|prompt",
        "timeout": "number (seconds, platform default)",
        "loop_limit": "number|null (default 5)",
        "failClosed": "boolean (default false)",
        "matcher": "string (regex filter)"
      }
    ]
  }
}
```

### Hook Types

- `command` (default) — shell script, communicates via stdin/stdout JSON
- `prompt` — LLM-evaluated natural language condition, returns `{ ok: boolean, reason?: string }`

### Prompt Hook Fields

```json
{
  "type": "prompt",
  "prompt": "string ($ARGUMENTS placeholder)",
  "model": "string (optional, override default)",
  "timeout": "number (seconds)"
}
```

## Hook Events (21 total: 18 Agent + 2 Tab + 1 Lifecycle)

### Agent Hooks (Cmd+K / Agent Chat)

| Event | Controllable | Description |
|-------|-------------|-------------|
| `sessionStart` | No (fire-and-forget) | New conversation created |
| `sessionEnd` | No (fire-and-forget) | Conversation ends |
| `preToolUse` | Yes (allow/deny) | Before any tool executes |
| `postToolUse` | No (observe) | After tool succeeds |
| `postToolUseFailure` | No (observe) | After tool fails/times out |
| `subagentStart` | Yes (allow/deny) | Before subagent (Task) spawns |
| `subagentStop` | No (followup) | After subagent completes |
| `beforeShellExecution` | Yes (allow/deny/ask) | Before shell command |
| `afterShellExecution` | No (observe) | After shell command |
| `beforeMCPExecution` | Yes (allow/deny/ask) | Before MCP tool call |
| `afterMCPExecution` | No (observe) | After MCP tool call |
| `beforeReadFile` | Yes (allow/deny) | Before file sent to LLM |
| `afterFileEdit` | No (observe) | After file modified |
| `beforeSubmitPrompt` | Yes (continue/block) | Before prompt sent to backend |
| `preCompact` | No (observe) | Before context compression |
| `stop` | No (followup) | Agent loop ends |
| `afterAgentResponse` | No (observe) | After assistant message |
| `afterAgentThought` | No (observe) | After thinking block |

### Tab Hooks (Inline Completion)

| Event | Controllable | Description |
|-------|-------------|-------------|
| `beforeTabFileRead` | Yes (allow/deny) | Before Tab reads file |
| `afterTabFileEdit` | No (observe) | After Tab edits file |

### Lifecycle Hooks (Outside Agent Sessions)

| Event | Controllable | Description |
|-------|-------------|-------------|
| `workspaceOpen` | No (fire-and-forget) | Workspace opens; returns plugin paths |

## Common Input Fields (all events)

```json
{
  "conversation_id": "string",
  "generation_id": "string",
  "model": "string",
  "model_id": "string (optional)",
  "model_params": [{"id": "string", "value": "string"}],
  "hook_event_name": "string",
  "cursor_version": "string",
  "workspace_roots": ["string"],
  "user_email": "string|null",
  "transcript_path": "string|null"
}
```

## Per-Event Input/Output Schemas

### sessionStart

```json
// Input
{
  "session_id": "string",
  "is_background_agent": "boolean",
  "composer_mode": "agent|ask|edit"
}
// Output
{
  "env": { "<key>": "<value>" },
  "additional_context": "string"
}
```

### sessionEnd

```json
// Input
{
  "session_id": "string",
  "reason": "completed|aborted|error|window_close|user_close",
  "duration_ms": "number",
  "is_background_agent": "boolean",
  "final_status": "string",
  "error_message": "string (optional)"
}
// Output: none (fire-and-forget)
```

### preToolUse

```json
// Input
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_use_id": "string",
  "cwd": "string",
  "model": "string",
  "agent_message": "string"
}
// Output
{
  "permission": "allow|deny",
  "user_message": "string (optional)",
  "agent_message": "string (optional)",
  "updated_input": "object (optional)"
}
```

### postToolUse

```json
// Input
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_output": "string (JSON-stringified)",
  "tool_use_id": "string",
  "cwd": "string",
  "duration": "number (ms)",
  "model": "string"
}
// Output
{
  "updated_mcp_tool_output": "object (MCP only, optional)",
  "additional_context": "string (optional)"
}
```

### postToolUseFailure

```json
// Input
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_use_id": "string",
  "cwd": "string",
  "error_message": "string",
  "failure_type": "error|timeout|permission_denied",
  "duration": "number (ms)",
  "is_interrupt": "boolean"
}
// Output: none
```

### subagentStart

```json
// Input
{
  "subagent_id": "string",
  "subagent_type": "generalPurpose|explore|shell|...",
  "task": "string",
  "parent_conversation_id": "string",
  "tool_call_id": "string",
  "subagent_model": "string",
  "is_parallel_worker": "boolean",
  "git_branch": "string (optional)"
}
// Output
{
  "permission": "allow|deny",
  "user_message": "string (optional)"
}
```

### subagentStop

```json
// Input
{
  "subagent_type": "string",
  "status": "completed|error|aborted",
  "task": "string",
  "description": "string",
  "summary": "string",
  "duration_ms": "number",
  "message_count": "number",
  "tool_call_count": "number",
  "loop_count": "number",
  "modified_files": ["string"],
  "agent_transcript_path": "string|null"
}
// Output
{
  "followup_message": "string (optional, completed only)"
}
```

### beforeShellExecution

```json
// Input
{
  "command": "string",
  "cwd": "string",
  "sandbox": "boolean"
}
// Output
{
  "permission": "allow|deny|ask",
  "user_message": "string (optional)",
  "agent_message": "string (optional)"
}
```

### afterShellExecution

```json
// Input
{
  "command": "string",
  "output": "string",
  "duration": "number (ms)",
  "sandbox": "boolean"
}
// Output: none
```

### beforeMCPExecution

```json
// Input
{
  "tool_name": "string",
  "tool_input": "string (JSON)",
  "url": "string (optional)",
  "command": "string (optional)"
}
// Output
{
  "permission": "allow|deny|ask",
  "user_message": "string (optional)",
  "agent_message": "string (optional)"
}
```

### afterMCPExecution

```json
// Input
{
  "tool_name": "string",
  "tool_input": "string",
  "result_json": "string",
  "duration": "number (ms)"
}
// Output: none
```

### beforeReadFile

```json
// Input
{
  "file_path": "string",
  "content": "string",
  "attachments": [{ "type": "file|rule", "file_path": "string" }]
}
// Output
{
  "permission": "allow|deny",
  "user_message": "string (optional)"
}
```

### afterFileEdit

```json
// Input
{
  "file_path": "string",
  "edits": [{ "old_string": "string", "new_string": "string" }]
}
// Output: none
```

### beforeTabFileRead

```json
// Input
{
  "file_path": "string",
  "content": "string"
}
// Output
{
  "permission": "allow|deny"
}
```

### afterTabFileEdit

```json
// Input
{
  "file_path": "string",
  "edits": [{
    "old_string": "string",
    "new_string": "string",
    "range": {
      "start_line_number": "number",
      "start_column": "number",
      "end_line_number": "number",
      "end_column": "number"
    },
    "old_line": "string",
    "new_line": "string"
  }]
}
// Output: none
```

### workspaceOpen

```json
// Input (omits conversation/generation/model fields)
{
  "hook_event_name": "workspaceOpen",
  "cursor_version": "string",
  "workspace_roots": ["string"],
  "user_email": "string|null"
}
// Output
{
  "pluginPaths": ["string"]
}
```

### beforeSubmitPrompt

```json
// Input
{
  "prompt": "string",
  "attachments": [{ "type": "file|rule", "file_path": "string" }]
}
// Output
{
  "continue": "boolean",
  "user_message": "string (optional)"
}
```

### afterAgentResponse

```json
// Input
{ "text": "string" }
// Output: none
```

### afterAgentThought

```json
// Input
{
  "text": "string",
  "duration_ms": "number (optional)"
}
// Output: none
```

### preCompact

```json
// Input
{
  "trigger": "auto|manual",
  "context_usage_percent": "number (0-100)",
  "context_tokens": "number",
  "context_window_size": "number",
  "message_count": "number",
  "messages_to_compact": "number",
  "is_first_compaction": "boolean"
}
// Output
{
  "user_message": "string (optional)"
}
```

### stop

```json
// Input
{
  "status": "completed|aborted|error",
  "loop_count": "number"
}
// Output
{
  "followup_message": "string (optional)"
}
```

## Matcher Targets

| Event | Matcher filters on |
|-------|--------------------|
| `preToolUse` / `postToolUse` / `postToolUseFailure` | Tool type: `Shell`, `Read`, `Write`, `Grep`, `Delete`, `Task`, `MCP:<tool_name>` |
| `subagentStart` / `subagentStop` | Subagent type: `generalPurpose`, `explore`, `shell` |
| `beforeShellExecution` / `afterShellExecution` | Shell command text |
| `beforeReadFile` | Tool type: `TabRead`, `Read` |
| `afterFileEdit` | Tool type: `TabWrite`, `Write` |
| `beforeSubmitPrompt` | `UserPromptSubmit` value |
| `stop` | `Stop` value |
| `afterAgentResponse` | `AgentResponse` value |
| `afterAgentThought` | `AgentThought` value |

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Block (equivalent to `permission: "deny"`) |
| Other | Failure — action continues (fail-open by default) |

## Environment Variables

| Variable | Always Present | Description |
|----------|---------------|-------------|
| `CURSOR_PROJECT_DIR` | Yes | Workspace root |
| `CURSOR_VERSION` | Yes | Cursor version string |
| `CURSOR_USER_EMAIL` | If logged in | Authenticated user email |
| `CURSOR_TRANSCRIPT_PATH` | If transcripts enabled | Conversation transcript path |
| `CURSOR_CODE_REMOTE` | For remote workspaces | `"true"` if remote |
| `CLAUDE_PROJECT_DIR` | Yes | Alias for compatibility |

## Cloud Agent Support

Cloud agents execute command-based hooks from `.cursor/hooks.json` only. User-level hooks are unavailable to cloud agents.

**Supported in cloud agents**: `beforeShellExecution`, `afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeSubmitPrompt`, `preCompact`, `afterAgentResponse`, `afterAgentThought`, `stop`

**Not supported in cloud agents**: `sessionStart`, `sessionEnd`, `beforeTabFileRead`, `afterTabFileEdit`, `workspaceOpen`, `beforeMCPExecution`, `afterMCPExecution`

Team/enterprise hooks are also unavailable in cloud agents.

## Constraints

- `failClosed: true` blocks action on hook failure (crash, timeout, invalid JSON); default is fail-open
- `loop_limit` (default 5) caps auto-followups from `stop` and `subagentStop`; set `null` to disable
- Cursor watches hooks.json and auto-reloads on save
- Claude Code compatible: exit code 2 = block, Claude-format hooks loaded via Third Party Hooks
