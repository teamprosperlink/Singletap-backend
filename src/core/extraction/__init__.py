"""
Core Extraction Module: GPT-4o extraction for natural language queries.

This module provides:
- GPT-4o extraction from natural language to structured NEW schema
- Hybrid extraction (GPT + NuExtract validation)
- Prompt loading utilities
- OpenAI client initialization
"""

from .gpt_extractor import (
    load_extraction_prompt,
    initialize_openai_client,
    extract_from_query,
    GPTExtractor
)

from .hybrid_extractor import (
    HybridExtractor,
    HybridExtractionResult,
    hybrid_extract,
    load_prompt,
    gpt_full_extract,
    nuextract_validate,
)

__all__ = [
    # GPT Extractor
    "load_extraction_prompt",
    "initialize_openai_client",
    "extract_from_query",
    "GPTExtractor",
    # Hybrid Extractor
    "HybridExtractor",
    "HybridExtractionResult",
    "hybrid_extract",
    "load_prompt",
    "gpt_full_extract",
    "nuextract_validate",
]
