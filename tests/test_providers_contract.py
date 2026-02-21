from __future__ import annotations

import importlib
import tests._path_setup  # noqa: F401
import types
import unittest
from contextlib import contextmanager
from pathlib import Path

from otel_hooks.domain.transcript import Turn


def _sample_turn() -> Turn:
    return Turn(
        user_msg={
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "hello"}],
            },
        },
        assistant_msgs=[
            {
                "type": "assistant",
                "message": {
                    "id": "a1",
                    "role": "assistant",
                    "model": "gpt-5",
                    "content": [
                        {"type": "tool_use", "id": "t1", "name": "read", "input": {"path": "/tmp/a"}},
                        {"type": "text", "text": "done"},
                    ],
                },
            }
        ],
        tool_results_by_id={"t1": {"ok": True}},
    )


@contextmanager
def _patch_modules(modules: dict[str, types.ModuleType]):
    import sys

    backups = {name: sys.modules.get(name) for name in modules}
    try:
        for name, mod in modules.items():
            sys.modules[name] = mod
        yield
    finally:
        for name, old in backups.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def _import_fresh(module_name: str):
    import sys

    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class _ContextRecorder:
    def __init__(self, sink: list["_ContextRecorder"], payload: dict[str, object]) -> None:
        self.payload = payload
        self.updates: list[dict[str, object]] = []
        sink.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, **kwargs: object) -> None:
        self.updates.append(dict(kwargs))


def _build_fake_langfuse_module() -> types.ModuleType:
    mod = types.ModuleType("langfuse")
    mod.instances = []
    mod.propagate_calls = []

    @contextmanager
    def propagate_attributes(**kwargs: object):
        mod.propagate_calls.append(dict(kwargs))
        yield

    class Langfuse:
        def __init__(self, public_key: str, secret_key: str, host: str) -> None:
            self.public_key = public_key
            self.secret_key = secret_key
            self.host = host
            self.spans: list[_ContextRecorder] = []
            self.observations: list[_ContextRecorder] = []
            self.flush_called = False
            self.shutdown_called = False
            mod.instances.append(self)

        def start_as_current_span(self, **kwargs: object):
            return _ContextRecorder(self.spans, dict(kwargs))

        def start_as_current_observation(self, **kwargs: object):
            return _ContextRecorder(self.observations, dict(kwargs))

        def flush(self) -> None:
            self.flush_called = True

        def shutdown(self) -> None:
            self.shutdown_called = True

    mod.Langfuse = Langfuse
    mod.propagate_attributes = propagate_attributes
    return mod


def _build_fake_otlp_modules() -> dict[str, types.ModuleType]:
    opentelemetry_mod = types.ModuleType("opentelemetry")
    exporter_mod = types.ModuleType("opentelemetry.exporter")
    otlp_mod = types.ModuleType("opentelemetry.exporter.otlp")
    proto_mod = types.ModuleType("opentelemetry.exporter.otlp.proto")
    http_mod = types.ModuleType("opentelemetry.exporter.otlp.proto.http")
    trace_exporter_mod = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")

    sdk_mod = types.ModuleType("opentelemetry.sdk")
    resources_mod = types.ModuleType("opentelemetry.sdk.resources")
    trace_mod = types.ModuleType("opentelemetry.sdk.trace")
    trace_export_mod = types.ModuleType("opentelemetry.sdk.trace.export")

    class OTLPSpanExporter:
        def __init__(self, endpoint: str, headers: dict[str, str] | None = None) -> None:
            self.endpoint = endpoint
            self.headers = headers or {}

    class Resource:
        @staticmethod
        def create(attrs: dict[str, str]) -> dict[str, str]:
            return dict(attrs)

    class _FakeTracer:
        def __init__(self) -> None:
            self.spans: list[_ContextRecorder] = []

        def start_as_current_span(self, name: str, attributes: dict[str, object]):
            return _ContextRecorder(self.spans, {"name": name, "attributes": dict(attributes)})

    class TracerProvider:
        def __init__(self, resource: dict[str, str]) -> None:
            self.resource = resource
            self.processors: list[BatchSpanProcessor] = []
            self.tracer = _FakeTracer()
            self.force_flush_called = False
            self.shutdown_called = False

        def add_span_processor(self, processor: "BatchSpanProcessor") -> None:
            self.processors.append(processor)

        def get_tracer(self, _name: str) -> _FakeTracer:
            return self.tracer

        def force_flush(self) -> None:
            self.force_flush_called = True

        def shutdown(self) -> None:
            self.shutdown_called = True

    class BatchSpanProcessor:
        def __init__(self, exporter: OTLPSpanExporter) -> None:
            self.exporter = exporter

    trace_exporter_mod.OTLPSpanExporter = OTLPSpanExporter
    resources_mod.Resource = Resource
    trace_mod.TracerProvider = TracerProvider
    trace_export_mod.BatchSpanProcessor = BatchSpanProcessor

    opentelemetry_mod.exporter = exporter_mod
    exporter_mod.otlp = otlp_mod
    otlp_mod.proto = proto_mod
    proto_mod.http = http_mod
    http_mod.trace_exporter = trace_exporter_mod

    opentelemetry_mod.sdk = sdk_mod
    sdk_mod.resources = resources_mod
    sdk_mod.trace = trace_mod
    trace_mod.export = trace_export_mod

    return {
        "opentelemetry": opentelemetry_mod,
        "opentelemetry.exporter": exporter_mod,
        "opentelemetry.exporter.otlp": otlp_mod,
        "opentelemetry.exporter.otlp.proto": proto_mod,
        "opentelemetry.exporter.otlp.proto.http": http_mod,
        "opentelemetry.exporter.otlp.proto.http.trace_exporter": trace_exporter_mod,
        "opentelemetry.sdk": sdk_mod,
        "opentelemetry.sdk.resources": resources_mod,
        "opentelemetry.sdk.trace": trace_mod,
        "opentelemetry.sdk.trace.export": trace_export_mod,
    }


