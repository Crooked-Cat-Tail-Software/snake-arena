"""OpenTelemetry tracing for the Snake Arena backend.

Every span carries three resource attributes identifying where it came
from, read from environment variables:

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

Where spans go is controlled by the standard OTel env vars, so nothing
here is tied to one backend:
  - OTEL_EXPORTER_OTLP_ENDPOINT (or OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    set -> spans are exported over OTLP/HTTP to that collector.
  - OTEL_TRACES_EXPORTER=console -> spans are printed to stdout (handy
    for local debugging).
  - Neither -> spans are created but not exported anywhere.
"""
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy.engine import Engine

DEFAULT_SERVICE_NAME = "snake-arena-backend"

# ALB health checks hit this every few seconds; tracing them would bury
# real traffic and cost money to store.
EXCLUDED_URLS = "/api/health"


def build_resource() -> Resource:
    """The service/environment/version attributes attached to every span."""
    environment = os.environ.get("APP_ENVIRONMENT", "local")
    return Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
            "service.version": os.environ.get("APP_VERSION", "local"),
            "deployment.environment.name": environment,
            "deployment.environment": environment,
        }
    )


def _add_exporter(provider: TracerProvider) -> None:
    exporter_choice = os.environ.get("OTEL_TRACES_EXPORTER", "").lower()
    otlp_endpoint_set = bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )
    if exporter_choice == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif exporter_choice in ("", "otlp") and otlp_endpoint_set:
        # Imported lazily so the exporter's protobuf/requests deps load
        # only when actually exporting.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))


def setup_telemetry(app: FastAPI, engine: Engine) -> TracerProvider:
    """Install the tracer provider and instrument FastAPI + SQLAlchemy."""
    provider = TracerProvider(resource=build_resource())
    _add_exporter(provider)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls=EXCLUDED_URLS
    )
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    return provider
