from __future__ import annotations

import base64
import tests._path_setup  # noqa: F401
import unittest

from otel_hooks.tools import get_tool


class CodexConfigGenerationTest(unittest.TestCase):
    def test_enable_otlp_builds_exporter_and_parses_headers(self) -> None:
        cfg = get_tool("codex")
        updated = cfg.enable_otlp({}, endpoint="http://collector", headers="a=1, b=2, invalid")

        exporter = updated["otel"]["exporter"]["otlp-http"]
        self.assertEqual(exporter["endpoint"], "http://collector")
        self.assertEqual(exporter["protocol"], "json")
        self.assertEqual(exporter["headers"], {"a": "1", "b": "2"})

    def test_enable_langfuse_builds_otlp_endpoint_and_auth_header(self) -> None:
        cfg = get_tool("codex")
        updated = cfg.enable_langfuse(
            {},
            public_key="pk",
            secret_key="sk",
            base_url="https://langfuse.example.com/",
        )

        exporter = updated["otel"]["exporter"]["otlp-http"]
        expected_auth = "Basic " + base64.b64encode(b"pk:sk").decode()

        self.assertEqual(
            exporter["endpoint"],
            "https://langfuse.example.com/api/public/otel/v1/traces",
        )
        self.assertEqual(exporter["protocol"], "json")
        self.assertEqual(exporter["headers"]["Authorization"], expected_auth)


if __name__ == "__main__":
    unittest.main()
