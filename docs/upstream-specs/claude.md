# Claude Code Hooks Specification

> Source: https://code.claude.com/docs/en/hooks
> Snapshot: 2026-08-04

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.claude/settings.json` |
| Project | `.claude/settings.json` |
| Local | `.claude/settings.local.json` |
| Plugin | `hooks/hooks.json` (when plugin enabled) |
| Skill/Agent | Frontmatter (while component active) |

## Config Schema

```json
{
  "hooks": {
    "<HookEventName>": [
      {
        "matcher": "regex_pattern_or_*",
        "hooks": [
          {
            "type": "command",
            "command": "string",
            "async": false,
            "asyncRewake": false,
            "shell": "bash",
            "timeout": 600,
            "statusMessage": "string",
            "once": false,
            "if": "permission_rule_syntax"
          }
        ]
      }
    ]
  },
  "disableAllHooks": false
}
```

### Hook Types

- `command` — shell command (`command`, `args`, `async`, `asyncRewake`, `shell`); when `args` present uses exec form (no shell)
- `http` — POST request (`url`, `headers`, `allowedEnvVars`)
- `mcp_tool` — MCP tool call (`server`, `tool`, `input` with `${path}` substitution)
- `prompt` — LLM prompt (`prompt`, `model`)
- `agent` — agent invocation (`prompt`, `model`) [experimental]

## Hook Events (31 total)

| Event | Blockable | Matcher Target |
|-------|-----------|----------------|
| SessionStart | No | source: `startup\|resume\|clear\|compact\|fork` |
| Setup | No | trigger: `init\|maintenance` |
| InstructionsLoaded | No | load_reason: `session_start\|nested_traversal\|path_glob_match\|include\|compact` |
| UserPromptSubmit | Yes (exit 2) | — |
| UserPromptExpansion | Yes (exit 2) | command_name |
| PreToolUse | Yes (exit 2) | tool_name |
| PermissionRequest | Yes (exit 2) | tool_name |
| PermissionDenied | No | tool_name |
| PostToolUse | Yes (exit 2) | tool_name |
| PostToolUseFailure | Yes (exit 2) | tool_name |
| PostToolBatch | Yes (exit 2) | — |
| Notification | No | notification_type |
| MessageDisplay | No | — |
| SubagentStart | No | agent_type |
| SubagentStop | Yes (exit 2) | agent_type |
| TaskCreated | Yes (exit 2) | — |
| TaskCompleted | Yes (exit 2) | — |
| Stop | Yes (exit 2) | — |
| StopFailure | No | error_type: `rate_limit\|overloaded\|authentication_failed\|...` |
| TeammateIdle | Yes (exit 2) | — |
| ConfigChange | Yes (exit 2) | source |
| CwdChanged | No | — |
| DirectoryAdded | No | — |
| FileChanged | No | filename (basename) |
| WorktreeCreate | Yes (exit 2) | — |
| WorktreeRemove | No | — |
| PreCompact | Yes (exit 2) | trigger: `manual\|auto` |
| PostCompact | No | trigger: `manual\|auto` |
| Elicitation | Yes (exit 2) | mcp_server name |
| ElicitationResult | Yes (exit 2) | mcp_server name |
| SessionEnd | No | reason: `clear\|resume\|logout\|prompt_input_exit\|bypass_permissions_disabled\|other` |

## Common Input Fields (all events)

```json
{
  "session_id": "string",
  "prompt_id": "uuid",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "default|plan|acceptEdits|auto|dontAsk|bypassPermissions",
  "hook_event_name": "string",
  "effort": {
    "level": "low|medium|high|xhigh|max"
  },
  "agent_id": "string (subagent only)",
  "agent_type": "string (subagent/--agent only)"
}
```

## Per-Event Input Fields

### SessionStart

- `source`: `startup|resume|clear|compact|fork`
- `model`: string
- `agent_type`: string (optional)
- `session_title`: string (optional)

### Setup

- `trigger`: `init|maintenance`

### InstructionsLoaded

- `file_path`: string
- `memory_type`: `User|Project|Local|Managed`
- `load_reason`: `session_start|nested_traversal|path_glob_match|include|compact`
- `globs`: string[] (path_glob_match only)
- `trigger_file_path`: string (lazy loads only)
- `parent_file_path`: string (include loads only)

### UserPromptSubmit

- `prompt`: string
- `is_continuation`: boolean (optional; true when continuing an interrupted session)

### UserPromptExpansion

- `expansion_type`: `slash_command|mcp_prompt`
- `command_name`: string
- `command_args`: string
- `command_source`: `plugin|user|custom`
- `prompt`: string (original unexpanded prompt)

### PreToolUse / PermissionRequest / PermissionDenied

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string

### PostToolUse

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string
- `tool_output`: string

### PostToolUseFailure

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string
- `error`: string

### PostToolBatch

- `tool_results`: array of `{ tool_name, tool_use_id, tool_input, tool_output?, error? }`

### Notification

- `message`: string
- `title`: string (optional)
- `notification_type`: `permission_prompt|idle_prompt|auth_success|elicitation_dialog|elicitation_complete|elicitation_response`
- `notification_data`: object (optional)

### SubagentStart / SubagentStop

- `agent_id`: string
- `agent_type`: string
- `task`: string (SubagentStart only)

### TaskCreated

- `task_id`: string
- `task_title`: string (optional)

### TaskCompleted

- `task_id`: string
- `task_title`: string (optional)

### CwdChanged

- `old_cwd`: string
- `new_cwd`: string

### DirectoryAdded

- `directory_path`: string (absolute path of newly added directory)

### FileChanged

- `file_path`: string
- `change_type`: `created|modified|deleted`
- `file_size`: number
- `modification_time`: number (Unix seconds)

### ConfigChange

- `config_source`: `user_settings|project_settings|local_settings|policy_settings|skills`
- `file_path`: string

### WorktreeCreate

- `isolation_type`: `worktree`
- `subagent_id`: string (optional)

### WorktreeRemove

- `worktree_path`: string
- `isolation_type`: `worktree`
- `subagent_id`: string (optional)

### PreCompact / PostCompact

- `compaction_trigger`: `manual|auto`
- `context_used`: number (PreCompact only)
- `context_limit`: number (PreCompact only)

### Elicitation

- `mcp_server_name`: string
- `request_id`: string
- `message`: string
- `form_schema`: object (JSON Schema)

### ElicitationResult

- `mcp_server_name`: string
- `request_id`: string
- `action`: `accept|decline|cancel`
- `content`: object

### StopFailure

- `error_type`: `rate_limit|overloaded|authentication_failed|oauth_org_not_allowed|billing_error|invalid_request|model_not_found|server_error|max_output_tokens|unknown`
- `error_message`: string

### TeammateIdle

- `teammate_id`: string
- `teammate_name`: string

### MessageDisplay

- `text`: string (content being displayed to user)

### Stop

- `last_assistant_message`: string (Claude's full response text; formerly `response`, before that `assistant_message`)

### SessionEnd

- `end_reason`: `clear|resume|logout|prompt_input_exit|bypass_permissions_disabled|other`

## Common Output Fields

```json
{
  "continue": true,
  "stopReason": "string",
  "suppressOutput": false,
  "systemMessage": "string",
  "terminalSequence": "string (OSC/BEL escape sequences only)"
}
```

## Per-Event Output

### SessionStart

- `additionalContext`: string (injected before first prompt)
- `initialUserMessage`: string (optional, overrides initial user message)
- `sessionTitle`: string (optional, sets session title)
- `watchPaths`: string[] (optional, paths to monitor for FileChanged events)
- `reloadSkills`: boolean (optional)

### PreToolUse

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask|defer",
    "permissionDecisionReason": "string",
    "updatedInput": {},
    "additionalContext": "string"
  }
}
```

