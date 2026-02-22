from __future__ import annotations

import argparse
import tests._path_setup  # noqa: F401
import unittest
from pathlib import Path
from unittest.mock import patch

from otel_hooks import cli
from otel_hooks.tools import Scope


class _StubTool:
    def __init__(self, *, registered: bool = False, scopes: list[Scope] | None = None) -> None:
        self._registered = registered
        self._scopes = scopes or [Scope.PROJECT]
        self.saved: list[tuple[dict[str, object], Scope]] = []
        self.register_called = 0
        self.unregister_called = 0

    def scopes(self) -> list[Scope]:
        return self._scopes

    def settings_path(self, scope: Scope) -> Path:
        return Path(f"/tmp/{scope.value}/settings.json")

    def load_settings(self, scope: Scope) -> dict[str, object]:
        return {"registered": self._registered}

    def save_settings(self, settings: dict[str, object], scope: Scope) -> None:
        self.saved.append((settings, scope))
        self._registered = bool(settings.get("registered", False))

    def register_hook(self, settings: dict[str, object], command: str | None = None) -> dict[str, object]:
        self.register_called += 1
        out = dict(settings)
        out["registered"] = True
        return out

    def unregister_hook(self, settings: dict[str, object]) -> dict[str, object]:
        self.unregister_called += 1
        out = dict(settings)
        out["registered"] = False
        return out

    def is_hook_registered(self, settings: dict[str, object]) -> bool:
        return bool(settings.get("registered", False))


def _args(
    *,
    tool: str = "claude",
    provider: str = "datadog",
    project: bool = True,
    global_: bool = False,
    local: bool = False,
    yes: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        tool=tool,
        provider=provider,
        project=project,
        global_=global_,
        local=local,
        yes=yes,
    )


