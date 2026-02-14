"""
Shared utility functions for Vriddhi Matching Engine.

Helper functions used across multiple modules.
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime


def generate_uuid() -> str:
    """
    Generate a new UUID string.

    Returns:
        UUID string in hex format
    """
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.

    Returns:
        ISO formatted timestamp string
    """
    return datetime.utcnow().isoformat()


def safe_get(data: Dict, keys: List[str], default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to search
        keys: List of keys for nested access
        default: Default value if key path doesn't exist

    Returns:
        Value at key path or default

    Example:
        safe_get({"a": {"b": {"c": 123}}}, ["a", "b", "c"]) -> 123
        safe_get({"a": {"b": {}}}, ["a", "b", "c"], 0) -> 0
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator between keys

    Returns:
        Flattened dictionary

    Example:
        flatten_dict({"a": {"b": 1, "c": 2}}) -> {"a_b": 1, "a_c": 2}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def is_valid_uuid(uuid_string: str) -> bool:
    """
    Check if string is a valid UUID.

    Args:
        uuid_string: String to validate

    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, AttributeError):
        return False


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to append to truncated text

    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """
    Clean and normalize text.

    Args:
        text: Text to clean

    Returns:
        Cleaned text (lowercase, stripped, normalized whitespace)
    """
    # Strip leading/trailing whitespace
    text = text.strip()
    # Normalize whitespace (multiple spaces to single space)
    text = ' '.join(text.split())
    # Convert to lowercase
    text = text.lower()
    return text


def get_intent_key(intent: str, subintent: str) -> str:
    """
    Generate intent key for matching.

    Args:
        intent: Intent type (product, service, mutual)
        subintent: Subintent type (buy, sell, seek, provide, connect)

    Returns:
        Intent key in format "intent_subintent"

    Example:
        get_intent_key("product", "buy") -> "product_buy"
    """
    return f"{intent}_{subintent}"


def parse_intent_key(intent_key: str) -> tuple:
    """
    Parse intent key into components.

    Args:
        intent_key: Intent key in format "intent_subintent"

    Returns:
        Tuple of (intent, subintent)

    Example:
        parse_intent_key("product_buy") -> ("product", "buy")
    """
    parts = intent_key.split("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""
