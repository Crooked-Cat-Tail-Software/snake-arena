"""OpenTelemetry instrumentation: every span carries service name,
environment, and deployed version (see backend/app/telemetry.py)."""
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.telemetry import build_resource


@pytest.fixture()
def spans(client):
    """Captures spans the real app emits during a test."""
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    trace.get_tracer_provider().add_span_processor(processor)
    yield exporter
    exporter.clear()


def test_resource_reads_env(monkeypatch):
    monkeypatch.setenv("OTEL_SERVICE_NAME", "snake-test")
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("APP_VERSION", "20261008-120000-abc1234")

    attrs = build_resource().attributes

    assert attrs["service.name"] == "snake-test"
    assert attrs["deployment.environment.name"] == "prod"
    assert attrs["deployment.environment"] == "prod"
    assert attrs["service.version"] == "20261008-120000-abc1234"


def test_resource_defaults(monkeypatch):
    for var in ("OTEL_SERVICE_NAME", "APP_ENVIRONMENT", "APP_VERSION"):
        monkeypatch.delenv(var, raising=False)

    attrs = build_resource().attributes

    assert attrs["service.name"] == "snake-arena-backend"
    assert attrs["deployment.environment.name"] == "local"
    assert attrs["service.version"] == "local"


def test_requests_produce_spans_with_resource(client, spans):
    response = client.post("/api/scores", json={"player_name": "otel", "score": 7})
    assert response.status_code == 201

    finished = spans.get_finished_spans()
    server_spans = [s for s in finished if s.kind == trace.SpanKind.SERVER]
    assert [s.name for s in server_spans] == ["POST /api/scores"]
    for attr in ("service.name", "deployment.environment.name", "service.version"):
        assert attr in server_spans[0].resource.attributes
    # Copied onto every span too, so X-Ray can index them as annotations.
    for span in finished:
        for attr in ("deployment.environment.name", "service.version"):
            assert span.attributes[attr] == span.resource.attributes[attr]


def test_health_check_not_traced(client, spans):
    assert client.get("/api/health").status_code == 200
    # No request span. (A SQLAlchemy "connect" span can still appear when
    # the pool opens a fresh connection -- that's not per-health-check.)
    server_spans = [
        s for s in spans.get_finished_spans() if s.kind == trace.SpanKind.SERVER
    ]
    assert server_spans == []