def _build_fake_ddtrace_module() -> types.ModuleType:
    mod = types.ModuleType("ddtrace")

    class _Span:
        def __init__(self, sink: list["_Span"], meta: dict[str, object]) -> None:
            self.meta = meta
            self.tags: dict[str, str] = {}
            sink.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_tags(self, tags: dict[str, str]) -> None:
            self.tags.update(tags)

    class _Tracer:
        def __init__(self) -> None:
            self.configure_calls: list[dict[str, object]] = []
            self.set_tags_calls: list[dict[str, str]] = []
            self.spans: list[_Span] = []
            self.flush_called = False
            self.shutdown_called = False

        def configure(self, **kwargs: object) -> None:
            self.configure_calls.append(dict(kwargs))

        def set_tags(self, tags: dict[str, str]) -> None:
            self.set_tags_calls.append(dict(tags))

        def trace(self, name: str, resource: str, service: str, span_type: str) -> _Span:
            return _Span(
                self.spans,
                {
                    "name": name,
                    "resource": resource,
                    "service": service,
                    "span_type": span_type,
                },
            )

        def flush(self) -> None:
            self.flush_called = True

        def shutdown(self) -> None:
            self.shutdown_called = True

    mod.tracer = _Tracer()
    return mod


class ProviderContractTest(unittest.TestCase):
    def test_langfuse_provider_emits_expected_span_shape(self) -> None:
        fake_langfuse = _build_fake_langfuse_module()
        with _patch_modules({"langfuse": fake_langfuse}):
            mod = _import_fresh("otel_hooks.providers.langfuse")
            provider = mod.LangfuseProvider("pk", "sk", "https://lf")
            provider.emit_turn("s1", 1, _sample_turn(), Path("/tmp/t.jsonl"), "claude")
            provider.emit_metric("tool_started", 1.0, {"tool_name": "read"}, "claude", "s1")
            provider.flush()
            provider.shutdown()

        client = fake_langfuse.instances[-1]
        self.assertEqual(client.public_key, "pk")
        self.assertEqual(client.secret_key, "sk")
        self.assertEqual(client.host, "https://lf")
        self.assertEqual(len(client.spans), 2)
        self.assertEqual(len(client.observations), 2)
        self.assertEqual(client.spans[0].payload["metadata"]["source_tool"], "claude")
        self.assertEqual(client.spans[0].payload["metadata"]["transcript_path"], "/tmp/t.jsonl")
        self.assertEqual(client.observations[1].updates[0]["output"], '{"ok": true}')
        self.assertTrue(client.flush_called)
        self.assertTrue(client.shutdown_called)
        self.assertEqual(len(fake_langfuse.propagate_calls), 2)

    def test_otlp_provider_emits_expected_span_shape(self) -> None:
        fake_modules = _build_fake_otlp_modules()
        with _patch_modules(fake_modules):
            mod = _import_fresh("otel_hooks.providers.otlp")
            provider = mod.OTLPProvider("http://collector", {"x-auth": "abc"})
            provider.emit_turn("s1", 1, _sample_turn(), Path("/tmp/t.jsonl"), "claude")
            provider.emit_metric("tool_started", 1.0, {"tool_name": "read"}, "claude", "s1")
            provider.flush()
            provider.shutdown()

        fake_provider = provider._provider
        spans = fake_provider.tracer.spans
        self.assertEqual(fake_provider.resource["service.name"], "otel-hooks")
        self.assertEqual(fake_provider.processors[0].exporter.endpoint, "http://collector")
        self.assertEqual(fake_provider.processors[0].exporter.headers, {"x-auth": "abc"})
        self.assertEqual(spans[0].payload["name"], "AI Session - Turn 1")
        self.assertEqual(spans[0].payload["attributes"]["source_tool"], "claude")
        self.assertEqual(spans[2].payload["name"], "Tool: read")
        self.assertEqual(spans[3].payload["name"], "Metric - tool_started")
        self.assertEqual(spans[3].payload["attributes"]["metric.attr.tool_name"], "read")
        self.assertTrue(fake_provider.force_flush_called)
        self.assertTrue(fake_provider.shutdown_called)

    def test_datadog_provider_emits_expected_span_shape(self) -> None:
        fake_ddtrace = _build_fake_ddtrace_module()
        with _patch_modules({"ddtrace": fake_ddtrace}):
            mod = _import_fresh("otel_hooks.providers.datadog")
            provider = mod.DatadogProvider(service="svc", env="prod")
            provider.emit_turn("s1", 1, _sample_turn(), Path("/tmp/t.jsonl"), "claude")
            provider.emit_metric("tool_started", 1.0, {"tool_name": "read"}, "claude", "s1")
            provider.flush()
            provider.shutdown()

        tracer = fake_ddtrace.tracer
        self.assertEqual(tracer.configure_calls, [{"service": "svc"}])
        self.assertEqual(tracer.set_tags_calls, [{"env": "prod"}])
        self.assertEqual(tracer.spans[0].meta["name"], "ai_session.turn")
        self.assertEqual(tracer.spans[0].tags["source_tool"], "claude")
        self.assertEqual(tracer.spans[2].meta["name"], "ai_session.tool")
        self.assertEqual(tracer.spans[3].meta["name"], "ai_session.metric")
        self.assertEqual(tracer.spans[3].tags["metric.attr.tool_name"], "read")
        self.assertTrue(tracer.flush_called)
        self.assertTrue(tracer.shutdown_called)


if __name__ == "__main__":
    unittest.main()
