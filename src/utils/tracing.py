"""
OpenTelemetry Tracing Configuration for Jaeger.

This module provides distributed tracing using OpenTelemetry with Jaeger as the backend.
Jaeger 2.0 natively supports OTLP protocol, so we use the OTLP exporter.

Environment Variables:
    TRACING_ENABLED: Enable/disable tracing entirely (default: false)
    JAEGER_ENDPOINT: Jaeger OTLP endpoint (default: http://localhost:4317)
    OTEL_SERVICE_NAME: Service name for traces (default: vriddhi-matching-engine)
    OTEL_SERVICE_VERSION: Service version (default: 2.0.0)

Usage:
    from src.utils.tracing import init_tracing, get_tracer

    # In main.py startup
    init_tracing(app)

    # To create custom spans (works even when tracing is disabled - returns no-op)
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("key", "value")
        # ... your code
"""

import os
from typing import Optional
from contextlib import contextmanager

# Configuration from environment variables
TRACING_ENABLED = os.getenv("TRACING_ENABLED", "false").lower() == "true"
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
OTLP_HEADERS = os.getenv("OTLP_HEADERS", "")  # Format: "key1=value1,key2=value2"
SERVICE_NAME_VALUE = os.getenv("OTEL_SERVICE_NAME", "vriddhi-matching-engine")
SERVICE_VERSION_VALUE = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")

# Legacy support
JAEGER_ENDPOINT = os.getenv("JAEGER_ENDPOINT", "")
if JAEGER_ENDPOINT and not os.getenv("OTLP_ENDPOINT"):
    OTLP_ENDPOINT = JAEGER_ENDPOINT

# Global state
_tracer_provider = None
_tracing_initialized = False
_opentelemetry_available = False

# Try to import OpenTelemetry (optional dependency)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.trace import Status, StatusCode
    _opentelemetry_available = True
except ImportError:
    _opentelemetry_available = False


class NoOpSpan:
    """No-operation span for when tracing is disabled."""
    def set_attribute(self, key, value):
        pass

    def record_exception(self, exception):
        pass

    def set_status(self, status):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class NoOpTracer:
    """No-operation tracer for when tracing is disabled."""
    @contextmanager
    def start_as_current_span(self, name, **kwargs):
        yield NoOpSpan()


_noop_tracer = NoOpTracer()


def init_tracing(app=None):
    """
    Initialize OpenTelemetry tracing with Jaeger exporter.

    Gracefully handles cases where:
    - TRACING_ENABLED=false (tracing disabled)
    - OpenTelemetry packages not installed
    - Jaeger not running/unreachable

    Args:
        app: FastAPI application instance (optional, for auto-instrumentation)
    """
    global _tracer_provider, _tracing_initialized

    # Check if tracing is enabled
    if not TRACING_ENABLED:
        print("[Tracing] Disabled (TRACING_ENABLED=false)")
        return

    # Check if OpenTelemetry is available
    if not _opentelemetry_available:
        print("[Tracing] OpenTelemetry packages not installed. Run: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")
        print("[Tracing] Continuing without tracing...")
        return

    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: SERVICE_NAME_VALUE,
        SERVICE_VERSION: SERVICE_VERSION_VALUE,
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)

    # Configure OTLP exporter (supports Jaeger, Grafana Cloud, etc.)
    try:
        # Parse headers if provided (for Grafana Cloud authentication)
        headers = None
        if OTLP_HEADERS:
            headers = {}
            for header in OTLP_HEADERS.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers[key.strip()] = value.strip()

        # Determine if we need secure connection (HTTPS)
        is_secure = OTLP_ENDPOINT.startswith("https://")

        # Create exporter with appropriate settings
        if is_secure:
            # Grafana Cloud or other HTTPS endpoints
            otlp_exporter = OTLPSpanExporter(
                endpoint=OTLP_ENDPOINT,
                headers=headers,
                insecure=False
            )
        else:
            # Local Jaeger (HTTP)
            otlp_exporter = OTLPSpanExporter(
                endpoint=OTLP_ENDPOINT,
                headers=headers,
                insecure=True
            )

        # Use BatchSpanProcessor for better performance
        span_processor = BatchSpanProcessor(otlp_exporter)
        _tracer_provider.add_span_processor(span_processor)

        # Set the global tracer provider
        trace.set_tracer_provider(_tracer_provider)
        _tracing_initialized = True

        print(f"[Tracing] Enabled - OTLP endpoint: {OTLP_ENDPOINT}")
        print(f"[Tracing] Service: {SERVICE_NAME_VALUE} v{SERVICE_VERSION_VALUE}")

    except Exception as e:
        print(f"[Tracing] Warning: Could not configure Jaeger exporter: {e}")
        print("[Tracing] Continuing without distributed tracing...")
        return

    # Auto-instrument FastAPI
    if app:
        try:
            FastAPIInstrumentor.instrument_app(app)
            print("[Tracing] FastAPI auto-instrumentation enabled")
        except Exception as e:
            print(f"[Tracing] FastAPI instrumentation failed: {e}")

    # Auto-instrument requests library (for external HTTP calls)
    try:
        RequestsInstrumentor().instrument()
        print("[Tracing] Requests library auto-instrumentation enabled")
    except Exception as e:
        print(f"[Tracing] Requests instrumentation failed: {e}")

    # Auto-instrument logging (adds trace context to logs)
    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
        print("[Tracing] Logging auto-instrumentation enabled")
    except Exception as e:
        print(f"[Tracing] Logging instrumentation failed: {e}")


