from __future__ import annotations

import tests._path_setup  # noqa: F401

import unittest

from otel_hooks.tools.copilot import CopilotConfig
from otel_hooks.tools.cursor import CursorConfig
from otel_hooks.tools.kiro import KiroConfig

COPILOT_HOOK_COMMAND = "otel-hooks hook --tool copilot"
CURSOR_HOOK_COMMAND = "otel-hooks hook --tool cursor"
KIRO_HOOK_COMMAND = "otel-hooks hook --tool kiro"


class MetricsHookRegistrationTest(unittest.TestCase):
    def test_copilot_registers_all_metric_events(self) -> None:
        cfg = CopilotConfig()
        settings: dict[str, object] = {"version": 1, "hooks": {}}

        updated = cfg.register_hook(settings)
        hooks = updated["hooks"]

        for event_name in (
            "sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse",
            "sessionEnd", "errorOccurred",
            "agentStop", "notification", "permissionRequest", "postToolUseFailure",
            "preCompact", "subagentStart", "subagentStop",
            "preToolUseFailure",
        ):
            self.assertIn(event_name, hooks)
            self.assertTrue(
                any("otel-hooks hook" in item.get("bash", "") for item in hooks[event_name])
            )

        self.assertTrue(cfg.is_hook_registered(updated))

    def test_copilot_is_not_registered_when_only_session_end_exists(self) -> None:
        cfg = CopilotConfig()
        settings = {
            "version": 1,
            "hooks": {"sessionEnd": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}]},
        }
        self.assertFalse(cfg.is_hook_registered(settings))

    def test_copilot_unregister_removes_registered_command_from_all_events(self) -> None:
        cfg = CopilotConfig()
        settings = {
            "version": 1,
            "hooks": {
                "sessionStart": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "userPromptSubmitted": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "preToolUse": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "postToolUse": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "sessionEnd": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "errorOccurred": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "agentStop": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "notification": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "permissionRequest": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "postToolUseFailure": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "preCompact": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "subagentStart": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "subagentStop": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "preToolUseFailure": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
            },
        }

        updated = cfg.unregister_hook(settings)
        self.assertEqual(updated["hooks"], {})

    def test_cursor_registers_all_events(self) -> None:
        cfg = CursorConfig()
        settings: dict[str, object] = {"version": 1, "hooks": {}}

        updated = cfg.register_hook(settings)
        hooks = updated["hooks"]

        for event_name in ("sessionStart", "preToolUse", "postToolUse", "stop"):
            self.assertIn(event_name, hooks)
            self.assertTrue(
                any("otel-hooks hook" in item.get("command", "") for item in hooks[event_name])
            )

        self.assertTrue(cfg.is_hook_registered(updated))
        self.assertEqual(updated["version"], 1)

    def test_cursor_is_not_registered_when_only_stop_exists(self) -> None:
        cfg = CursorConfig()
        settings = {"version": 1, "hooks": {"stop": [{"command": CURSOR_HOOK_COMMAND}]}}
        self.assertFalse(cfg.is_hook_registered(settings))

    def test_cursor_unregister_removes_registered_command_from_all_events(self) -> None:
        cfg = CursorConfig()
        settings = {
            "version": 1,
            "hooks": {
                "sessionStart": [{"command": CURSOR_HOOK_COMMAND}],
                "preToolUse": [{"command": CURSOR_HOOK_COMMAND}],
                "postToolUse": [{"command": CURSOR_HOOK_COMMAND}],
                "stop": [{"command": CURSOR_HOOK_COMMAND}],
            },
        }

        updated = cfg.unregister_hook(settings)
        self.assertEqual(updated["hooks"], {})

    def test_kiro_registers_all_metric_events(self) -> None:
        cfg = KiroConfig()
        settings: dict[str, object] = {}

        updated = cfg.register_hook(settings)
        self.assertEqual(updated.get("version"), "v1")
        hooks = updated["hooks"]
        self.assertIsInstance(hooks, list)

        registered_triggers = {
            h["trigger"] for h in hooks if "otel-hooks hook" in h.get("action", {}).get("command", "")
        }
        for trigger in (
            "SessionStart", "UserPromptSubmit", "Stop",
            "PreToolUse", "PostToolUse",
            "PreTaskExec", "PostTaskExec",
            "PostFileCreate", "PostFileSave", "PostFileDelete",
        ):
            self.assertIn(trigger, registered_triggers, msg=f"trigger not registered: {trigger}")

        self.assertTrue(cfg.is_hook_registered(updated))

    def test_kiro_is_not_registered_when_only_stop_exists(self) -> None:
        cfg = KiroConfig()
        settings = {
            "version": "v1",
            "hooks": [{"name": "otel-hooks", "trigger": "Stop", "action": {"type": "command", "command": KIRO_HOOK_COMMAND}}],
        }
        self.assertFalse(cfg.is_hook_registered(settings))

    def test_kiro_unregister_removes_registered_command_from_all_events(self) -> None:
        cfg = KiroConfig()
        settings = {
            "version": "v1",
            "hooks": [
                {"name": "otel-hooks", "trigger": t, "action": {"type": "command", "command": KIRO_HOOK_COMMAND}}
                for t in ("SessionStart", "UserPromptSubmit", "Stop", "PreToolUse", "PostToolUse",
                          "PreTaskExec", "PostTaskExec", "PostFileCreate", "PostFileSave", "PostFileDelete")
            ],
        }

        updated = cfg.unregister_hook(settings)
        self.assertEqual(updated["hooks"], [])


if __name__ == "__main__":
    unittest.main()
