"""
Core Extraction Module: GPT-4o extraction for natural language queries.

This module provides:
- GPT-4o extraction from natural language to structured NEW schema
- Prompt loading utilities
- OpenAI client initialization
"""

from .gpt_extractor import (
    load_extraction_prompt,
    initialize_openai_client,
    extract_from_query,
    GPTExtractor
)

__all__ = [
    "load_extraction_prompt",
    "initialize_openai_client",
    "extract_from_query",
    "GPTExtractor"
]
