"""
Structured logging utilities for Vriddhi Matching Engine.

Uses structlog for structured, contextual logging with emoji indicators.
Provides consistent logging across all modules with JSON output capability.
"""

import logging
import sys
from enum import Enum
from typing import Any, Optional

import structlog
from structlog.typing import Processor


class LogEmoji(Enum):
    """Standard emoji indicators for different log types"""
    START = "🚀"
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SEARCH = "🔍"
    STORE = "💾"
    MATCH = "🎯"
    EXTRACT = "🤖"
    FILTER = "🔎"
    SEMANTIC = "🧠"
    BOOLEAN = "⚖️"
    LOCATION = "📍"
    LOADING = "⏳"
    CONFIG = "🌍"
    KEY = "🔑"
    DOC = "📄"
    SYNC = "🔄"
    DATA = "📊"
    DB = "📝"
    VECTOR = "🔢"


def add_emoji_processor(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Structlog processor that prepends emoji to log messages based on emoji key.

    Usage:
        log.info("Server starting", emoji="start")
        # Output: 🚀 Server starting
    """
    emoji_key = event_dict.pop("emoji", None)
    if emoji_key:
        emoji_map = {
            "start": LogEmoji.START.value,
            "success": LogEmoji.SUCCESS.value,
            "error": LogEmoji.ERROR.value,
            "warning": LogEmoji.WARNING.value,
            "info": LogEmoji.INFO.value,
            "search": LogEmoji.SEARCH.value,
            "store": LogEmoji.STORE.value,
            "match": LogEmoji.MATCH.value,
            "extract": LogEmoji.EXTRACT.value,
            "filter": LogEmoji.FILTER.value,
            "semantic": LogEmoji.SEMANTIC.value,
            "boolean": LogEmoji.BOOLEAN.value,
            "location": LogEmoji.LOCATION.value,
            "loading": LogEmoji.LOADING.value,
            "config": LogEmoji.CONFIG.value,
            "key": LogEmoji.KEY.value,
            "doc": LogEmoji.DOC.value,
            "sync": LogEmoji.SYNC.value,
            "data": LogEmoji.DATA.value,
            "db": LogEmoji.DB.value,
            "vector": LogEmoji.VECTOR.value,
        }
        emoji = emoji_map.get(emoji_key, "")
        if emoji:
            event_dict["event"] = f"{emoji} {event_dict.get('event', '')}"
    return event_dict


def configure_structlog(
    json_output: bool = False,
    log_level: str = "INFO",
    include_timestamp: bool = True
) -> None:
    """
    Configure structlog with consistent settings for the application.

    Args:
        json_output: If True, output logs as JSON (for production/cloud logging)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        include_timestamp: If True, include timestamp in logs
    """
    # Shared processors for both dev and prod
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_emoji_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if include_timestamp:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    if json_output:
        # Production: JSON output for structured log aggregation
        shared_processors.append(structlog.processors.format_exc_info)
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Console-friendly colored output
        shared_processors.append(structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        ))

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog BoundLogger instance

    Usage:
        from src.utils.logging import get_logger

        log = get_logger(__name__)
        log.info("Server starting", emoji="start", port=8000)
        log.error("Connection failed", emoji="error", error=str(e))
    """
    return structlog.get_logger(name)


# Convenience functions for common log operations
def log_start(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a start/initialization message"""
    log.info(msg, emoji="start", **kwargs)


def log_success(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a success message"""
    log.info(msg, emoji="success", **kwargs)


def log_error(
    log: structlog.stdlib.BoundLogger,
    msg: str,
    exc_info: bool = False,
    **kwargs: Any
) -> None:
    """Log an error message"""
    log.error(msg, emoji="error", exc_info=exc_info, **kwargs)


def log_warning(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a warning message"""
    log.warning(msg, emoji="warning", **kwargs)


def log_info(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log an info message"""
    log.info(msg, emoji="info", **kwargs)


def log_search(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a search operation"""
    log.info(msg, emoji="search", **kwargs)


def log_store(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a storage operation"""
    log.info(msg, emoji="store", **kwargs)


def log_match(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a matching operation"""
    log.info(msg, emoji="match", **kwargs)


def log_extract(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log an extraction operation (GPT)"""
    log.info(msg, emoji="extract", **kwargs)


def log_filter(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a filtering operation"""
    log.info(msg, emoji="filter", **kwargs)


def log_semantic(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a semantic matching operation"""
    log.info(msg, emoji="semantic", **kwargs)


def log_boolean(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a boolean matching operation"""
    log.info(msg, emoji="boolean", **kwargs)


def log_location(log: structlog.stdlib.BoundLogger, msg: str, **kwargs: Any) -> None:
    """Log a location matching operation"""
    log.info(msg, emoji="location", **kwargs)


# Initialize structlog with default settings on module import
# Can be reconfigured later with configure_structlog()
configure_structlog(json_output=False, log_level="INFO")
