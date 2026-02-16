"""
Local Model Extractor: Extract structured JSON using local models via Ollama.

Supports:
- NuExtract-2.0-2B (best for extraction)
- Qwen3-0.6B (smallest)
- SmolLM3-3B (function calling)
- Phi-4-mini (reasoning)

Uses the same prompt file (GLOBAL_REFERENCE_CONTEXT.md) as GPT extraction.
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Model mappings (Ollama model names)
SUPPORTED_MODELS = {
    "nuextract": "nuextract",  # NuExtract-2.0-2B
    "qwen3": "qwen3:0.6b",     # Qwen3-0.6B
    "smollm3": "smollm3:3b",   # SmolLM3-3B
    "phi4-mini": "phi4-mini",  # Phi-4-mini-instruct
}


@dataclass
class ExtractionResult:
    """Result of an extraction attempt."""
    model: str
    query: str
    extracted_json: Optional[Dict[str, Any]]
    raw_output: str
    latency_ms: float
    success: bool
    error: Optional[str] = None


# ============================================================================
# PROMPT LOADING (reuse same prompt as GPT)
# ============================================================================

def load_extraction_prompt(prompt_path: Optional[str] = None) -> Optional[str]:
    """
    Load the extraction prompt from GLOBAL_REFERENCE_CONTEXT.md.

    Uses the same prompt as GPT extraction for fair comparison.
    """
    if prompt_path is None:
        # Navigate to project root from tests/model_comparison/
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        prompt_path = os.path.join(project_root, "prompt", "GLOBAL_REFERENCE_CONTEXT.md")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        print(f"[OK] Prompt loaded: {len(prompt_text)} chars")
        return prompt_text
    except Exception as e:
        print(f"[ERROR] Failed to load prompt: {e}")
        return None


# ============================================================================
# OLLAMA INTEGRATION
# ============================================================================

def check_ollama_status() -> bool:
    """Check if Ollama is running."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def list_available_models() -> List[str]:
    """List models available in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        return []
    except:
        return []


def pull_model(model_name: str) -> bool:
    """Pull a model from Ollama registry."""
    print(f"[INFO] Pulling model: {model_name}")
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            timeout=600  # 10 min timeout for large models
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Failed to pull model: {e}")
        return False


# ============================================================================
# LOCAL MODEL EXTRACTION
# ============================================================================

def extract_with_local_model(
    query: str,
    model_name: str,
    extraction_prompt: str,
    timeout: int = 120
) -> ExtractionResult:
    """
    Extract structured JSON using a local model via Ollama.

    Args:
        query: Natural language query
        model_name: Ollama model name (e.g., "nuextract", "qwen3:0.6b")
        extraction_prompt: System prompt (GLOBAL_REFERENCE_CONTEXT.md)
        timeout: Request timeout in seconds

    Returns:
        ExtractionResult with extracted JSON and metrics
    """
    start_time = time.time()

    # Build the prompt (combine system + user)
    full_prompt = f"""{extraction_prompt}

---

Now extract the JSON schema for this query:

USER QUERY: {query}

Respond with ONLY valid JSON, no explanation."""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 2048,
                }
            },
            timeout=timeout
        )

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            return ExtractionResult(
                model=model_name,
                query=query,
                extracted_json=None,
                raw_output="",
                latency_ms=latency_ms,
                success=False,
                error=f"HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        raw_output = data.get("response", "")

        # Try to parse JSON from output
        extracted_json = parse_json_from_output(raw_output)

        return ExtractionResult(
            model=model_name,
            query=query,
            extracted_json=extracted_json,
            raw_output=raw_output,
            latency_ms=latency_ms,
            success=extracted_json is not None,
            error=None if extracted_json else "Failed to parse JSON from output"
        )

    except requests.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return ExtractionResult(
            model=model_name,
            query=query,
            extracted_json=None,
            raw_output="",
            latency_ms=latency_ms,
            success=False,
            error=f"Timeout after {timeout}s"
        )
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return ExtractionResult(
            model=model_name,
            query=query,
            extracted_json=None,
            raw_output="",
            latency_ms=latency_ms,
            success=False,
            error=str(e)
        )


def parse_json_from_output(raw_output: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from model output.

    Handles various formats:
    - Pure JSON
    - JSON wrapped in ```json ... ```
    - JSON with surrounding text
    """
    output = raw_output.strip()

    # Try direct parse first
    try:
        return json.loads(output)
    except:
        pass

    # Try extracting from markdown code block
    if "```json" in output:
        try:
            start = output.find("```json") + 7
            end = output.find("```", start)
            if end > start:
                json_str = output[start:end].strip()
                return json.loads(json_str)
        except:
            pass

    # Try extracting from generic code block
    if "```" in output:
        try:
            start = output.find("```") + 3
            # Skip language identifier if present
            if output[start:start+10].strip().startswith(("{", "[")):
                pass
            else:
                newline_pos = output.find("\n", start)
                if newline_pos > start:
                    start = newline_pos + 1
            end = output.find("```", start)
            if end > start:
                json_str = output[start:end].strip()
                return json.loads(json_str)
        except:
            pass

    # Try finding JSON object boundaries
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = output[start:end]
            return json.loads(json_str)
    except:
        pass

    return None