class CliBehaviorTest(unittest.TestCase):
    def test_cmd_enable_registers_hook_and_writes_provider_config(self) -> None:
        tool = _StubTool(scopes=[Scope.PROJECT])
        saved_cfg: dict[str, object] = {}

        def _save_config(data: dict[str, object], scope: Scope) -> None:
            saved_cfg["data"] = data
            saved_cfg["scope"] = scope

        with patch("otel_hooks.cli.get_tool", return_value=tool), patch(
            "otel_hooks.cli.cfg.load_raw_config", return_value={}
        ), patch("otel_hooks.cli.cfg.env_keys_for_provider", return_value=[]), patch(
            "otel_hooks.cli.cfg.save_config", side_effect=_save_config
        ):
            rc = cli.cmd_enable(_args())

        self.assertEqual(rc, 0)
        self.assertEqual(tool.register_called, 1)
        self.assertEqual(tool.saved[-1][1], Scope.PROJECT)
        self.assertEqual(saved_cfg["scope"], Scope.PROJECT)
        self.assertNotIn("provider", saved_cfg["data"])
        self.assertNotIn("enabled", saved_cfg["data"])

    def test_cmd_enable_all_writes_provider_config_once(self) -> None:
        claude = _StubTool(scopes=[Scope.PROJECT])
        cursor = _StubTool(scopes=[Scope.PROJECT])
        tools = {"claude": claude, "cursor": cursor}
        save_calls: list[tuple[dict[str, object], Scope]] = []

        with patch("otel_hooks.cli.TOOLS", ["claude", "cursor"]), patch(
            "otel_hooks.cli.get_tool",
            side_effect=lambda name: tools[name],
        ), patch("otel_hooks.cli.cfg.load_raw_config", return_value={}), patch(
            "otel_hooks.cli.cfg.env_keys_for_provider", return_value=[]
        ), patch(
            "otel_hooks.cli.cfg.save_config",
            side_effect=lambda data, scope: save_calls.append((data, scope)),
        ):
            rc = cli.cmd_enable(_args(tool="all", provider="datadog"))

        self.assertEqual(rc, 0)
        self.assertEqual(claude.register_called, 1)
        self.assertEqual(cursor.register_called, 1)
        self.assertEqual(len(save_calls), 1)
        self.assertEqual(save_calls[0][1], Scope.PROJECT)
        self.assertNotIn("provider", save_calls[0][0])

    def test_cmd_disable_unregisters_hook_without_touching_otel_config(self) -> None:
        tool = _StubTool(registered=True, scopes=[Scope.PROJECT])

        with patch("otel_hooks.cli.get_tool", return_value=tool):
            rc = cli.cmd_disable(_args())

        self.assertEqual(rc, 0)
        self.assertEqual(tool.unregister_called, 1)
        self.assertEqual(tool.saved[-1][0]["registered"], False)

    def test_doctor_fixes_missing_hook_and_enables_config_when_yes_flag(self) -> None:
        tool = _StubTool(registered=False, scopes=[Scope.PROJECT])
        saved_cfg: dict[str, object] = {}

        def _save_config(data: dict[str, object], scope: Scope) -> None:
            saved_cfg["data"] = data
            saved_cfg["scope"] = scope

        with patch("otel_hooks.cli.get_tool", return_value=tool), patch(
            "otel_hooks.cli.cfg.load_config", return_value={}
        ), patch("otel_hooks.cli.cfg.load_raw_config", return_value={}), patch(
            "otel_hooks.cli.cfg.env_keys_for_provider", return_value=[]
        ), patch(
            "otel_hooks.cli.cfg.save_config", side_effect=_save_config
        ):
            rc = cli.cmd_doctor(_args(provider="datadog", yes=True))

        self.assertEqual(rc, 0)
        self.assertEqual(tool.register_called, 1)
        self.assertEqual(saved_cfg["scope"], Scope.PROJECT)
        self.assertNotIn("enabled", saved_cfg["data"])
        self.assertNotIn("provider", saved_cfg["data"])

    def test_doctor_all_yes_fixes_provider_once_and_repairs_all_hooks(self) -> None:
        claude = _StubTool(registered=False, scopes=[Scope.PROJECT])
        cursor = _StubTool(registered=False, scopes=[Scope.PROJECT])
        tools = {"claude": claude, "cursor": cursor}
        save_calls: list[tuple[dict[str, object], Scope]] = []

        with patch("otel_hooks.cli.TOOLS", ["claude", "cursor"]), patch(
            "otel_hooks.cli.get_tool",
            side_effect=lambda name: tools[name],
        ), patch("otel_hooks.cli.cfg.load_config", return_value={}), patch(
            "otel_hooks.cli.cfg.load_raw_config", return_value={}
        ), patch("otel_hooks.cli.cfg.env_keys_for_provider", return_value=[]), patch(
            "otel_hooks.cli.cfg.save_config",
            side_effect=lambda data, scope: save_calls.append((data, scope)),
        ):
            rc = cli.cmd_doctor(_args(tool="all", provider="datadog", yes=True))

        self.assertEqual(rc, 0)
        self.assertEqual(claude.register_called, 1)
        self.assertEqual(cursor.register_called, 1)
        self.assertEqual(len(save_calls), 1)
        self.assertEqual(save_calls[0][1], Scope.PROJECT)
        self.assertNotIn("provider", save_calls[0][0])

    def test_doctor_fixes_via_tui_confirm(self) -> None:
        tool = _StubTool(registered=False, scopes=[Scope.PROJECT])
        saved_cfg: dict[str, object] = {}

        def _save_config(data: dict[str, object], scope: Scope) -> None:
            saved_cfg["data"] = data
            saved_cfg["scope"] = scope

        with patch("otel_hooks.cli.get_tool", return_value=tool), patch(
            "otel_hooks.cli.cfg.load_config", return_value={}
        ), patch("otel_hooks.cli.cfg.load_raw_config", return_value={}), patch(
            "otel_hooks.cli.cfg.env_keys_for_provider", return_value=[]
        ), patch(
            "otel_hooks.cli._confirm", return_value=True
        ), patch(
            "otel_hooks.cli.cfg.save_config", side_effect=_save_config
        ):
            rc = cli.cmd_doctor(_args(provider="datadog"))

        self.assertEqual(rc, 0)
        self.assertEqual(tool.register_called, 1)

    def test_doctor_skips_fix_when_user_declines(self) -> None:
        tool = _StubTool(registered=False, scopes=[Scope.PROJECT])

        with patch("otel_hooks.cli.get_tool", return_value=tool), patch(
            "otel_hooks.cli.cfg.load_config", return_value={}
        ), patch(
            "otel_hooks.cli._confirm", return_value=False
        ):
            rc = cli.cmd_doctor(_args(provider="datadog"))

        self.assertEqual(rc, 1)
        self.assertEqual(tool.register_called, 0)

    def test_resolve_tools_notty_without_flag_raises(self) -> None:
        with patch("otel_hooks.cli._is_tty", return_value=False):
            with self.assertRaises(SystemExit):
                cli._resolve_tools(_args(tool=None))

    def test_resolve_provider_notty_without_flag_raises(self) -> None:
        with patch("otel_hooks.cli._is_tty", return_value=False):
            with self.assertRaises(SystemExit):
                cli._resolve_provider(_args(provider=None))


if __name__ == "__main__":
    unittest.main()
