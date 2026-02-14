"""
GPT-4o Extraction Module: Extract structured NEW schema from natural language.

This module handles:
- Loading the extraction prompt from GLOBAL_REFERENCE_CONTEXT.md
- Initializing OpenAI client
- Calling GPT-4o API to extract structured NEW schema from queries
"""

import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI


# ============================================================================
# PROMPT LOADING
# ============================================================================

def load_extraction_prompt(prompt_path: Optional[str] = None) -> Optional[str]:
    """
    Load the extraction prompt from file.

    Args:
        prompt_path: Path to the prompt file. If None, uses default location.

    Returns:
        Prompt text, or None if loading failed

    Default Location:
        PROJECT_ROOT/prompt/GLOBAL_REFERENCE_CONTEXT.md
    """
    if prompt_path is None:
        # Default to prompt/GLOBAL_REFERENCE_CONTEXT.md in project root
        # Navigate up from src/core/extraction/ to project root
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        prompt_path = os.path.join(project_root, "prompt", "GLOBAL_REFERENCE_CONTEXT.md")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        print(f"[OK] Extraction prompt loaded from {prompt_path} ({len(prompt_text)} chars)")
        return prompt_text
    except Exception as e:
        print(f"[WARN] Warning: Could not load extraction prompt: {e}")
        return None


# ============================================================================
# OPENAI CLIENT INITIALIZATION
# ============================================================================

def initialize_openai_client(api_key: Optional[str] = None) -> Optional[OpenAI]:
    """
    Initialize OpenAI client.

    Args:
        api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env variable.

    Returns:
        Initialized OpenAI client, or None if API key not available
    """
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAI client initialized")
        return client
    else:
        print("⚠️ Warning: OPENAI_API_KEY not set. Extraction will not work.")
        return None


# ============================================================================
# GPT EXTRACTION
# ============================================================================

def extract_from_query(
    query: str,
    openai_client: OpenAI,
    extraction_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.0
) -> Dict[str, Any]:
    """
    Extract structured NEW schema from natural language query using GPT-4o.

    Args:
        query: Natural language query (e.g., "need a plumber who speaks kannada")
        openai_client: Initialized OpenAI client
        extraction_prompt: System prompt for extraction (from GLOBAL_REFERENCE_CONTEXT.md)
        model: OpenAI model to use (default: gpt-4o)
        temperature: Sampling temperature (default: 0.0 for deterministic output)

    Returns:
        Structured NEW schema dictionary

    Raises:
        ValueError: If OpenAI client or extraction prompt not provided
        RuntimeError: If API call fails

    Example:
        >>> client = initialize_openai_client()
        >>> prompt = load_extraction_prompt()
        >>> result = extract_from_query(
        ...     "looking for a plumber in bangalore",
        ...     client,
        ...     prompt
        ... )
        >>> print(result["intent"])
        "service"
    """
    if not openai_client:
        raise ValueError("OpenAI client not initialized. Call initialize_openai_client() first.")

    if not extraction_prompt:
        raise ValueError("Extraction prompt not loaded. Call load_extraction_prompt() first.")

    try:
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": query}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        # Parse response
        output_text = response.choices[0].message.content
        extracted_data = json.loads(output_text)

        print(f"✅ Successfully extracted schema for query: {query[:50]}...")
        return extracted_data

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GPT response as JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Extraction failed: {str(e)}")


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

class GPTExtractor:
    """
    Convenience wrapper for GPT extraction with state management.

    Usage:
        extractor = GPTExtractor()
        extractor.initialize()
        result = extractor.extract("need a plumber in bangalore")
    """

    def __init__(self):
        self.openai_client: Optional[OpenAI] = None
        self.extraction_prompt: Optional[str] = None
        self.initialized: bool = False

    def initialize(
        self,
        api_key: Optional[str] = None,
        prompt_path: Optional[str] = None
    ) -> bool:
        """
        Initialize the extractor (load prompt + OpenAI client).

        Args:
            api_key: OpenAI API key (optional, reads from env if not provided)
            prompt_path: Path to extraction prompt (optional, uses default if not provided)

        Returns:
            True if initialization successful, False otherwise
        """
        self.openai_client = initialize_openai_client(api_key)
        self.extraction_prompt = load_extraction_prompt(prompt_path)

        self.initialized = (self.openai_client is not None and self.extraction_prompt is not None)

        if self.initialized:
            print("✅ GPT Extractor fully initialized")
        else:
            print("⚠️ GPT Extractor initialization incomplete")

        return self.initialized

    def extract(
        self,
        query: str,
        model: str = "gpt-4o",
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Extract structured schema from query.

        Args:
            query: Natural language query
            model: OpenAI model to use
            temperature: Sampling temperature

        Returns:
            Structured NEW schema dictionary

        Raises:
            RuntimeError: If extractor not initialized
        """
        if not self.initialized:
            raise RuntimeError("Extractor not initialized. Call initialize() first.")

        return extract_from_query(
            query=query,
            openai_client=self.openai_client,
            extraction_prompt=self.extraction_prompt,
            model=model,
            temperature=temperature
        )
