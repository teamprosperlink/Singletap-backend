"""
Grafana Cloud Integration for Unified Observability.

Provides all-in-one observability using Grafana Cloud Free Tier:
- Logs -> Grafana Loki (via OTLP or Loki HTTP API)
- Traces -> Grafana Tempo (via OTLP)
- Metrics -> Grafana Mimir (via OTLP) [optional]

Grafana Cloud Free Tier Limits (as of 2026):
- 50 GB Logs
- 50 GB Traces
- 10,000 Metrics series
- 14-day retention

Environment Variables:
    GRAFANA_CLOUD_ENABLED: Enable/disable Grafana Cloud (default: false)
    GRAFANA_CLOUD_ENDPOINT: OTLP gateway URL (e.g., https://otlp-gateway-prod-us-central-0.grafana.net/otlp)
    GRAFANA_CLOUD_INSTANCE_ID: Your Grafana Cloud instance ID
    GRAFANA_CLOUD_API_KEY: Your Grafana Cloud API token (with MetricsPublisher role)
    OTEL_SERVICE_NAME: Service name for telemetry (default: vriddhi-matching-engine)
    OTEL_SERVICE_VERSION: Service version (default: 2.0.0)

Usage:
    from src.utils.grafana import init_grafana_cloud, shutdown_grafana_cloud

    # In main.py startup
    init_grafana_cloud(app)

    # In main.py shutdown
    shutdown_grafana_cloud()
"""

import os
import base64
import logging
import json
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager

# Configuration from environment variables (read first, before setting OTEL env vars)
GRAFANA_CLOUD_ENABLED = os.getenv("GRAFANA_CLOUD_ENABLED", "false").lower() == "true"
GRAFANA_CLOUD_ENDPOINT = os.getenv("GRAFANA_CLOUD_ENDPOINT", "")
GRAFANA_CLOUD_INSTANCE_ID = os.getenv("GRAFANA_CLOUD_INSTANCE_ID", "")
GRAFANA_CLOUD_API_KEY = os.getenv("GRAFANA_CLOUD_API_KEY", "")

# Configure OTEL environment variables BEFORE any OpenTelemetry imports
# This ensures any auto-configured exporters use the correct Grafana Cloud endpoint
os.environ["OTEL_METRICS_EXPORTER"] = "none"  # Disable metrics (we only use traces + Loki logs)
os.environ["OTEL_LOGS_EXPORTER"] = "none"  # We use Loki HTTP API instead

if GRAFANA_CLOUD_ENABLED and GRAFANA_CLOUD_ENDPOINT and GRAFANA_CLOUD_INSTANCE_ID and GRAFANA_CLOUD_API_KEY:
    # Set OTLP endpoint for auto-configured exporters
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = GRAFANA_CLOUD_ENDPOINT
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"{GRAFANA_CLOUD_ENDPOINT}/v1/traces"
    # Set auth header for OTLP exporters (format: key=value,key2=value2)
    auth_credentials = f"{GRAFANA_CLOUD_INSTANCE_ID}:{GRAFANA_CLOUD_API_KEY}"
    auth_b64 = base64.b64encode(auth_credentials.encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_b64}"
GRAFANA_LOKI_ENDPOINT = os.getenv("GRAFANA_LOKI_ENDPOINT", "")  # Optional separate Loki endpoint
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "vriddhi-matching-engine")
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Global state
_grafana_initialized = False
_tracer_provider = None
_log_handler = None
_loki_handler = None

# Check for OpenTelemetry availability
_opentelemetry_available = False
_early_tracer_provider = None  # TracerProvider set up at import time
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME as RESOURCE_SERVICE_NAME, SERVICE_VERSION as RESOURCE_SERVICE_VERSION
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.trace import Status, StatusCode
    _opentelemetry_available = True

except ImportError:
    _opentelemetry_available = False


def _get_auth_header() -> str:
    """
    Generate the Basic auth header for Grafana Cloud.

    Format: Basic base64(instance_id:api_key)
    """
    if not GRAFANA_CLOUD_INSTANCE_ID or not GRAFANA_CLOUD_API_KEY:
        return ""

    credentials = f"{GRAFANA_CLOUD_INSTANCE_ID}:{GRAFANA_CLOUD_API_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