def shutdown_tracing():
    """Shutdown tracing and flush pending spans."""
    global _tracer_provider
    if _tracer_provider and _tracing_initialized:
        try:
            _tracer_provider.shutdown()
            print("[Tracing] Shutdown complete")
        except Exception as e:
            print(f"[Tracing] Shutdown error: {e}")
    else:
        print("[Tracing] Nothing to shutdown (tracing was not initialized)")


def get_tracer(name: str = __name__):
    """
    Get a tracer for creating custom spans.

    Returns a no-op tracer if tracing is disabled, so your code works
    regardless of whether tracing is enabled.

    Args:
        name: Name for the tracer (typically __name__)

    Returns:
        OpenTelemetry Tracer or NoOpTracer

    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my-operation") as span:
            span.set_attribute("user_id", user_id)
            # ... your code (works even if tracing disabled)
    """
    if _tracing_initialized and _opentelemetry_available:
        return trace.get_tracer(name)
    return _noop_tracer


def add_span_attributes(span, **attributes):
    """
    Helper to add multiple attributes to a span.

    Works with both real spans and NoOpSpan.

    Args:
        span: Current span
        **attributes: Key-value pairs to add
    """
    for key, value in attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, str(value) if not isinstance(value, (int, float, bool)) else value)
            except Exception:
                pass  # Ignore errors for no-op spans


def record_exception(span, exception: Exception, status_message: str = None):
    """
    Record an exception in the current span.

    Works with both real spans and NoOpSpan.

    Args:
        span: Current span
        exception: The exception to record
        status_message: Optional custom status message
    """
    try:
        span.record_exception(exception)
        if _opentelemetry_available:
            span.set_status(Status(StatusCode.ERROR, status_message or str(exception)))
    except Exception:
        pass  # Ignore errors for no-op spans


def traced(span_name: str = None):
    """
    Decorator to automatically trace a function.

    Works even when tracing is disabled (becomes a no-op).

    Args:
        span_name: Custom span name (defaults to function name)

    Usage:
        @traced("custom-operation-name")
        def my_function():
            pass
    """
    import functools
    import asyncio

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            name = span_name or func.__name__

            with tracer.start_as_current_span(name) as span:
                add_span_attributes(span,
                    **{"function.name": func.__name__, "function.module": func.__module__}
                )
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    record_exception(span, e)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            name = span_name or func.__name__

            with tracer.start_as_current_span(name) as span:
                add_span_attributes(span,
                    **{"function.name": func.__name__, "function.module": func.__module__}
                )
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    record_exception(span, e)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


def is_tracing_enabled() -> bool:
    """Check if tracing is currently enabled and initialized."""
    return _tracing_initialized and _opentelemetry_available
