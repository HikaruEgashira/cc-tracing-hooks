from __future__ import annotations

import tests._path_setup  # noqa: F401
import unittest

from otel_hooks.hook_event import EventType
from otel_hooks.tools import parse_hook_event


class HookPayloadAdapterTest(unittest.TestCase):
    def test_parse_hook_event_for_claude_payload(self) -> None:
        payload = {
            "sessionId": "s1",
            "transcriptPath": "./transcript.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude-code")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "transcript.jsonl")
        self.assertEqual(event.session_id, "s1")

    def test_parse_hook_event_for_cursor_payload(self) -> None:
        payload = {
            "conversation_id": "c1",
            "transcript_path": "./cursor.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "cursor.jsonl")
        self.assertEqual(event.session_id, "c1")

    def test_parse_hook_event_prefers_cursor_when_payload_is_ambiguous(self) -> None:
        payload = {
            "conversation_id": "cursor-1",
            "sessionId": "claude-1",
            "transcriptPath": "./shared.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertEqual(event.session_id, "cursor-1")

    def test_parse_hook_event_cursor_without_transcript(self) -> None:
        event = parse_hook_event({"conversation_id": "c1"})
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "c1")

    def test_parse_hook_event_returns_none_for_unknown_payload(self) -> None:
        event = parse_hook_event({"foo": "bar"})
        self.assertIsNone(event)

    def test_parse_hook_event_for_cline_payload(self) -> None:
        payload = {"taskId": "t1", "clineVersion": "3.36"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "t1")

    def test_parse_hook_event_for_codex_payload(self) -> None:
        payload = {"thread-id": "th1", "type": "agent-turn-complete"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "codex")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "th1")

    def test_parse_hook_event_for_gemini_payload(self) -> None:
        payload = {"session_id": "g1", "timestamp": "2025-01-01T00:00:00Z", "transcript_path": ""}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "gemini")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "g1")

    def test_parse_hook_event_for_copilot_metrics_payload(self) -> None:
        payload = {"hook_event_name": "PreToolUse", "tool_name": "bash", "cwd": "/tmp"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_START)
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.data.get("tool_name"), "bash")

    def test_parse_hook_event_for_copilot_metrics_payload_lower_camel(self) -> None:
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "preToolUse",
            "tool_name": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_START)
        self.assertEqual(event.data.get("tool_name"), "bash")

    def test_parse_hook_event_uses_source_tool_hint_for_ambiguous_payload(self) -> None:
        payload = {
            "source_tool": "kiro",
            "hook_event_name": "preToolUse",
            "tool_name": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")

    def test_parse_hook_event_for_kiro_metrics_payload(self) -> None:
        payload = {"hook_event_name": "userPromptSubmit", "prompt": "hello", "cwd": "/tmp"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)
        self.assertIsNone(event.transcript_path)

    def test_parse_hook_event_for_opencode_plugin_trace_payload(self) -> None:
        payload = {
            "source_tool": "opencode",
            "opencode_event_type": "message.part.updated",
            "session_id": "o1",
            "transcript_path": "./opencode.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "opencode")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "opencode.jsonl")
        self.assertEqual(event.session_id, "o1")

    def test_parse_hook_event_for_opencode_plugin_metric_payload(self) -> None:
        payload = {
            "source_tool": "opencode",
            "kind": "metric",
            "session_id": "o1",
            "metric_name": "tool_completed",
            "metric_value": 1,
            "metric_attributes": {"tool_name": "read"},
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "opencode")
        self.assertIsNone(event.transcript_path)
        # Legacy payload preserved in extensions
        legacy = event.extensions.get("legacy_payload", {})
        self.assertEqual(legacy.get("metric_name"), "tool_completed")
        self.assertEqual(legacy.get("metric_attributes", {}).get("tool_name"), "read")

    def test_parse_hook_event_prefers_gemini_over_claude_when_session_id_and_timestamp_exist(self) -> None:
        payload = {
            "session_id": "g2",
            "timestamp": "2025-01-01T00:00:00Z",
            "transcript_path": "./gemini.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "gemini")
        self.assertEqual(event.session_id, "g2")
        self.assertEqual(event.transcript_path.name, "gemini.jsonl")

    def test_parse_hook_event_for_claude_user_prompt_expansion(self) -> None:
        """UserPromptExpansion maps to PROMPT_SUBMIT (new Claude Code event)."""
        payload = {
            "source_tool": "claude",
            "hook_event_name": "UserPromptExpansion",
            "session_id": "s1",
            "expansion_type": "slash_command",
            "command_name": "review",
            "command_args": "",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)

    def test_parse_hook_event_for_copilot_agent_stop(self) -> None:
        """agentStop maps to SESSION_END (new Copilot event, 2026-05-18 spec)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "agentStop",
            "sessionId": "cp-1",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.SESSION_END)
        self.assertEqual(event.session_id, "cp-1")

    def test_parse_hook_event_for_copilot_subagent_start(self) -> None:
        """subagentStart maps to SESSION_START (new Copilot event, 2026-05-18 spec)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "subagentStart",
            "sessionId": "cp-2",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.SESSION_START)

    def test_parse_hook_event_for_copilot_post_tool_use_failure(self) -> None:
        """postToolUseFailure maps to TOOL_END (new Copilot event, 2026-05-18 spec)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "postToolUseFailure",
            "sessionId": "cp-3",
            "toolName": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_END)

    def test_parse_hook_event_for_copilot_permission_request(self) -> None:
        """permissionRequest maps to TOOL_START (new Copilot event, 2026-05-18 spec)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "permissionRequest",
            "sessionId": "cp-4",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_START)

    def test_parse_hook_event_for_claude_post_tool_batch(self) -> None:
        """PostToolBatch maps to TOOL_END; tool_results field (2026-05-26 spec)."""
        payload = {
            "source_tool": "claude",
            "hook_event_name": "PostToolBatch",
            "session_id": "s1",
            "tool_results": [{"tool_name": "Read", "tool_use_id": "tu1", "tool_input": {}, "tool_output": "ok"}],
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude")
        self.assertEqual(event.type, EventType.TOOL_END)

    def test_parse_hook_event_for_claude_setup_event(self) -> None:
        """Setup maps to SESSION_START (added in 2026-05-04 spec update)."""
        payload = {
            "source_tool": "claude",
            "hook_event_name": "Setup",
            "session_id": "s1",
            "trigger": "init",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude")
        self.assertEqual(event.type, EventType.SESSION_START)

    def test_parse_hook_event_for_claude_message_display(self) -> None:
        """MessageDisplay maps to SESSION_END (new Claude Code event, 2026-06-09 spec)."""
        payload = {
            "source_tool": "claude",
            "hook_event_name": "MessageDisplay",
            "session_id": "s1",
            "text": "Hello from Claude",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude")
        self.assertEqual(event.type, EventType.SESSION_END)

    def test_parse_hook_event_for_copilot_pre_tool_use_failure(self) -> None:
        """preToolUseFailure removed from Copilot spec (2026-07-14); backward-compat mapping retained."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "preToolUseFailure",
            "sessionId": "cp-5",
            "toolName": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_END)

    def test_parse_hook_event_for_copilot_pre_tool_use_failure_pascal_case(self) -> None:
        """PreToolUseFailure (PascalCase alias) also maps to TOOL_END (backward compat)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "PreToolUseFailure",
            "sessionId": "cp-5b",
            "toolName": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_END)

    def test_parse_hook_event_for_kiro_with_session_id(self) -> None:
        """Kiro payloads now include session_id in common fields (2026-05-04 spec update)."""
        payload = {
            "hook_event_name": "userPromptSubmit",
            "cwd": "/tmp",
            "session_id": "kiro-sess-1",
            "prompt": "hello",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)
        self.assertEqual(event.session_id, "kiro-sess-1")

    def test_parse_hook_event_for_cline_sdk_tool_call_before(self) -> None:
        """Cline SDK tool_call_before maps to TOOL_START (2026-06-30 SDK hooks spec)."""
        payload = {
            "source_tool": "cline",
            "hook_event_name": "tool_call_before",
            "session_id": "cline-sdk-1",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertEqual(event.type, EventType.TOOL_START)
        self.assertEqual(event.session_id, "cline-sdk-1")

    def test_parse_hook_event_for_cline_sdk_tool_call_after(self) -> None:
        """Cline SDK tool_call_after maps to TOOL_END (2026-06-30 SDK hooks spec)."""
        payload = {
            "source_tool": "cline",
            "hook_event_name": "tool_call_after",
            "session_id": "cline-sdk-2",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertEqual(event.type, EventType.TOOL_END)

    def test_parse_hook_event_for_cline_sdk_session_start(self) -> None:
        """Cline SDK session_start maps to SESSION_START (2026-06-30 SDK hooks spec)."""
        payload = {
            "source_tool": "cline",
            "hook_event_name": "session_start",
            "session_id": "cline-sdk-3",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertEqual(event.type, EventType.SESSION_START)

    def test_parse_hook_event_for_cline_sdk_run_end(self) -> None:
        """Cline SDK run_end maps to SESSION_END (2026-06-30 SDK hooks spec)."""
        payload = {
            "source_tool": "cline",
            "hook_event_name": "run_end",
            "session_id": "cline-sdk-4",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertEqual(event.type, EventType.SESSION_END)

    def test_parse_hook_event_for_cline_legacy_task_id_still_works(self) -> None:
        """Legacy Cline extension format (taskId) continues to work after SDK migration."""
        payload = {"taskId": "t99", "clineVersion": "3.36"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertEqual(event.session_id, "t99")

    def test_parse_hook_event_for_kiro_pre_task_exec(self) -> None:
        """PreTaskExec is Kiro-specific and maps to SESSION_START (2026-07-07 spec sync)."""
        payload = {
            "hook_event_name": "PreTaskExec",
            "session_id": "kiro-1",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.SESSION_START)
        self.assertEqual(event.session_id, "kiro-1")

    def test_parse_hook_event_for_kiro_post_task_exec(self) -> None:
        """PostTaskExec is Kiro-specific and maps to SESSION_END (2026-07-07 spec sync)."""
        payload = {
            "hook_event_name": "PostTaskExec",
            "session_id": "kiro-2",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.SESSION_END)

    def test_parse_hook_event_for_kiro_post_file_create(self) -> None:
        """PostFileCreate is Kiro-specific and maps to FILE_WRITE (2026-07-07 spec sync)."""
        payload = {
            "hook_event_name": "PostFileCreate",
            "session_id": "kiro-3",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.FILE_WRITE)

    def test_parse_hook_event_for_kiro_post_file_save(self) -> None:
        """PostFileSave is Kiro-specific and maps to FILE_WRITE (2026-07-07 spec sync)."""
        payload = {
            "hook_event_name": "PostFileSave",
            "session_id": "kiro-4",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.FILE_WRITE)

    def test_parse_hook_event_for_kiro_post_file_delete(self) -> None:
        """PostFileDelete is Kiro-specific and maps to FILE_WRITE (2026-07-07 spec sync)."""
        payload = {
            "hook_event_name": "PostFileDelete",
            "session_id": "kiro-5",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.FILE_WRITE)

    def test_parse_hook_event_for_copilot_user_prompt_transformed(self) -> None:
        """userPromptTransformed maps to PROMPT_SUBMIT (new Copilot event, 2026-07-21 spec sync)."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "userPromptTransformed",
            "sessionId": "cp-6",
            "cwd": "/tmp",
            "prompt": "original user prompt",
            "transformedPrompt": "system-transformed prompt sent to model",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)
        self.assertEqual(event.session_id, "cp-6")

    def test_parse_hook_event_for_copilot_user_prompt_transformed_pascal_case(self) -> None:
        """UserPromptTransformed (PascalCase alias) also maps to PROMPT_SUBMIT."""
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "UserPromptTransformed",
            "sessionId": "cp-7",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)


if __name__ == "__main__":
    unittest.main()