class GrafanaCloudSpanExporter:
    """
    Custom span exporter that sends traces to Grafana Cloud using JSON format.

    The default OTLP protobuf exporter sometimes has issues with Grafana Cloud,
    so this exporter uses the JSON format which works more reliably.

    Implements the SpanExporter interface for use with SimpleSpanProcessor.
    """

    def __init__(self, endpoint: str, auth_header: str):
        self.endpoint = endpoint
        self.auth_header = auth_header
        self._shutdown = False

    def export(self, spans):
        """Export spans to Grafana Cloud. Returns SpanExportResult."""
        from opentelemetry.sdk.trace.export import SpanExportResult
        import sys

        print(f"[Grafana] export() called with {len(spans) if spans else 0} spans", file=sys.stderr)

        if self._shutdown:
            return SpanExportResult.SUCCESS

        if not spans:
            return SpanExportResult.SUCCESS

        try:
            import requests

            # Convert spans to OTLP JSON format
            resource_spans = {}

            for span in spans:
                # Get resource key
                resource = span.resource
                resource_key = id(resource)

                if resource_key not in resource_spans:
                    resource_spans[resource_key] = {
                        'resource': {
                            'attributes': [
                                {'key': k, 'value': self._encode_value(v)}
                                for k, v in resource.attributes.items()
                            ]
                        },
                        'scopeSpans': []
                    }

                # Find or create scope
                scope_name = span.instrumentation_scope.name if span.instrumentation_scope else 'unknown'
                scope_spans = resource_spans[resource_key]['scopeSpans']

                scope_entry = None
                for ss in scope_spans:
                    if ss['scope'].get('name') == scope_name:
                        scope_entry = ss
                        break

                if not scope_entry:
                    scope_entry = {
                        'scope': {'name': scope_name},
                        'spans': []
                    }
                    scope_spans.append(scope_entry)

                # Convert span
                span_data = {
                    'traceId': format(span.context.trace_id, '032x'),
                    'spanId': format(span.context.span_id, '016x'),
                    'name': span.name,
                    'kind': span.kind.value if hasattr(span.kind, 'value') else 1,
                    'startTimeUnixNano': str(span.start_time),
                    'endTimeUnixNano': str(span.end_time),
                    'attributes': [
                        {'key': k, 'value': self._encode_value(v)}
                        for k, v in (span.attributes or {}).items()
                    ],
                    'status': {}
                }

                if span.parent and span.parent.span_id:
                    span_data['parentSpanId'] = format(span.parent.span_id, '016x')

                scope_entry['spans'].append(span_data)

            # Build payload
            payload = {
                'resourceSpans': list(resource_spans.values())
            }

            # Send to Grafana Cloud
            headers = {
                'Authorization': self.auth_header,
                'Content-Type': 'application/json'
            }

            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code in (200, 202):
                import sys
                print(f"[Grafana] Exported {len(spans)} span(s) successfully", file=sys.stderr)
                return SpanExportResult.SUCCESS
            else:
                import sys
                print(f"[Grafana] Trace export failed: {response.status_code} {response.text[:200]}", file=sys.stderr)
                return SpanExportResult.FAILURE

        except Exception as e:
            import sys
            print(f"[Grafana] Trace export error: {e}", file=sys.stderr)
            return SpanExportResult.FAILURE

    def _encode_value(self, value):
        """Encode a value for OTLP JSON format."""
        if isinstance(value, bool):
            return {'boolValue': value}
        elif isinstance(value, int):
            return {'intValue': str(value)}
        elif isinstance(value, float):
            return {'doubleValue': value}
        else:
            return {'stringValue': str(value)}

    def shutdown(self):
        """Shutdown the exporter."""
        self._shutdown = True

    def force_flush(self, timeout_millis=30000):
        """Force flush any pending spans."""
        pass  # No buffering in this simple implementation