# ============================================================================
# LOCAL MODEL EXTRACTOR CLASS (mirrors GPTExtractor interface)
# ============================================================================

class LocalModelExtractor:
    """
    Extractor using local models via Ollama.

    Mirrors the GPTExtractor interface for easy swapping.

    Usage:
        extractor = LocalModelExtractor(model="nuextract")
        extractor.initialize()
        result = extractor.extract("need a plumber in bangalore")
    """

    def __init__(self, model: str = "nuextract"):
        """
        Initialize with a specific model.

        Args:
            model: Model key from SUPPORTED_MODELS or direct Ollama model name
        """
        self.model_key = model
        self.model_name = SUPPORTED_MODELS.get(model, model)
        self.extraction_prompt: Optional[str] = None
        self.initialized: bool = False

    def initialize(self, prompt_path: Optional[str] = None) -> bool:
        """
        Initialize the extractor (check Ollama + load prompt).

        Args:
            prompt_path: Path to extraction prompt (optional)

        Returns:
            True if initialization successful
        """
        # Check Ollama
        if not check_ollama_status():
            print("[ERROR] Ollama is not running. Start with: ollama serve")
            return False

        print("[OK] Ollama is running")

        # Check if model is available
        available = list_available_models()
        if self.model_name not in available:
            print(f"[WARN] Model {self.model_name} not found. Available: {available}")
            print(f"[INFO] Attempting to pull {self.model_name}...")
            if not pull_model(self.model_name):
                print(f"[ERROR] Failed to pull model {self.model_name}")
                return False

        print(f"[OK] Model {self.model_name} available")

        # Load prompt
        self.extraction_prompt = load_extraction_prompt(prompt_path)
        if not self.extraction_prompt:
            return False

        self.initialized = True
        print(f"[OK] LocalModelExtractor initialized with {self.model_name}")
        return True

    def extract(self, query: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Extract structured schema from query.

        Args:
            query: Natural language query
            timeout: Request timeout in seconds

        Returns:
            Structured schema dictionary

        Raises:
            RuntimeError: If extraction fails
        """
        if not self.initialized:
            raise RuntimeError("Extractor not initialized. Call initialize() first.")

        result = extract_with_local_model(
            query=query,
            model_name=self.model_name,
            extraction_prompt=self.extraction_prompt,
            timeout=timeout
        )

        if not result.success:
            raise RuntimeError(f"Extraction failed: {result.error}")

        return result.extracted_json

    def extract_with_metrics(self, query: str, timeout: int = 120) -> ExtractionResult:
        """
        Extract with full metrics (latency, raw output, etc.).

        Args:
            query: Natural language query
            timeout: Request timeout in seconds

        Returns:
            ExtractionResult with all metrics
        """
        if not self.initialized:
            raise RuntimeError("Extractor not initialized. Call initialize() first.")

        return extract_with_local_model(
            query=query,
            model_name=self.model_name,
            extraction_prompt=self.extraction_prompt,
            timeout=timeout
        )


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("LOCAL MODEL EXTRACTOR TEST")
    print("=" * 60)

    # Check Ollama
    if not check_ollama_status():
        print("\n[ERROR] Ollama is not running!")
        print("Start Ollama with: ollama serve")
        sys.exit(1)

    print("\n[OK] Ollama is running")

    # List available models
    models = list_available_models()
    print(f"\nAvailable models: {models}")

    # Test with first available model or nuextract
    test_model = "nuextract" if "nuextract" in models else (models[0] if models else None)

    if not test_model:
        print("\n[ERROR] No models available. Pull a model first:")
        print("  ollama pull nuextract")
        sys.exit(1)

    print(f"\nTesting with model: {test_model}")

    # Initialize extractor
    extractor = LocalModelExtractor(model=test_model)
    if not extractor.initialize():
        print("[ERROR] Failed to initialize extractor")
        sys.exit(1)

    # Test query
    test_query = "Looking to buy a Dell laptop in Bangalore under 50000"
    print(f"\nQuery: {test_query}")

    result = extractor.extract_with_metrics(test_query)

    print(f"\nLatency: {result.latency_ms:.0f}ms")
    print(f"Success: {result.success}")

    if result.success:
        print(f"\nExtracted JSON:")
        print(json.dumps(result.extracted_json, indent=2))
    else:
        print(f"\nError: {result.error}")
        print(f"\nRaw output:\n{result.raw_output[:500]}...")
