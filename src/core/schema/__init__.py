"""
Core Schema Module: Schema validation and transformation.

This module handles:
- NEW schema validation (14 fields, axis-based constraints)
- Schema transformation from NEW → OLD format
- String normalization and constraint flattening
"""

from .normalizer import (
    normalize_and_validate_v2,
    transform_new_to_old,
    validate_new_schema,
    SchemaValidationError
)

__all__ = [
    "normalize_and_validate_v2",
    "transform_new_to_old",
    "validate_new_schema",
    "SchemaValidationError"
]
