"""
Hybrid Extractor: GPT Classification + NuExtract Extraction

Architecture:
  Layer 1: GPT-4o classifies intent/subintent (semantic understanding)
  Layer 2: NuExtract extracts structured data (items, domain, location, constraints)

Benefits:
- GPT handles nuanced classification ("I am a plumber" = provide, not seek)
- NuExtract handles structured extraction (cheaper, faster for detailed schema)
- Reduced GPT API costs (classification is simpler than full extraction)

Uses same prompt: GLOBAL_REFERENCE_CONTEXT.md for NuExtract extraction
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
sys.path.insert(0, project_root)

from openai import OpenAI


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Classification prompt for GPT (minimal tokens)
CLASSIFICATION_PROMPT = """You are a query classifier. Classify the user's query into:

INTENT: "product" (buying/selling physical items) or "service" (seeking/providing services)

SUBINTENT:
- For PRODUCT: "buy" (user wants to purchase) or "sell" (user is selling)
- For SERVICE: "seek" (user needs a service provider) or "provide" (user offers their services)

EXAMPLES:
- "I want to buy a laptop" → product/buy
- "Selling my car" → product/sell
- "Need a plumber" → service/seek
- "I am a plumber, available for work" → service/provide
- "Looking for electrician" → service/seek
- "Offering tutoring services" → service/provide

Respond with ONLY JSON: {"intent": "...", "subintent": "..."}
"""

# Extraction prompt for NuExtract (detailed schema)
EXTRACTION_PROMPT_TEMPLATE = """Extract structured data from the query using this schema:

SCHEMA:
- domain: array of domains (lowercase with &). Choose from:
  Products: "technology & electronics", "food & beverage", "healthcare & wellness", "fashion & apparel", "home & furniture", "automotive & vehicles", "sports & outdoors", "pets & animals", "real estate & property", "agriculture & farming", "jewelry & accessories manufacturing", "beauty & cosmetics"
  Services: "construction & trades", "repair & maintenance services", "education & training", "finance, insurance & legal", "transportation & logistics", "hospitality, travel & accommodation", "personal services", "entertainment & events"

- items: array of item objects, each with:
  - type: string (e.g., "laptop", "plumber", "car")
  - categorical: object with attributes (e.g., {"brand": "dell", "color": "black"})
  - min: object for minimum constraints (e.g., {"price": 40000})
  - max: object for maximum constraints (e.g., {"price": 50000, "quantity": 5})
  - range: object for range constraints (e.g., {"price": [40000, 60000]})

- target_location: object with "name" field (e.g., {"name": "bangalore"})

- location_match_mode: "explicit" (specific location) or "flexible"

QUERY: {query}
INTENT: {intent}
SUBINTENT: {subintent}

Extract and return ONLY valid JSON with: domain, items, target_location, location_match_mode
"""


@dataclass
class HybridResult:
    """Result from hybrid extraction."""
    query: str
    # Classification (GPT)
    intent: Optional[str]
    subintent: Optional[str]
    classification_latency_ms: float
    classification_success: bool
    # Extraction (NuExtract)
    extracted_data: Optional[Dict[str, Any]]
    extraction_latency_ms: float
    extraction_success: bool
    # Combined
    final_json: Optional[Dict[str, Any]]
    total_latency_ms: float
    success: bool
    error: Optional[str] = None


# ============================================================================
# GPT CLASSIFICATION
# ============================================================================

def classify_with_gpt(
    query: str,
    openai_client: OpenAI,
    model: str = "gpt-4o-mini"  # Use mini for classification (cheaper)
) -> Tuple[Optional[str], Optional[str], float, Optional[str]]:
    """
    Classify query intent and subintent using GPT.

    Returns:
        (intent, subintent, latency_ms, error)
    """
    start_time = time.time()

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
            max_tokens=50,
            response_format={"type": "json_object"}
        )

        latency_ms = (time.time() - start_time) * 1000
        output = response.choices[0].message.content
        data = json.loads(output)

        return data.get("intent"), data.get("subintent"), latency_ms, None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, None, latency_ms, str(e)


# ============================================================================
# NUEXTRACT EXTRACTION
# ============================================================================

def extract_with_nuextract(
    query: str,
    intent: str,
    subintent: str,
    model: str = "nuextract:latest",
    timeout: int = 60
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    """
    Extract structured data using NuExtract.

    Returns:
        (extracted_data, latency_ms, error)
    """
    start_time = time.time()

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        query=query,
        intent=intent,
        subintent=subintent
    )

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 800
                }
            },
            timeout=timeout
        )

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            return None, latency_ms, f"HTTP {response.status_code}"

        data = response.json()
        raw_output = data.get("response", "")

        # Parse JSON from output
        extracted = parse_json_from_output(raw_output)

        if extracted is None:
            return None, latency_ms, "Failed to parse JSON"

        return extracted, latency_ms, None

    except requests.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, f"Timeout after {timeout}s"
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, str(e)


def parse_json_from_output(raw_output: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from model output."""
    output = raw_output.strip()

    # Remove end tokens
    if "<|end-output|>" in output:
        output = output.split("<|end-output|>")[0].strip()

    # Try direct parse
    try:
        return json.loads(output)
    except:
        pass

    # Try markdown code block
    if "```json" in output:
        try:
            start = output.find("```json") + 7
            end = output.find("```", start)
            if end > start:
                return json.loads(output[start:end].strip())
        except:
            pass

    # Try finding JSON boundaries
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
    except:
        pass

    return None


