from __future__ import annotations

from copy import deepcopy

import tests._path_setup  # noqa: F401
import unittest

from otel_hooks.tools import get_tool

HOOK_COMMAND = "otel-hooks hook"


class ToolHookIdempotencyTest(unittest.TestCase):
    def _assert_idempotent(self, cfg, hook_command: str) -> None:
        once = cfg.register_hook({})
        twice = cfg.register_hook(deepcopy(once))

        self.assertEqual(once, twice)
        self.assertTrue(cfg.is_hook_registered(twice))
        self.assertEqual(repr(twice).count(hook_command), 1)

        unregistered_once = cfg.unregister_hook(deepcopy(twice))
        unregistered_twice = cfg.unregister_hook(deepcopy(unregistered_once))

        self.assertEqual(unregistered_once, unregistered_twice)
        self.assertFalse(cfg.is_hook_registered(unregistered_twice))

    def test_claude_register_unregister_is_idempotent(self) -> None:
        self._assert_idempotent(get_tool("claude"), HOOK_COMMAND)

    def test_cursor_register_unregister_is_idempotent(self) -> None:
        self._assert_idempotent(get_tool("cursor"), HOOK_COMMAND)

    def test_gemini_register_unregister_is_idempotent(self) -> None:
        self._assert_idempotent(get_tool("gemini"), HOOK_COMMAND)

    def test_cline_register_unregister_is_idempotent(self) -> None:
        self._assert_idempotent(get_tool("cline"), HOOK_COMMAND)


if __name__ == "__main__":
    unittest.main()
