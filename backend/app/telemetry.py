"""OpenTelemetry traces and metrics for the Snake Arena backend.

Every span and metric carries three resource attributes identifying
where it came from, read from environment variables:

  - service.name                -- OTEL_SERVICE_NAME (default
                                   "snake-arena-backend")
  - deployment.environment.name -- APP_ENVIRONMENT ("local", "dev",
                                   "prod"; set per deployment -- see
                                   infra/aws/02-app.yaml and
                                   docker-compose.yml)
  - service.version             -- APP_VERSION (the image tag, baked into
                                   the image at build time -- see
                                   Dockerfile and infra/aws/build.sh)

The legacy `deployment.environment` key is set too, alongside the
current `deployment.environment.name` semantic convention, since some
backends (e.g. AWS X-Ray / Application Signals) still read the old one.

Where telemetry goes is controlled by the standard OTel env vars, so
nothing here is tied to one backend:
  - OTEL_EXPORTER_OTLP_ENDPOINT set -> traces and metrics are exported
    over OTLP/HTTP to that collector (on AWS, the ADOT sidecar).
  - OTEL_TRACES_EXPORTER=console / OTEL_METRICS_EXPORTER=console ->
    printed to stdout instead (handy for local debugging).
  - Neither -> created but not exported anywhere.

The game metrics themselves are defined in game_metrics.py.
"""
import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider
from opentelemetry.sdk.metrics.view import ExponentialBucketHistogramAggregation, View
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy.engine import Engine

DEFAULT_SERVICE_NAME = "snake-arena-backend"

# ALB health checks hit this every few seconds; tracing them would bury
# real traffic and cost money to store.
EXCLUDED_URLS = "/api/health"

# Export counts as "change since last export" rather than running totals.
# CloudWatch metrics are per-period values, and the collector's CloudWatch
# exporter discards the first running-total point from every new task.
DELTA_TEMPORALITY = {
    Counter: AggregationTemporality.DELTA,
    Histogram: AggregationTemporality.DELTA,
}


# Exponential histograms carry the value distribution through to
# CloudWatch, which can then compute percentiles (e.g. median score);
# the default explicit-bucket histogram arrives as only min/max/sum/count.
HISTOGRAM_VIEWS = [
    View(instrument_type=Histogram, aggregation=ExponentialBucketHistogramAggregation())
]


def build_resource() -> Resource:
    """The service/environment/version attributes attached to all telemetry."""
    environment = os.environ.get("APP_ENVIRONMENT", "local")
    return Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
            "service.version": os.environ.get("APP_VERSION", "local"),
            "deployment.environment.name": environment,
            "deployment.environment": environment,
        }
    )


# Resource attributes also copied onto every span: AWS X-Ray only makes
# span attributes searchable (as annotations, e.g.
# annotation.deployment_environment_name = "prod"); resource attributes
# arrive as unsearchable metadata.
SPAN_COPIED_RESOURCE_ATTRIBUTES = ("deployment.environment.name", "service.version")


class ResourceAttributesOnSpans(SpanProcessor):
    """Copies SPAN_COPIED_RESOURCE_ATTRIBUTES onto each span as it starts."""

    def on_start(self, span: Span, parent_context=None) -> None:
        for key in SPAN_COPIED_RESOURCE_ATTRIBUTES:
            value = span.resource.attributes.get(key)
            if value is not None:
                span.set_attribute(key, value)


def _exporter_choice(signal: str) -> str:
    """"console", "otlp", or "" (none) for OTEL_<signal>_EXPORTER."""
    choice = os.environ.get(f"OTEL_{signal}_EXPORTER", "").lower()
    if choice == "console":
        return "console"
    otlp_endpoint_set = bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get(f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT")
    )
    if choice in ("", "otlp") and otlp_endpoint_set:
        return "otlp"
    return ""


def _add_span_exporter(provider: TracerProvider) -> None:
    choice = _exporter_choice("TRACES")
    if choice == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif choice == "otlp":
        # Imported lazily so the exporter's protobuf/requests deps load
        # only when actually exporting.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))


def _metric_readers() -> list[MetricReader]:
    choice = _exporter_choice("METRICS")
    if choice == "console":
        exporter = ConsoleMetricExporter(preferred_temporality=DELTA_TEMPORALITY)
    elif choice == "otlp":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        exporter = OTLPMetricExporter(preferred_temporality=DELTA_TEMPORALITY)
    else:
        return []
    # Default interval: every 60s, matching CloudWatch's 1-minute resolution.
    return [PeriodicExportingMetricReader(exporter)]


def setup_telemetry(app: FastAPI, engine: Engine) -> None:
    """Install tracer/meter providers and instrument FastAPI + SQLAlchemy."""
    resource = build_resource()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(ResourceAttributesOnSpans())
    _add_span_exporter(tracer_provider)
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(
        MeterProvider(
            resource=resource, metric_readers=_metric_readers(), views=HISTOGRAM_VIEWS
        )
    )

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=tracer_provider, excluded_urls=EXCLUDED_URLS
    )
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=tracer_provider)
