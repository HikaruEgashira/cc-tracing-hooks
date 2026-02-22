from __future__ import annotations

import tests._path_setup  # noqa: F401

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from otel_hooks import config
from otel_hooks.tools import Scope, available_tools, get_tool


class ToolsRegistryAndConfigTest(unittest.TestCase):
    def test_available_tools_contains_supported_tools(self) -> None:
        tools = available_tools()
        self.assertIn("claude", tools)
        self.assertIn("codex", tools)
        self.assertIn("cursor", tools)
        self.assertIn("copilot", tools)
        self.assertIn("kiro", tools)
        self.assertIn("opencode", tools)
        self.assertEqual(tools, sorted(tools))

    def test_get_tool_returns_config_instance(self) -> None:
        claude = get_tool("claude")
        self.assertEqual(claude.name, "claude")
        self.assertIn(Scope.GLOBAL, claude.scopes())

    def test_load_raw_config_reads_single_scope_without_merge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".otel-hooks.json").write_text('{"provider": "otlp"}', encoding="utf-8")
            cfg_dir = root / ".config" / "otel-hooks"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text('{"provider": "langfuse"}', encoding="utf-8")

            with patch("otel_hooks.config.Path.cwd", return_value=root), patch(
                "otel_hooks.config.Path.home", return_value=root
            ):
                project_cfg = config.load_raw_config(Scope.PROJECT)
                global_cfg = config.load_raw_config(Scope.GLOBAL)

            self.assertEqual(project_cfg["provider"], "otlp")
            self.assertEqual(global_cfg["provider"], "langfuse")

    def test_load_config_applies_env_override_last(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".otel-hooks.json").write_text('{"debug": false}', encoding="utf-8")
            cfg_dir = root / ".config" / "otel-hooks"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text('{"debug": false}', encoding="utf-8")

            with patch.dict(os.environ, {"OTEL_HOOKS_DEBUG": "true"}, clear=False), patch(
                "otel_hooks.config.Path.cwd", return_value=root
            ), patch("otel_hooks.config.Path.home", return_value=root):
                merged = config.load_config()

            self.assertEqual(merged["debug"], True)

    def test_load_config_applies_provider_env_for_all_configured_providers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".otel-hooks.json").write_text('{"langfuse": {}, "otlp": {}}', encoding="utf-8")
            cfg_dir = root / ".config" / "otel-hooks"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text("{}", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"LANGFUSE_PUBLIC_KEY": "pk", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
                clear=False,
            ), patch(
                "otel_hooks.config.Path.cwd", return_value=root
            ), patch("otel_hooks.config.Path.home", return_value=root):
                merged = config.load_config()

            self.assertEqual(merged["langfuse"]["public_key"], "pk")
            self.assertEqual(merged["otlp"]["endpoint"], "http://localhost:4318")


if __name__ == "__main__":
    unittest.main()