class LokiHandler(logging.Handler):
    """
    Custom logging handler that sends logs to Grafana Loki.

    Uses the Loki HTTP API for log ingestion.
    Batches logs for efficient sending.
    """

    def __init__(self, url: str, labels: dict = None, batch_size: int = 100, flush_interval: float = 5.0):
        super().__init__()
        self.url = url.rstrip('/') + '/loki/api/v1/push'
        self.labels = labels or {}
        self.labels.update({
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
        })
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Auth header
        self.auth_header = _get_auth_header()

        # Batch queue
        self._queue = queue.Queue()
        self._shutdown = threading.Event()

        # Start background flush thread
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def _flush_loop(self):
        """Background thread that periodically flushes logs to Loki."""
        while not self._shutdown.is_set():
            self._shutdown.wait(self.flush_interval)
            self._flush()

    def _flush(self):
        """Send batched logs to Loki."""
        entries = []
        while not self._queue.empty() and len(entries) < self.batch_size:
            try:
                entries.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not entries:
            return

        try:
            import requests

            # Format for Loki push API
            # Each entry is [timestamp_nanoseconds, log_line]
            streams = [{
                "stream": self.labels,
                "values": entries
            }]

            payload = {"streams": streams}

            headers = {
                "Content-Type": "application/json",
            }
            if self.auth_header:
                headers["Authorization"] = self.auth_header

            response = requests.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code not in (200, 204):
                # Log to stderr to avoid recursion
                import sys
                print(f"[Loki] Failed to send logs: {response.status_code} {response.text}", file=sys.stderr)

        except Exception as e:
            import sys
            print(f"[Loki] Error sending logs: {e}", file=sys.stderr)

    def emit(self, record: logging.LogRecord):
        """Handle a log record by adding it to the batch queue."""
        try:
            # Format timestamp as nanoseconds (Loki requirement)
            timestamp_ns = str(int(record.created * 1e9))

            # Format log message with metadata
            log_data = {
                "level": record.levelname.lower(),
                "message": self.format(record),
                "logger": record.name,
            }

            # Add extra fields if present
            if hasattr(record, 'emoji'):
                log_data['emoji'] = record.emoji

            # Loki expects [timestamp, line] format
            log_line = json.dumps(log_data)

            self._queue.put([timestamp_ns, log_line])

            # Flush if batch is full
            if self._queue.qsize() >= self.batch_size:
                self._flush()

        except Exception:
            self.handleError(record)

    def close(self):
        """Shutdown handler and flush remaining logs."""
        self._shutdown.set()
        self._flush()
        super().close()


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


