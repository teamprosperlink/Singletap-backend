"""
Hybrid Extractor: GPT Full Extraction + NuExtract Validation

Architecture:
  Level 1: GPT-4o-mini does FULL extraction using GLOBAL_REFERENCE_CONTEXT.md (~30K tokens)
  Level 2: NuExtract validates using MINIMAL prompt NUEXTRACT_VALIDATION_PROMPT.md (~2K tokens)

Key Design:
- GPT uses FULL prompt for semantic understanding (handles nuanced cases)
- NuExtract uses MINIMAL prompt for format validation (fast, fits in context)
- Fallback safety: If NuExtract fails, GPT output is still usable
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


@dataclass
class HybridExtractionResult:
    """Result from hybrid extraction pipeline."""
    query: str
    # Level 1: GPT Full Extraction
    gpt_json: Optional[Dict[str, Any]]
    gpt_latency_ms: float
    gpt_success: bool
    # Level 2: NuExtract Validation
    nuextract_json: Optional[Dict[str, Any]]
    nuextract_latency_ms: float
    nuextract_success: bool
    # Final Output (all fields with defaults must come last)
    gpt_error: Optional[str] = None
    nuextract_error: Optional[str] = None
    final_json: Optional[Dict[str, Any]] = None
    total_latency_ms: float = 0.0
    success: bool = False
    fallback_used: bool = False


# ============================================================================
# PROMPT LOADING
# ============================================================================

def _get_project_root() -> str:
    """Get project root directory."""
    current_file = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))


def load_prompt(prompt_path: Optional[str] = None) -> Optional[str]:
    """
    Load the FULL GLOBAL_REFERENCE_CONTEXT.md prompt for GPT.

    Args:
        prompt_path: Path to prompt file. If None, uses default location.

    Returns:
        Full prompt text, or None if loading failed
    """
    if prompt_path is None:
        prompt_path = os.path.join(_get_project_root(), "prompt", "GLOBAL_REFERENCE_CONTEXT.md")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        return prompt_text
    except Exception as e:
        print(f"[ERROR] Failed to load prompt: {e}")
        return None


def load_validation_prompt() -> Optional[str]:
    """
    Load the MINIMAL NUEXTRACT_VALIDATION_PROMPT.md for NuExtract.

    This is a compact ~2K token prompt optimized for NuExtract's context window.

    Returns:
        Validation prompt text, or None if loading failed
    """
    prompt_path = os.path.join(_get_project_root(), "prompt", "NUEXTRACT_VALIDATION_PROMPT.md")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        return prompt_text
    except Exception as e:
        print(f"[ERROR] Failed to load validation prompt: {e}")
        return None


# ============================================================================
# LEVEL 1: GPT FULL EXTRACTION
# ============================================================================

def gpt_full_extract(
    query: str,
    prompt_content: str,
    openai_client: OpenAI,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    """
    Level 1: GPT does FULL extraction using GLOBAL_REFERENCE_CONTEXT.md.

    Args:
        query: Natural language query
        prompt_content: FULL GLOBAL_REFERENCE_CONTEXT.md content
        openai_client: Initialized OpenAI client
        model: GPT model to use (default: gpt-4o-mini for cost efficiency)
        temperature: Sampling temperature (0.0 for determinism)

    Returns:
        (extracted_json, latency_ms, error)
    """
    start_time = time.time()

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": f"Extract JSON for this query: {query}"}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        latency_ms = (time.time() - start_time) * 1000
        output_text = response.choices[0].message.content
        extracted_json = json.loads(output_text)

        return extracted_json, latency_ms, None

    except json.JSONDecodeError as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, f"JSON parse error: {str(e)}"
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, str(e)


# ============================================================================
# LEVEL 2: NUEXTRACT VALIDATION
# ============================================================================

# Cached validation prompt (loaded once)
_validation_prompt_cache: Optional[str] = None


def _get_validation_prompt() -> Optional[str]:
    """Get cached validation prompt."""
    global _validation_prompt_cache
    if _validation_prompt_cache is None:
        _validation_prompt_cache = load_validation_prompt()
    return _validation_prompt_cache


def nuextract_validate(
    query: str,
    gpt_json: Dict[str, Any],
    prompt_content: str = None,  # Ignored - uses minimal prompt instead
    model: str = "nuextract:latest",
    timeout: int = 60  # Allow 60s for CPU inference
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    """
    Level 2: NuExtract validates and corrects GPT output using MINIMAL prompt.

    Uses NUEXTRACT_VALIDATION_PROMPT.md (~2K tokens) instead of full prompt.
    This fits in NuExtract's optimal context window and completes in <10s.

    Args:
        query: Original natural language query
        gpt_json: GPT's extracted JSON
        prompt_content: IGNORED - uses minimal validation prompt
        model: NuExtract model name in Ollama
        timeout: Request timeout in seconds (30s should be plenty)

    Returns:
        (validated_json, latency_ms, error)
    """
    start_time = time.time()

    # Load minimal validation prompt
    validation_prompt = _get_validation_prompt()
    if validation_prompt is None:
        return None, 0, "Failed to load validation prompt"

    # Build complete prompt with query and JSON to validate
    full_prompt = f"""{validation_prompt}

