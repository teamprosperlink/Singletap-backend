"""
Canonicalization layer for resolving non-deterministic values from GPT extraction.

Sits between GPT extraction and schema normalization:
    GPT -> CANONICALIZE -> normalize_and_validate_v2 -> OLD schema -> match
"""

from canonicalization.orchestrator import canonicalize_listing

__all__ = ["canonicalize_listing"]