# =============================================================================
# EARLY SETUP: Configure TracerProvider and instrument FastAPI at import time
# This MUST happen before any FastAPI app is created
# =============================================================================
def _early_setup():
    """Set up TracerProvider with our exporter at import time."""
    global _early_tracer_provider, _grafana_initialized

    if not _opentelemetry_available:
        return

    if not GRAFANA_CLOUD_ENABLED:
        return

    if not all([GRAFANA_CLOUD_ENDPOINT, GRAFANA_CLOUD_INSTANCE_ID, GRAFANA_CLOUD_API_KEY]):
        return

    try:
        # Create resource
        resource = Resource.create({
            RESOURCE_SERVICE_NAME: SERVICE_NAME,
            RESOURCE_SERVICE_VERSION: SERVICE_VERSION,
            "deployment.environment": ENVIRONMENT,
        })

        # Create our custom exporter
        auth_header = _get_auth_header()
        otlp_endpoint = f"{GRAFANA_CLOUD_ENDPOINT}/v1/traces"
        exporter = GrafanaCloudSpanExporter(
            endpoint=otlp_endpoint,
            auth_header=auth_header
        )

        # Create TracerProvider
        _early_tracer_provider = TracerProvider(resource=resource)
        _early_tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Check what's currently set BEFORE attempting to set
        current = trace.get_tracer_provider()
        print(f"[Grafana] Current provider before set: {type(current).__name__}")

        # Set as global provider (force if needed)
        try:
            from opentelemetry.trace import _TRACER_PROVIDER_SET_ONCE
            if hasattr(_TRACER_PROVIDER_SET_ONCE, '_done'):
                print(f"[Grafana] Resetting _done flag: {_TRACER_PROVIDER_SET_ONCE._done} -> False")
                _TRACER_PROVIDER_SET_ONCE._done = False
        except Exception as e:
            print(f"[Grafana] Could not reset flag: {e}")

        trace.set_tracer_provider(_early_tracer_provider)

        # Verify it was set
        after = trace.get_tracer_provider()
        print(f"[Grafana] Provider after set: {type(after).__name__}")
        is_ours = after is _early_tracer_provider
        print(f"[Grafana] Is our provider? {is_ours}")

        if not is_ours:
            # Force it by directly setting the global
            print("[Grafana] Warning: set_tracer_provider didn't work, forcing...")
            import opentelemetry.trace as trace_module
            trace_module._TRACER_PROVIDER = _early_tracer_provider
            final = trace.get_tracer_provider()
            print(f"[Grafana] Final provider: {type(final).__name__}, is ours: {final is _early_tracer_provider}")

        print(f"[Grafana] Early TracerProvider configured -> {otlp_endpoint}")

        # Now instrument FastAPI (AFTER TracerProvider is set)
        instrumentor = FastAPIInstrumentor()
        if not instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.instrument()
            print("[Grafana] Early FastAPI instrumentation applied")

        _grafana_initialized = True

    except Exception as e:
        print(f"[Grafana] Early setup error: {e}")
        import traceback
        traceback.print_exc()


# Run early setup at import time
_early_setup()


def init_grafana_cloud(app=None) -> bool:
    """
    Initialize Grafana Cloud observability stack.

    Sets up:
    - OpenTelemetry traces -> Grafana Tempo
    - Structured logs -> Grafana Loki

    Args:
        app: FastAPI application instance (optional, for auto-instrumentation)

    Returns:
        True if initialization successful, False otherwise
    """
    global _grafana_initialized, _tracer_provider, _loki_handler

    if not GRAFANA_CLOUD_ENABLED:
        print("[Grafana] Disabled (GRAFANA_CLOUD_ENABLED=false)")
        return False

    if not GRAFANA_CLOUD_ENDPOINT:
        print("[Grafana] No endpoint configured. Set GRAFANA_CLOUD_ENDPOINT environment variable.")
        print("[Grafana] Example: https://otlp-gateway-prod-us-central-0.grafana.net/otlp")
        return False

    if not GRAFANA_CLOUD_INSTANCE_ID or not GRAFANA_CLOUD_API_KEY:
        print("[Grafana] Missing credentials. Set GRAFANA_CLOUD_INSTANCE_ID and GRAFANA_CLOUD_API_KEY.")
        return False

    success = True

    # Check if early setup already configured tracing
    if _early_tracer_provider:
        print("[Grafana] Tracing already configured via early setup")
        print(f"[Grafana] Service: {SERVICE_NAME} v{SERVICE_VERSION}")
        _tracer_provider = _early_tracer_provider

        # Additional instrumentations (requests, logging)
        if _opentelemetry_available:
            # Instrument the specific app instance
            if app:
                try:
                    FastAPIInstrumentor.instrument_app(app)
                    print(f"[Grafana] FastAPI app instrumented: {app.title}")
                except Exception as e:
                    print(f"[Grafana] App instrumentation note: {e}")

            try:
                RequestsInstrumentor().instrument()
                print("[Grafana] Requests library auto-instrumentation enabled")
            except Exception as e:
                print(f"[Grafana] Requests instrumentation note: {e}")

            try:
                LoggingInstrumentor().instrument(set_logging_format=True)
                print("[Grafana] Logging auto-instrumentation enabled")
            except Exception as e:
                print(f"[Grafana] Logging instrumentation note: {e}")
    elif not _opentelemetry_available:
        print("[Grafana] OpenTelemetry not available")
        success = False
    else:
        print("[Grafana] Warning: Early setup did not run - tracing may not work")

    # Initialize Loki logging
    # Note: Grafana Cloud Loki uses a DIFFERENT endpoint than OTLP gateway
    # OTLP Gateway: https://otlp-gateway-prod-{region}.grafana.net/otlp (for traces)
    # Loki: https://logs-prod-XXX.grafana.net (for logs via Loki HTTP API)
    # The Loki endpoint format doesn't match the OTLP gateway region, so user must provide it explicitly
    loki_endpoint = GRAFANA_LOKI_ENDPOINT
    if not loki_endpoint:
        print("[Grafana] No GRAFANA_LOKI_ENDPOINT set. Log shipping to Loki disabled.")
        print("[Grafana] To enable, find your Loki endpoint in Grafana Cloud portal -> Your Stack -> Send Logs")

    if loki_endpoint:
        try:
            print(f"[Grafana] Loki endpoint: {loki_endpoint}")
            _loki_handler = LokiHandler(
                url=loki_endpoint,
                labels={
                    "app": SERVICE_NAME,
                    "version": SERVICE_VERSION,
                    "env": ENVIRONMENT,
                },
                batch_size=50,
                flush_interval=5.0
            )
            _loki_handler.setLevel(logging.INFO)

            # Add to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(_loki_handler)

            print(f"[Grafana] Logging enabled -> Loki at {_loki_handler.url}")

        except Exception as e:
            print(f"[Grafana] Loki initialization failed: {e}")
            success = False

    if success:
        _grafana_initialized = True
        print(f"[Grafana] Cloud observability initialized successfully")
        print(f"[Grafana] Endpoint: {GRAFANA_CLOUD_ENDPOINT}")

    return success