---
Query: {query}

JSON to validate and correct:
```json
{json.dumps(gpt_json, indent=2)}
```

Return ONLY the corrected JSON, no explanation.
"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 1500,  # Reduced output length
                    "num_ctx": 4096  # Minimal context for faster processing
                }
            },
            timeout=timeout
        )

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            return None, latency_ms, f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        raw_output = data.get("response", "")

        # Parse JSON from output
        validated_json = parse_json_from_output(raw_output)

        if validated_json is None:
            return None, latency_ms, f"Failed to parse JSON from: {raw_output[:200]}"

        return validated_json, latency_ms, None

    except requests.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, f"Timeout after {timeout}s"
    except requests.ConnectionError:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, f"Cannot connect to Ollama at {OLLAMA_BASE_URL}"
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, str(e)


def parse_json_from_output(raw_output: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from model output, handling various formats."""
    output = raw_output.strip()

    # Remove common end tokens
    for end_token in ["<|end-output|>", "<|eot_id|>", "</s>"]:
        if end_token in output:
            output = output.split(end_token)[0].strip()

    # Try direct parse
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    if "```json" in output:
        try:
            start = output.find("```json") + 7
            end = output.find("```", start)
            if end > start:
                return json.loads(output[start:end].strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON boundaries
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
    except json.JSONDecodeError:
        pass

    return None


# ============================================================================
# SCHEMA VALIDATION
# ============================================================================

REQUIRED_FIELDS = ["intent", "subintent", "domain", "items"]


def validate_schema(json_data: Optional[Dict[str, Any]]) -> bool:
    """
    Validate that JSON has required fields.

    Args:
        json_data: Extracted JSON data

    Returns:
        True if all required fields present and non-null
    """
    if json_data is None:
        return False

    for field in REQUIRED_FIELDS:
        if field not in json_data or json_data[field] is None:
            return False

    return True


# ============================================================================
# HYBRID EXTRACTOR CLASS
# ============================================================================

class HybridExtractor:
    """
    Two-level hybrid extraction pipeline.

    Level 1: GPT-4o-mini does FULL extraction using GLOBAL_REFERENCE_CONTEXT.md
    Level 2: NuExtract validates and corrects using MINIMAL validation prompt

    Modes:
        - skip_nuextract=False (default): Full hybrid (GPT + NuExtract validation)
        - skip_nuextract=True: GPT-only mode (skips Level 2)

    Usage:
        # Full hybrid mode
        extractor = HybridExtractor()
        if extractor.initialize():
            result = extractor.extract("Looking to buy a Dell laptop under 50000")
            print(result.final_json)

        # GPT-only mode (skip NuExtract)
        extractor = HybridExtractor(skip_nuextract=True)
        if extractor.initialize():
            result = extractor.extract("Looking to buy a Dell laptop under 50000")
            print(result.final_json)
    """

    def __init__(
        self,
        gpt_model: str = "gpt-4o-mini",
        nuextract_model: str = "nuextract:latest",
        skip_nuextract: bool = False
    ):
        self.gpt_model = gpt_model
        self.nuextract_model = nuextract_model
        self.skip_nuextract = skip_nuextract
        self.openai_client: Optional[OpenAI] = None
        self.prompt_content: Optional[str] = None
        self.initialized: bool = False

    def initialize(
        self,
        api_key: Optional[str] = None,
        prompt_path: Optional[str] = None
    ) -> bool:
        """
        Initialize the hybrid extractor.

        Args:
            api_key: OpenAI API key (reads from OPENAI_API_KEY env if not provided)
            prompt_path: Path to GLOBAL_REFERENCE_CONTEXT.md (uses default if not provided)

        Returns:
            True if initialization successful
        """
        # Load FULL prompt
        self.prompt_content = load_prompt(prompt_path)
        if self.prompt_content is None:
            print("[ERROR] Failed to load GLOBAL_REFERENCE_CONTEXT.md")
            return False

        print(f"[OK] Loaded prompt ({len(self.prompt_content)} chars)")

        # Initialize OpenAI client
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            print("[ERROR] OPENAI_API_KEY not set")
            return False

        self.openai_client = OpenAI(api_key=api_key)
        print("[OK] OpenAI client initialized")

        # Check Ollama availability (only if NuExtract validation is enabled)
        if not self.skip_nuextract:
            try:
                response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
                    print(f"[OK] Ollama running, models: {models}")

                    # Check if NuExtract is available
                    if self.nuextract_model not in models and "nuextract" not in str(models):
                        print(f"[WARN] {self.nuextract_model} not found in Ollama")
                else:
                    print(f"[WARN] Ollama returned HTTP {response.status_code}")
            except Exception as e:
                print(f"[WARN] Cannot connect to Ollama: {e}")
                print("       NuExtract validation will fail. Run: ollama serve")
        else:
            print("[INFO] NuExtract validation skipped (GPT-only mode)")

        self.initialized = True
        print(f"[OK] HybridExtractor initialized")
        print(f"     Level 1: {self.gpt_model}")
        if self.skip_nuextract:
            print(f"     Level 2: SKIPPED (GPT-only mode)")
        else:
            print(f"     Level 2: {self.nuextract_model}")
        return True

    def extract(self, query: str) -> HybridExtractionResult:
        """
        Extract structured data using hybrid pipeline.

        Level 1: GPT Full Extraction
        Level 2: NuExtract Validation

        Args:
            query: Natural language query

        Returns:
            HybridExtractionResult with all extraction data
        """
        total_start = time.time()

        # Check initialization
        if not self.initialized:
            return HybridExtractionResult(
                query=query,
                gpt_json=None, gpt_latency_ms=0, gpt_success=False, gpt_error="Not initialized",
                nuextract_json=None, nuextract_latency_ms=0, nuextract_success=False,
                final_json=None, total_latency_ms=0, success=False
            )

        # =====================================================================
        # LEVEL 1: GPT Full Extraction
        # =====================================================================
        print(f"\n[Level 1] GPT extraction: {query[:50]}...")

        gpt_json, gpt_latency, gpt_error = gpt_full_extract(
            query=query,
            prompt_content=self.prompt_content,
            openai_client=self.openai_client,
            model=self.gpt_model
        )

        if gpt_error:
            print(f"  [FAIL] GPT error: {gpt_error}")
            return HybridExtractionResult(
                query=query,
                gpt_json=None, gpt_latency_ms=gpt_latency, gpt_success=False, gpt_error=gpt_error,
                nuextract_json=None, nuextract_latency_ms=0, nuextract_success=False,
                final_json=None, total_latency_ms=(time.time() - total_start) * 1000, success=False
            )

        print(f"  [OK] GPT extracted ({gpt_latency:.0f}ms)")

        # =====================================================================
        # LEVEL 2: NuExtract Validation (optional - can be skipped)
        # =====================================================================
        nuextract_json = None
        nuextract_latency = 0.0
        nuextract_error = None
        nuextract_success = False
        fallback_used = False

        if self.skip_nuextract:
            # GPT-only mode: skip NuExtract validation
            print(f"[Level 2] Skipped (GPT-only mode)")
            final_json = gpt_json
            nuextract_success = True  # Consider successful since we're skipping
        else:
            # Full hybrid mode: run NuExtract validation
            print(f"[Level 2] NuExtract validation...")

            nuextract_json, nuextract_latency, nuextract_error = nuextract_validate(
                query=query,
                gpt_json=gpt_json,
                prompt_content=self.prompt_content,
                model=self.nuextract_model
            )

            # Determine final output
            if nuextract_error or not validate_schema(nuextract_json):
                # Fallback to GPT output
                print(f"  [WARN] NuExtract failed: {nuextract_error or 'Invalid schema'}")
                print(f"  [INFO] Using GPT output as fallback")
                final_json = gpt_json
                fallback_used = True
                nuextract_success = False
            else:
                print(f"  [OK] NuExtract validated ({nuextract_latency:.0f}ms)")
                final_json = nuextract_json
                nuextract_success = True

        total_latency = (time.time() - total_start) * 1000
        print(f"[Done] Total: {total_latency:.0f}ms (GPT: {gpt_latency:.0f}ms, NuExtract: {nuextract_latency:.0f}ms)")

        return HybridExtractionResult(
            query=query,
            gpt_json=gpt_json,
            gpt_latency_ms=gpt_latency,
            gpt_success=True,
            nuextract_json=nuextract_json,
            nuextract_latency_ms=nuextract_latency,
            nuextract_success=nuextract_success,
            nuextract_error=nuextract_error,
            final_json=final_json,
            total_latency_ms=total_latency,
            success=True,
            fallback_used=fallback_used
        )


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def hybrid_extract(query: str, extractor: Optional[HybridExtractor] = None) -> Dict[str, Any]:
    """
    Convenience function for hybrid extraction.

    Args:
        query: Natural language query
        extractor: Optional pre-initialized extractor

    Returns:
        Extracted JSON dictionary

    Raises:
        RuntimeError: If extraction fails
    """
    if extractor is None:
        extractor = HybridExtractor()
        if not extractor.initialize():
            raise RuntimeError("Failed to initialize HybridExtractor")

    result = extractor.extract(query)

    if not result.success or result.final_json is None:
        raise RuntimeError(f"Extraction failed: {result.gpt_error or result.nuextract_error}")

    return result.final_json


# ============================================================================
# CLI TEST
# ============================================================================

TEST_QUERIES = [
    "Looking to buy a Dell laptop in Bangalore under 50000",
    "I am a plumber in Bangalore, charge 500 per hour",
    "Need electrician for AC repair in Mumbai, budget 2000",
    "Selling iPhone 15 Pro in Delhi for 80000 to 100000",
]


def run_hybrid_test():
    """Run hybrid extraction test."""
    print("=" * 70)
    print("HYBRID EXTRACTOR TEST")
    print("Level 1: GPT Full Extraction (gpt-4o-mini)")
    print("Level 2: NuExtract Validation")
    print("Prompt: FULL GLOBAL_REFERENCE_CONTEXT.md for BOTH levels")
    print("=" * 70)

    extractor = HybridExtractor()
    if not extractor.initialize():
        print("\n[ERROR] Failed to initialize. Check API key and Ollama.")
        return

    results = []
    for query in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("-" * 60)

        result = extractor.extract(query)
        results.append(result)

        if result.success:
            print(f"\nFinal JSON:")
            print(json.dumps(result.final_json, indent=2))
            if result.fallback_used:
                print("\n[NOTE] Used GPT output (NuExtract failed)")
        else:
            print(f"\n[ERROR] Extraction failed")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.success)
    fallback_count = sum(1 for r in results if r.fallback_used)
    avg_total = sum(r.total_latency_ms for r in results if r.success) / max(success_count, 1)
    avg_gpt = sum(r.gpt_latency_ms for r in results if r.gpt_success) / max(success_count, 1)

    print(f"Success: {success_count}/{len(results)}")
    print(f"Fallback to GPT: {fallback_count}/{len(results)}")
    print(f"Avg total latency: {avg_total:.0f}ms")
    print(f"Avg GPT latency: {avg_gpt:.0f}ms")


if __name__ == "__main__":
    run_hybrid_test()
