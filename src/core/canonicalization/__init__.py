"""
Canonicalization layer for Vriddhi Matching Engine.

This layer sits between GPT-4o extraction and schema normalization to resolve
non-deterministic LLM outputs into canonical, deterministic values.
"""

from .orchestrator import canonicalize_listing

__all__ = ["canonicalize_listing"]