# ============================================================================
# HYBRID EXTRACTOR CLASS
# ============================================================================

class HybridExtractor:
    """
    Hybrid extractor using GPT for classification and NuExtract for extraction.

    Usage:
        extractor = HybridExtractor()
        extractor.initialize()
        result = extractor.extract("Looking to buy a Dell laptop in Bangalore under 50000")
    """

    def __init__(
        self,
        classification_model: str = "gpt-4o-mini",
        extraction_model: str = "nuextract:latest"
    ):
        self.classification_model = classification_model
        self.extraction_model = extraction_model
        self.openai_client: Optional[OpenAI] = None
        self.initialized: bool = False

    def initialize(self, api_key: Optional[str] = None) -> bool:
        """Initialize the extractor."""
        # Initialize OpenAI
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            print("[ERROR] OPENAI_API_KEY not set")
            return False

        self.openai_client = OpenAI(api_key=api_key)
        print("[OK] OpenAI client initialized")

        # Check Ollama
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code != 200:
                print("[ERROR] Ollama not responding")
                return False
            print("[OK] Ollama is running")
        except:
            print("[ERROR] Cannot connect to Ollama")
            return False

        # Check NuExtract model
        models = [m["name"] for m in response.json().get("models", [])]
        if self.extraction_model not in models and "nuextract" not in str(models):
            print(f"[WARN] {self.extraction_model} not found. Available: {models}")

        self.initialized = True
        print(f"[OK] HybridExtractor initialized")
        print(f"     Classification: {self.classification_model}")
        print(f"     Extraction: {self.extraction_model}")
        return True

    def extract(self, query: str) -> HybridResult:
        """
        Extract structured data using hybrid approach.

        Args:
            query: Natural language query

        Returns:
            HybridResult with classification and extraction data
        """
        if not self.initialized:
            return HybridResult(
                query=query,
                intent=None, subintent=None,
                classification_latency_ms=0, classification_success=False,
                extracted_data=None,
                extraction_latency_ms=0, extraction_success=False,
                final_json=None,
                total_latency_ms=0, success=False,
                error="Extractor not initialized"
            )

        total_start = time.time()

        # Step 1: GPT Classification
        intent, subintent, class_latency, class_error = classify_with_gpt(
            query=query,
            openai_client=self.openai_client,
            model=self.classification_model
        )

        if class_error:
            return HybridResult(
                query=query,
                intent=None, subintent=None,
                classification_latency_ms=class_latency, classification_success=False,
                extracted_data=None,
                extraction_latency_ms=0, extraction_success=False,
                final_json=None,
                total_latency_ms=(time.time() - total_start) * 1000,
                success=False,
                error=f"Classification failed: {class_error}"
            )

        print(f"  Classification: {intent}/{subintent} ({class_latency:.0f}ms)")

        # Step 2: NuExtract Extraction
        extracted, extract_latency, extract_error = extract_with_nuextract(
            query=query,
            intent=intent,
            subintent=subintent,
            model=self.extraction_model
        )

        total_latency = (time.time() - total_start) * 1000

        if extract_error:
            return HybridResult(
                query=query,
                intent=intent, subintent=subintent,
                classification_latency_ms=class_latency, classification_success=True,
                extracted_data=None,
                extraction_latency_ms=extract_latency, extraction_success=False,
                final_json=None,
                total_latency_ms=total_latency,
                success=False,
                error=f"Extraction failed: {extract_error}"
            )

        print(f"  Extraction: OK ({extract_latency:.0f}ms)")

        # Step 3: Combine results
        final_json = {
            "intent": intent,
            "subintent": subintent,
            **extracted
        }

        return HybridResult(
            query=query,
            intent=intent, subintent=subintent,
            classification_latency_ms=class_latency, classification_success=True,
            extracted_data=extracted,
            extraction_latency_ms=extract_latency, extraction_success=True,
            final_json=final_json,
            total_latency_ms=total_latency,
            success=True
        )


# ============================================================================
# CLI TEST
# ============================================================================

TEST_QUERIES = [
    "Looking to buy a Dell laptop in Bangalore under 50000",
    "I am a plumber in Bangalore, charge 500 per hour",
    "Need electrician for AC repair in Mumbai",
    "Selling iPhone 15 Pro in Delhi for 80000",
]


def run_hybrid_test():
    """Run hybrid extraction test."""
    print("=" * 70)
    print("HYBRID EXTRACTOR TEST")
    print("GPT Classification + NuExtract Extraction")
    print("=" * 70)

    extractor = HybridExtractor()
    if not extractor.initialize():
        print("\n[ERROR] Failed to initialize. Check API key and Ollama.")
        return

    results = []
    for query in TEST_QUERIES:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print("-" * 50)

        result = extractor.extract(query)
        results.append(result)

        if result.success:
            print(f"\nFinal JSON:")
            print(json.dumps(result.final_json, indent=2))
            print(f"\nTotal latency: {result.total_latency_ms:.0f}ms")
            print(f"  - Classification: {result.classification_latency_ms:.0f}ms")
            print(f"  - Extraction: {result.extraction_latency_ms:.0f}ms")
        else:
            print(f"\n[ERROR] {result.error}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.success)
    avg_latency = sum(r.total_latency_ms for r in results if r.success) / max(success_count, 1)

    print(f"Success rate: {success_count}/{len(results)}")
    print(f"Average latency: {avg_latency:.0f}ms")


if __name__ == "__main__":
    run_hybrid_test()