def shutdown_grafana_cloud():
    """Shutdown Grafana Cloud integrations and flush pending data."""
    global _tracer_provider, _loki_handler, _grafana_initialized

    if not _grafana_initialized:
        print("[Grafana] Nothing to shutdown (not initialized)")
        return

    # Shutdown tracing
    if _tracer_provider:
        try:
            _tracer_provider.shutdown()
            print("[Grafana] Tracing shutdown complete")
        except Exception as e:
            print(f"[Grafana] Tracing shutdown error: {e}")

    # Shutdown Loki handler
    if _loki_handler:
        try:
            _loki_handler.close()
            print("[Grafana] Loki handler shutdown complete")
        except Exception as e:
            print(f"[Grafana] Loki shutdown error: {e}")

    _grafana_initialized = False
    print("[Grafana] Shutdown complete")


def get_tracer(name: str = __name__):
    """
    Get a tracer for creating custom spans.

    Returns a no-op tracer if Grafana Cloud is disabled.

    Args:
        name: Name for the tracer (typically __name__)

    Returns:
        OpenTelemetry Tracer or NoOpTracer
    """
    if _grafana_initialized and _opentelemetry_available:
        return trace.get_tracer(name)
    return _noop_tracer


def add_span_attributes(span, **attributes):
    """
    Helper to add multiple attributes to a span.

    Works with both real spans and NoOpSpan.
    """
    for key, value in attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, str(value) if not isinstance(value, (int, float, bool)) else value)
            except Exception:
                pass


def record_exception(span, exception: Exception, status_message: str = None):
    """
    Record an exception in the current span.

    Works with both real spans and NoOpSpan.
    """
    try:
        span.record_exception(exception)
        if _opentelemetry_available:
            span.set_status(Status(StatusCode.ERROR, status_message or str(exception)))
    except Exception:
        pass


def traced(span_name: str = None):
    """
    Decorator to automatically trace a function.

    Works even when Grafana Cloud is disabled (becomes a no-op).

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


def is_grafana_enabled() -> bool:
    """Check if Grafana Cloud is enabled and initialized."""
    return _grafana_initialized


# Convenience re-exports for backward compatibility
def init_tracing(app=None):
    """Alias for init_grafana_cloud for backward compatibility."""
    return init_grafana_cloud(app)


def shutdown_tracing():
    """Alias for shutdown_grafana_cloud for backward compatibility."""
    return shutdown_grafana_cloud()
