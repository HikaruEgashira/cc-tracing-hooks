"""GitHub Copilot tool configuration (.github/hooks/otel-hooks.json).

Works with both GitHub Copilot CLI and VS Code Copilot agent.

Reference:
  - https://docs.github.com/en/copilot/reference/hooks-configuration
"""

from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool
from .json_io import load_json, save_json

HOOKS_FILE = "otel-hooks.json"
_HOOK_EVENTS = (
    "sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse",
    "sessionEnd", "errorOccurred",
    # Added in 2026-05-18 spec sync
    "agentStop", "notification", "permissionRequest", "postToolUseFailure",
    "preCompact", "subagentStart", "subagentStop",
)
_EVENT_ALIASES = {
    "sessionStart": "session_start",
    "SessionStart": "session_start",
    "userPromptSubmitted": "user_prompt_submitted",
    "UserPromptSubmitted": "user_prompt_submitted",
    "UserPromptSubmit": "user_prompt_submitted",
    "preToolUse": "pre_tool_use",
    "PreToolUse": "pre_tool_use",
    "postToolUse": "post_tool_use",
    "PostToolUse": "post_tool_use",
    "sessionEnd": "session_end",
    "SessionEnd": "session_end",
    "errorOccurred": "error_occurred",
    "ErrorOccurred": "error_occurred",
    "agentStop": "agent_stop",
    "AgentStop": "agent_stop",
    "notification": "notification",
    "Notification": "notification",
    "permissionRequest": "permission_request",
    "PermissionRequest": "permission_request",
    "postToolUseFailure": "post_tool_use_failure",
    "PostToolUseFailure": "post_tool_use_failure",
    "preCompact": "pre_compact",
    "PreCompact": "pre_compact",
    "subagentStart": "subagent_start",
    "SubagentStart": "subagent_start",
    "subagentStop": "subagent_stop",
    "SubagentStop": "subagent_stop",
}



@register_tool
class CopilotConfig:
    @property
    def name(self) -> str:
        return "copilot"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".copilot" / "hooks" / HOOKS_FILE
        return Path.cwd() / ".github" / "hooks" / HOOKS_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope), default={"version": 1, "hooks": {}})

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", {})
        return all(
            any("otel-hooks hook" in hook.get("bash", "") for hook in hooks.get(event_name, []))
            for event_name in _HOOK_EVENTS
        )

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        base_cmd = command or "otel-hooks hook"
        cmd = f"{base_cmd} --tool copilot"
        settings.setdefault("version", 1)
        hooks = settings.setdefault("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.setdefault(event_name, [])
            if any("otel-hooks hook" in hook.get("bash", "") for hook in group):
                continue
            group.append(
                {
                    "type": "command",
                    "bash": cmd,
                    "comment": "otel-hooks: emit observability data",
                }
            )
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.get(event_name, [])
            if not group:
                continue
            hooks[event_name] = [
                hook for hook in group if "otel-hooks hook" not in hook.get("bash", "")
            ]
            if not hooks[event_name]:
                del hooks[event_name]
        return settings

