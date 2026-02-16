"""
Model Comparison Test Module

Tests for comparing GPT vs Local Models for JSON extraction.

Phase 1: Compare extraction quality
- test_model_comparison.py: Compare GPT-4o vs NuExtract/Qwen/SmolLM/Phi4

Phase 2: Test two-layer architecture
- test_two_layer_architecture.py: GPT + Local Model validation

Phase 3: Hybrid Pipeline (FINAL)
- test_hybrid_pipeline.py: GPT Full Extract + NuExtract Validate
  CRITICAL: Both levels use FULL GLOBAL_REFERENCE_CONTEXT.md

Usage:
    # Run hybrid pipeline test (recommended)
    python -m tests.model_comparison.test_hybrid_pipeline --quick

    # Run model comparison
    python -m tests.model_comparison.test_model_comparison --quick

    # Run two-layer architecture test
    python -m tests.model_comparison.test_two_layer_architecture --model nuextract

    # Test local model extractor
    python -m tests.model_comparison.local_model_extractor

Prerequisites:
    1. Ollama must be running: ollama serve
    2. Pull required models:
       - ollama pull nuextract
       - ollama pull qwen3:0.6b
       - ollama pull smollm3:3b
       - ollama pull phi4-mini

All models use the same prompt: prompt/GLOBAL_REFERENCE_CONTEXT.md
"""

from tests.model_comparison.local_model_extractor import (
    LocalModelExtractor,
    ExtractionResult,
    check_ollama_status,
    list_available_models,
    load_extraction_prompt,
    SUPPORTED_MODELS,
)

__all__ = [
    "LocalModelExtractor",
    "ExtractionResult",
    "check_ollama_status",
    "list_available_models",
    "load_extraction_prompt",
    "SUPPORTED_MODELS",
]
