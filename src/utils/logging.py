"""
Standardized logging utilities for Vriddhi Matching Engine.

Provides consistent logging with emoji indicators across all modules.
Consolidates 398+ logging statements into reusable helpers.
"""

import logging
from enum import Enum
from typing import Optional


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


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Create a standardized logger with consistent formatting.

    Args:
        name: Logger name (typically __name__ of the module)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Only add handler if logger doesn't have one
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_start(logger: logging.Logger, msg: str):
    """Log a start/initialization message"""
    logger.info(f"{LogEmoji.START.value} {msg}")


def log_success(logger: logging.Logger, msg: str):
    """Log a success message"""
    logger.info(f"{LogEmoji.SUCCESS.value} {msg}")


def log_error(logger: logging.Logger, msg: str, exc_info: bool = False):
    """
    Log an error message

    Args:
        logger: Logger instance
        msg: Error message
        exc_info: Include exception traceback (default: False)
    """
    logger.error(f"{LogEmoji.ERROR.value} {msg}", exc_info=exc_info)


def log_warning(logger: logging.Logger, msg: str):
    """Log a warning message"""
    logger.warning(f"{LogEmoji.WARNING.value} {msg}")


def log_info(logger: logging.Logger, msg: str):
    """Log an info message"""
    logger.info(f"{LogEmoji.INFO.value} {msg}")


def log_search(logger: logging.Logger, msg: str):
    """Log a search operation"""
    logger.info(f"{LogEmoji.SEARCH.value} {msg}")


def log_store(logger: logging.Logger, msg: str):
    """Log a storage operation"""
    logger.info(f"{LogEmoji.STORE.value} {msg}")


def log_match(logger: logging.Logger, msg: str):
    """Log a matching operation"""
    logger.info(f"{LogEmoji.MATCH.value} {msg}")


def log_extract(logger: logging.Logger, msg: str):
    """Log an extraction operation (GPT)"""
    logger.info(f"{LogEmoji.EXTRACT.value} {msg}")


def log_filter(logger: logging.Logger, msg: str):
    """Log a filtering operation"""
    logger.info(f"{LogEmoji.FILTER.value} {msg}")


def log_semantic(logger: logging.Logger, msg: str):
    """Log a semantic matching operation"""
    logger.info(f"{LogEmoji.SEMANTIC.value} {msg}")


def log_boolean(logger: logging.Logger, msg: str):
    """Log a boolean matching operation"""
    logger.info(f"{LogEmoji.BOOLEAN.value} {msg}")


def log_location(logger: logging.Logger, msg: str):
    """Log a location matching operation"""
    logger.info(f"{LogEmoji.LOCATION.value} {msg}")
