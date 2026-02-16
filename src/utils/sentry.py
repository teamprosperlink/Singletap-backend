"""
Sentry Error Tracking and Performance Monitoring.

Sentry captures errors, exceptions, and performance data from your application.

Environment Variables:
    SENTRY_DSN: Your Sentry DSN (get from sentry.io)
    SENTRY_ENABLED: Enable/disable Sentry (default: false)
    ENVIRONMENT: Environment name (development/staging/production)
    OTEL_SERVICE_VERSION: App version for release tracking

Usage:
    from src.utils.sentry import init_sentry

    # In main.py startup
    init_sentry()

    # Errors are automatically captured!
    # You can also capture manually:
    import sentry_sdk
    sentry_sdk.capture_message("Something happened")
    sentry_sdk.capture_exception(exception)
"""

import os

# Configuration
SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "false").lower() == "true"
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")

_sentry_initialized = False


def init_sentry():
    """
    Initialize Sentry SDK for error tracking.

    Automatically captures:
    - Unhandled exceptions
    - HTTP errors (4xx, 5xx)
    - Performance traces
    - Database queries (if configured)
    """
    global _sentry_initialized

    if not SENTRY_ENABLED:
        print("[Sentry] Disabled (SENTRY_ENABLED=false)")
        return

    if not SENTRY_DSN:
        print("[Sentry] No DSN configured. Set SENTRY_DSN environment variable.")
        print("[Sentry] Get your DSN from: sentry.io -> Project Settings -> Client Keys")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=ENVIRONMENT,
            release=f"vriddhi-matching-engine@{SERVICE_VERSION}",

            # Performance monitoring
            traces_sample_rate=0.1 if ENVIRONMENT == "production" else 1.0,
            profiles_sample_rate=0.1 if ENVIRONMENT == "production" else 1.0,

            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],

            # Don't send PII (personal data)
            send_default_pii=False,

            # Filter out health check noise
            before_send=_filter_events,
        )

        _sentry_initialized = True
        print(f"[Sentry] Initialized for {ENVIRONMENT}")
        print(f"[Sentry] Release: vriddhi-matching-engine@{SERVICE_VERSION}")

    except ImportError:
        print("[Sentry] sentry-sdk not installed. Run: pip install sentry-sdk[fastapi]")
    except Exception as e:
        print(f"[Sentry] Failed to initialize: {e}")


def _filter_events(event, hint):
    """Filter out noisy events before sending to Sentry."""
    # Don't send health check errors
    if "transaction" in event:
        transaction = event.get("transaction", "")
        if transaction in ["/health", "/ping", "/"]:
            return None

    # Don't send 404 errors (usually noise)
    if "exception" in event:
        exc_info = hint.get("exc_info")
        if exc_info:
            exc_type = exc_info[0]
            if exc_type and exc_type.__name__ == "HTTPException":
                # Get status code if available
                exc_value = exc_info[1]
                if hasattr(exc_value, "status_code") and exc_value.status_code == 404:
                    return None

    return event


def capture_message(message: str, level: str = "info"):
    """
    Manually capture a message in Sentry.

    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
    """
    if not _sentry_initialized:
        return

    import sentry_sdk
    sentry_sdk.capture_message(message, level=level)


def capture_exception(exception: Exception = None):
    """
    Manually capture an exception in Sentry.

    Args:
        exception: Exception to capture (uses current exception if None)
    """
    if not _sentry_initialized:
        return

    import sentry_sdk
    sentry_sdk.capture_exception(exception)


def set_user(user_id: str, email: str = None, username: str = None):
    """
    Set user context for error reports.

    Args:
        user_id: User identifier
        email: User email (optional)
        username: Username (optional)
    """
    if not _sentry_initialized:
        return

    import sentry_sdk
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": username,
    })


def set_context(name: str, data: dict):
    """
    Set additional context for error reports.

    Args:
        name: Context name (e.g., "listing", "query")
        data: Context data dictionary
    """
    if not _sentry_initialized:
        return

    import sentry_sdk
    sentry_sdk.set_context(name, data)


def is_sentry_enabled() -> bool:
    """Check if Sentry is enabled and initialized."""
    return _sentry_initialized
