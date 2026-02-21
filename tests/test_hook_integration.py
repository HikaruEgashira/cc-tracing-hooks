from __future__ import annotations

import json
import tempfile
import tests._path_setup  # noqa: F401
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from otel_hooks import hook


class _StubProvider:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, int]] = []
        self.metrics: list[tuple[str, float, str]] = []
        self.flush_called = False
        self.shutdown_called = False

    def emit_turn(self, session_id: str, turn_num: int, turn, transcript_path: Path | None, source_tool: str = "") -> None:
        self.emitted.append((session_id, turn_num))

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        self.metrics.append((metric_name, metric_value, source_tool))

    def flush(self) -> None:
        self.flush_called = True

    def shutdown(self) -> None:
        self.shutdown_called = True


class _FailingProvider(_StubProvider):
    def __init__(self) -> None:
        super().__init__()
        self.emit_attempts = 0

    def emit_turn(self, session_id: str, turn_num: int, turn, transcript_path: Path | None, source_tool: str = "") -> None:
        self.emit_attempts += 1
        raise RuntimeError("emit failed")


class _MetricFailingProvider(_StubProvider):
    def __init__(self) -> None:
        super().__init__()
        self.metric_attempts = 0

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        self.metric_attempts += 1
        raise RuntimeError("emit metric failed")


class HookIntegrationTest(unittest.TestCase):
    def test_run_hook_emits_once_and_skips_already_processed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "a1",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }

            provider1 = _StubProvider()
            provider2 = _StubProvider()
            providers = [provider1, provider2]

            def provider_factory(_name: str, _cfg: dict[str, object]):
                return providers.pop(0)

            rc1 = hook.run_hook(payload, config, provider_factory=provider_factory)

            self.assertEqual(rc1, 0)
            self.assertEqual(provider1.emitted, [("s-1", 1)])
            self.assertTrue(provider1.flush_called)
            self.assertTrue(provider1.shutdown_called)

            # 同一 payload を再実行しても state により再送しない
            rc2 = hook.run_hook(payload, config, provider_factory=provider_factory)

            self.assertEqual(rc2, 0)
            self.assertEqual(provider2.emitted, [])
            self.assertFalse(provider2.flush_called)
            self.assertTrue(provider2.shutdown_called)

            state_file = root / "state" / "otel_hook_state.json"
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(len(state), 1)
            saved = next(iter(state.values()))
            self.assertEqual(saved["turn_count"], 1)

    def test_run_hook_emits_metrics_for_metrics_only_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {"hook_event_name": "PreToolUse", "tool_name": "bash", "cwd": str(root)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }

            provider = _StubProvider()
            rc = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: provider)

            self.assertEqual(rc, 0)
            self.assertEqual(provider.emitted, [])
            self.assertEqual(provider.metrics, [("tool_started", 1.0, "copilot")])
            self.assertTrue(provider.flush_called)
            self.assertTrue(provider.shutdown_called)

    def test_run_hook_returns_zero_when_provider_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text("", encoding="utf-8")
            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }

            rc = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: None)

            self.assertEqual(rc, 0)

    def test_run_hook_flushes_and_shuts_down_when_metric_emit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {"hook_event_name": "PreToolUse", "tool_name": "bash", "cwd": str(root)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }

            provider = _MetricFailingProvider()
            rc = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: provider)

            self.assertEqual(rc, 0)
            self.assertEqual(provider.metric_attempts, 1)
            self.assertTrue(provider.flush_called)
            self.assertTrue(provider.shutdown_called)

    def test_run_hook_does_not_advance_turn_count_when_emit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "a1",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }

            provider = _FailingProvider()
            rc = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: provider)

            self.assertEqual(rc, 0)
            self.assertTrue(provider.shutdown_called)

            state_file = root / "state" / "otel_hook_state.json"
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text(encoding="utf-8"))
            saved = next(iter(state.values()))
            # 送信失敗時は再送可能性のため turn_count を進めない
            self.assertEqual(saved["turn_count"], 0)
            self.assertEqual(saved["offset"], 0)
            self.assertEqual(saved["buffer"], "")

    def test_run_hook_retries_same_turn_when_emit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "a1",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}
            config = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state"),
            }
            provider = _FailingProvider()

            rc1 = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: provider)
            rc2 = hook.run_hook(payload, config, provider_factory=lambda _name, _cfg: provider)

            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 0)
            self.assertEqual(provider.emit_attempts, 2)

    def test_run_hook_parallel_calls_do_not_cross_state_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            transcript_a = root / "a.jsonl"
            transcript_a.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello-a"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "aa",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world-a"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            transcript_b = root / "b.jsonl"
            transcript_b.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello-b"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "bb",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world-b"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload_a = {"sessionId": "s-a", "transcriptPath": str(transcript_a)}
            payload_b = {"sessionId": "s-b", "transcriptPath": str(transcript_b)}
            config_a = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state-a"),
            }
            config_b = {
                "provider": "langfuse",
                "debug": False,
                "state_dir": str(root / "state-b"),
            }

            provider_a = _StubProvider()
            provider_b = _StubProvider()

            def provider_factory(_name: str, cfg: dict[str, object]):
                return provider_a if cfg["state_dir"] == str(root / "state-a") else provider_b

            with ThreadPoolExecutor(max_workers=2) as ex:
                fut_a = ex.submit(hook.run_hook, payload_a, config_a, provider_factory=provider_factory)
                fut_b = ex.submit(hook.run_hook, payload_b, config_b, provider_factory=provider_factory)
                rc_a = fut_a.result(timeout=5)
                rc_b = fut_b.result(timeout=5)

            self.assertEqual(rc_a, 0)
            self.assertEqual(rc_b, 0)
            self.assertEqual(provider_a.emitted, [("s-a", 1)])
            self.assertEqual(provider_b.emitted, [("s-b", 1)])
            self.assertTrue((root / "state-a" / "otel_hook_state.json").exists())
            self.assertTrue((root / "state-b" / "otel_hook_state.json").exists())


if __name__ == "__main__":
    unittest.main()