### UserPromptSubmit / UserPromptExpansion

- `decision`: `"block"` (optional)
- `reason`: string
- `additionalContext`: string (optional)
- `sessionTitle`: string (UserPromptSubmit only, optional)

### PostToolUse

- `decision`: `"block"` (optional)
- `reason`: string
- `hookSpecificOutput.updatedToolOutput`: string (optional, replaces tool output seen by Claude)
- `hookSpecificOutput.additionalContext`: string (optional, appended context for Claude)

### PostToolBatch / TaskCreated / TaskCompleted / PreCompact

- `decision`: `"block"` (optional)
- `reason`: string

### Stop (output)

- `decision`: `"block"` (optional)
- `reason`: string
- `hookSpecificOutput.hookEventName`: `"Stop"`
- `hookSpecificOutput.additionalContext`: string (non-error feedback injected into next turn)

### PermissionRequest

- `hookSpecificOutput.decision.behavior`: `allow|deny`
- `hookSpecificOutput.decision.updatedInput`: object
- `hookSpecificOutput.decision.permissionRules`: array of rule strings

### PermissionDenied

- `hookSpecificOutput.retry`: boolean

### WorktreeCreate

- `hookSpecificOutput.worktreePath`: string (absolute path)

### MessageDisplay

- `hookSpecificOutput.displayContent`: string (modified display text)

### Elicitation / ElicitationResult

- `hookSpecificOutput.action`: `accept|decline|cancel`
- `hookSpecificOutput.content`: object (accept only)

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Block/deny — stderr as rejection reason |
| Other | Non-blocking warning |

## Environment Variables

- `$CLAUDE_PROJECT_DIR` — project root
- `$CLAUDE_PLUGIN_ROOT` — plugin install dir
- `$CLAUDE_PLUGIN_DATA` — plugin data dir
- `$CLAUDE_CODE_REMOTE` — `"true"` in web environments
- `$CLAUDE_EFFORT` — effort level (`low`, `medium`, `high`, `xhigh`, `max`)
- `$CLAUDE_ENV_FILE` — env persist file (SessionStart, Setup, CwdChanged, FileChanged only)
- `$CLAUDE_CODE_BRIDGE_SESSION_ID` — Remote Control session ID (v2.1.199+)

## Constraints

- Hook output capped at 10,000 characters (exceeding saves to file with shortened model preview)
- All matching hooks run in parallel
- Identical handlers deduplicated by command/URL
- JSON-only stdout on exit 0
- `OTEL_*` exporter variables are removed from all subprocess environments
