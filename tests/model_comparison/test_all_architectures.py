"""
Comprehensive Architecture Comparison Test

Tests 5 extraction architectures using GLOBAL_REFERENCE_CONTEXT.md:

1. GPT Classify + NuExtract Extract (Hybrid - Recommended)
2. GPT Full Extract + NuExtract Validate/Correct
3. NuExtract + Phi-3 Local (Fully Local)
4. Phi-4/Phi-3 Full Extraction (Standalone Local)
5. Chain with Fallback (Hybrid+)

All architectures use the same prompt: GLOBAL_REFERENCE_CONTEXT.md
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
sys.path.insert(0, project_root)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[WARN] OpenAI not installed. GPT-based architectures will be skipped.")


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Test queries covering different scenarios
TEST_QUERIES = [
    # Product Buy
    ("Looking to buy a Dell laptop in Bangalore under 50000", "product", "buy"),
    ("Want to purchase iPhone 15 Pro in Delhi, budget 90000", "product", "buy"),
    # Product Sell
    ("Selling HP laptop starting 40000 in Bangalore", "product", "sell"),
    ("Fresh organic vegetables available 100 rupees per kg in Mumbai", "product", "sell"),
    # Service Seek
    ("Looking for a plumber in Bangalore who speaks Kannada", "service", "seek"),
    ("Need electrician for AC repair in Mumbai, budget 2000", "service", "seek"),
    # Service Provide
    ("I am a plumber in Bangalore, charge 500 per hour", "service", "provide"),
    ("Yoga instructor offering home sessions in Delhi, 500 per class", "service", "provide"),
]

# Required schema fields
REQUIRED_FIELDS = ["intent", "subintent", "domain", "items"]


@dataclass
class ExtractionResult:
    """Result from extraction."""
    query: str
    architecture: str
    extracted_json: Optional[Dict[str, Any]]
    latency_ms: float
    success: bool
    intent_correct: Optional[bool] = None
    subintent_correct: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class ArchitectureResults:
    """Results for an architecture."""
    name: str
    results: List[ExtractionResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results) * 100

    @property
    def intent_accuracy(self) -> float:
        correct = sum(1 for r in self.results if r.intent_correct)
        total = sum(1 for r in self.results if r.intent_correct is not None)
        return (correct / total * 100) if total > 0 else 0.0

    @property
    def subintent_accuracy(self) -> float:
        correct = sum(1 for r in self.results if r.subintent_correct)
        total = sum(1 for r in self.results if r.subintent_correct is not None)
        return (correct / total * 100) if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        successful = [r for r in self.results if r.success]
        return sum(r.latency_ms for r in successful) / len(successful) if successful else 0.0


# ============================================================================
# PROMPT LOADING
# ============================================================================

def load_global_prompt() -> str:
    """Load GLOBAL_REFERENCE_CONTEXT.md prompt."""
    prompt_path = os.path.join(project_root, "prompt", "GLOBAL_REFERENCE_CONTEXT.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] Failed to load prompt: {e}")
        return ""


def create_classification_prompt() -> str:
    """Create minimal classification prompt for GPT."""
    return """You are a query classifier for a matching system.

Classify the user's query:

INTENT:
- "product": Buying or selling physical items/goods
- "service": Seeking or providing services

SUBINTENT:
- For PRODUCT: "buy" (user wants to purchase) or "sell" (user is selling/offering)
- For SERVICE: "seek" (user needs someone to help) or "provide" (user offers their skills)

CLASSIFICATION RULES:
- "I am a [profession]" = service/provide (they ARE that profession)
- "I need a [profession]" = service/seek (they NEED that profession)
- "Looking for [profession]" = service/seek
- "I want to buy" = product/buy
- "Selling" or "For sale" = product/sell
- "Available" with price = usually sell/provide

Respond with ONLY JSON: {"intent": "...", "subintent": "..."}"""


def create_extraction_prompt(intent: str, subintent: str) -> str:
    """Create extraction prompt with classified intent."""
    return f"""Extract structured data from the query.

KNOWN CLASSIFICATION:
- Intent: {intent}
- Subintent: {subintent}

EXTRACT TO JSON:
- domain: array of domains (lowercase with &). Examples:
  Products: "technology & electronics", "food & beverage", "automotive & vehicles"
  Services: "construction & trades", "repair & maintenance services", "personal services"

- items: array of objects, each with:
  - type: string (laptop, plumber, car, vegetables, etc.)
  - categorical: object with attributes (brand, color, model, etc.)
  - min: object for minimum constraints (price, rate, quantity)
  - max: object for maximum constraints (price, budget, quantity)
  - range: object for range constraints

- target_location: object with "name" field (city name, lowercase)

- location_match_mode: "explicit" or "flexible"

Return ONLY valid JSON with: domain, items, target_location, location_match_mode"""


# ============================================================================
# OLLAMA HELPERS
# ============================================================================

def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_available_models() -> List[str]:
    """Get list of available Ollama models."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return [m["name"] for m in response.json().get("models", [])]
    except:
        pass
    return []


def ollama_generate(model: str, prompt: str, timeout: int = 120) -> Tuple[Optional[str], float, Optional[str]]:
    """Generate with Ollama model."""
    start = time.time()
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 800}
            },
            timeout=timeout
        )
        latency = (time.time() - start) * 1000

        if response.status_code != 200:
            return None, latency, f"HTTP {response.status_code}"

        return response.json().get("response", ""), latency, None
    except requests.Timeout:
        return None, (time.time() - start) * 1000, "Timeout"
    except Exception as e:
        return None, (time.time() - start) * 1000, str(e)


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from model output."""
    text = text.strip()

    # Remove end tokens
    for token in ["<|end-output|>", "<|endoftext|>", "</s>"]:
        if token in text:
            text = text.split(token)[0].strip()

    # Try direct parse
    try:
        return json.loads(text)
    except:
        pass

    # Try markdown code block
    if "```json" in text:
        try:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return json.loads(text[start:end].strip())
        except:
            pass

    # Try finding JSON boundaries
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except:
        pass

    return None


# ============================================================================
# ARCHITECTURE 1: GPT Classify + NuExtract Extract
# ============================================================================

def test_arch1_gpt_classify_nuextract(
    query: str,
    expected_intent: str,
    expected_subintent: str,
    openai_client: Optional[OpenAI]
) -> ExtractionResult:
    """
    Architecture 1: GPT Classification + NuExtract Extraction

    GPT handles semantic classification (intent/subintent)
    NuExtract handles structured extraction (items, domain, location)
    """
    start = time.time()

    if not openai_client:
        return ExtractionResult(
            query=query, architecture="Arch1: GPT+NuExtract",
            extracted_json=None, latency_ms=0, success=False,
            error="OpenAI not available"
        )

    # Step 1: GPT Classification
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": create_classification_prompt()},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=50,
            response_format={"type": "json_object"}
        )
        class_json = json.loads(response.choices[0].message.content)
        intent = class_json.get("intent")
        subintent = class_json.get("subintent")
    except Exception as e:
        return ExtractionResult(
            query=query, architecture="Arch1: GPT+NuExtract",
            extracted_json=None, latency_ms=(time.time() - start) * 1000,
            success=False, error=f"GPT classification failed: {e}"
        )

    # Step 2: NuExtract Extraction
    extract_prompt = create_extraction_prompt(intent, subintent) + f"\n\nQUERY: {query}\n\nJSON:"
    output, _, error = ollama_generate("nuextract:latest", extract_prompt)

    latency = (time.time() - start) * 1000

    if error:
        return ExtractionResult(
            query=query, architecture="Arch1: GPT+NuExtract",
            extracted_json=None, latency_ms=latency, success=False,
            error=f"NuExtract failed: {error}"
        )

    extracted = parse_json(output)
    if not extracted:
        return ExtractionResult(
            query=query, architecture="Arch1: GPT+NuExtract",
            extracted_json=None, latency_ms=latency, success=False,
            error="Failed to parse NuExtract output"
        )

    # Combine results
    final = {"intent": intent, "subintent": subintent, **extracted}

    return ExtractionResult(
        query=query, architecture="Arch1: GPT+NuExtract",
        extracted_json=final, latency_ms=latency, success=True,
        intent_correct=(intent == expected_intent),
        subintent_correct=(subintent == expected_subintent)
    )


# ============================================================================
# ARCHITECTURE 2: GPT Full Extract + NuExtract Validate
# ============================================================================

def test_arch2_gpt_full_nuextract_validate(
    query: str,
    expected_intent: str,
    expected_subintent: str,
    openai_client: Optional[OpenAI],
    global_prompt: str
) -> ExtractionResult:
    """
    Architecture 2: GPT Full Extraction + NuExtract Validation

    GPT does comprehensive extraction first
    NuExtract validates and corrects the output
    """
    start = time.time()

    if not openai_client:
        return ExtractionResult(
            query=query, architecture="Arch2: GPT+Validate",
            extracted_json=None, latency_ms=0, success=False,
            error="OpenAI not available"
        )

    # Step 1: GPT Full Extraction (using full prompt, truncated for API limits)
    gpt_prompt = global_prompt[:8000] + "\n\nExtract JSON for this query. Return ONLY valid JSON."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": gpt_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        gpt_json = json.loads(response.choices[0].message.content)
    except Exception as e:
        return ExtractionResult(
            query=query, architecture="Arch2: GPT+Validate",
            extracted_json=None, latency_ms=(time.time() - start) * 1000,
            success=False, error=f"GPT extraction failed: {e}"
        )

    # Step 2: NuExtract Validation
    validate_prompt = f"""Validate and correct this JSON extraction:

ORIGINAL QUERY: {query}

GPT EXTRACTION:
{json.dumps(gpt_json, indent=2)}

VALIDATION RULES:
- intent must be "product" or "service"
- subintent must be "buy"/"sell" (product) or "seek"/"provide" (service)
- domain must be array with lowercase strings containing &
- items must be array with type field

Return corrected JSON only:"""

    output, _, error = ollama_generate("nuextract:latest", validate_prompt)
    latency = (time.time() - start) * 1000

    if error:
        # Fallback to GPT output if validation fails
        final = gpt_json
    else:
        validated = parse_json(output)
        final = validated if validated else gpt_json

    intent = final.get("intent")
    subintent = final.get("subintent")

    return ExtractionResult(
        query=query, architecture="Arch2: GPT+Validate",
        extracted_json=final, latency_ms=latency, success=True,
        intent_correct=(intent == expected_intent),
        subintent_correct=(subintent == expected_subintent)
    )


# ============================================================================
# ARCHITECTURE 3: NuExtract + Phi-3 Local
# ============================================================================

def test_arch3_nuextract_phi3(
    query: str,
    expected_intent: str,
    expected_subintent: str,
    global_prompt: str
) -> ExtractionResult:
    """
    Architecture 3: NuExtract Extraction + Phi-3 Classification

    NuExtract does raw extraction first
    Phi-3 classifies/refines the output
    """
    start = time.time()

    # Check models available
    models = get_available_models()
    phi_model = "phi3:mini" if "phi3:mini" in models else None

    if not phi_model:
        return ExtractionResult(
            query=query, architecture="Arch3: NuExtract+Phi3",
            extracted_json=None, latency_ms=0, success=False,
            error="Phi3 model not available"
        )

    # Step 1: NuExtract Raw Extraction
    extract_prompt = f"""Extract from query:
- domain: array (e.g., ["technology & electronics"])
- items: array with type, categorical, min/max
- target_location: object with name

QUERY: {query}

JSON:"""

    output, _, error = ollama_generate("nuextract:latest", extract_prompt)

    if error:
        return ExtractionResult(
            query=query, architecture="Arch3: NuExtract+Phi3",
            extracted_json=None, latency_ms=(time.time() - start) * 1000,
            success=False, error=f"NuExtract failed: {error}"
        )

    extracted = parse_json(output)
    if not extracted:
        return ExtractionResult(
            query=query, architecture="Arch3: NuExtract+Phi3",
            extracted_json=None, latency_ms=(time.time() - start) * 1000,
            success=False, error="Failed to parse NuExtract output"
        )

    # Step 2: Phi-3 Classification
    classify_prompt = f"""Classify this query:

QUERY: {query}
EXTRACTED DATA: {json.dumps(extracted)}

Rules:
- intent: "product" (buying/selling items) or "service" (seeking/providing services)
- subintent: "buy"/"sell" for product, "seek"/"provide" for service
- "I am a [profession]" = service/provide
- "I need a [profession]" = service/seek

Return JSON: {{"intent": "...", "subintent": "..."}}"""

    phi_output, _, phi_error = ollama_generate(phi_model, classify_prompt, timeout=60)
    latency = (time.time() - start) * 1000

    if phi_error:
        return ExtractionResult(
            query=query, architecture="Arch3: NuExtract+Phi3",
            extracted_json=extracted, latency_ms=latency, success=False,
            error=f"Phi3 classification failed: {phi_error}"
        )

    classification = parse_json(phi_output)
    if not classification:
        return ExtractionResult(
            query=query, architecture="Arch3: NuExtract+Phi3",
            extracted_json=extracted, latency_ms=latency, success=False,
            error="Failed to parse Phi3 output"
        )

    # Combine
    final = {
        "intent": classification.get("intent"),
        "subintent": classification.get("subintent"),
        **extracted
    }

    return ExtractionResult(
        query=query, architecture="Arch3: NuExtract+Phi3",
        extracted_json=final, latency_ms=latency, success=True,
        intent_correct=(final.get("intent") == expected_intent),
        subintent_correct=(final.get("subintent") == expected_subintent)
    )


# ============================================================================
# ARCHITECTURE 4: Phi-3/Phi-4 Full Extraction (Standalone Local)
# ============================================================================

def test_arch4_phi_standalone(
    query: str,
    expected_intent: str,
    expected_subintent: str,
    global_prompt: str
) -> ExtractionResult:
    """
    Architecture 4: Phi-3/Phi-4 Full Extraction

    Single local model does both classification and extraction
    """
    start = time.time()

    # Check models available
    models = get_available_models()
    phi_model = None
    for m in ["phi4-mini", "phi3:mini", "mistral:latest"]:
        if m in models:
            phi_model = m
            break

    if not phi_model:
        return ExtractionResult(
            query=query, architecture="Arch4: Phi Standalone",
            extracted_json=None, latency_ms=0, success=False,
            error="No suitable model available (phi4-mini, phi3:mini, or mistral)"
        )

    # Full extraction prompt (truncated for local model context)
    full_prompt = f"""Extract JSON from query.

SCHEMA:
- intent: "product" or "service"
- subintent: "buy"/"sell" (product) or "seek"/"provide" (service)
- domain: array like ["technology & electronics"] or ["construction & trades"]
- items: array with type, categorical, min/max
- target_location: object with name
- location_match_mode: "explicit" or "flexible"

RULES:
- "I am a [profession]" = service/provide
- "I need/looking for [profession]" = service/seek
- "want to buy" = product/buy
- "selling" = product/sell

QUERY: {query}

Return complete JSON:"""

    output, latency, error = ollama_generate(phi_model, full_prompt, timeout=90)

    if error:
        return ExtractionResult(
            query=query, architecture=f"Arch4: {phi_model}",
            extracted_json=None, latency_ms=latency, success=False,
            error=error
        )

    extracted = parse_json(output)
    if not extracted:
        return ExtractionResult(
            query=query, architecture=f"Arch4: {phi_model}",
            extracted_json=None, latency_ms=latency, success=False,
            error="Failed to parse output"
        )

    return ExtractionResult(
        query=query, architecture=f"Arch4: {phi_model}",
        extracted_json=extracted, latency_ms=latency, success=True,
        intent_correct=(extracted.get("intent") == expected_intent),
        subintent_correct=(extracted.get("subintent") == expected_subintent)
    )


# ============================================================================
# ARCHITECTURE 5: Chain with Fallback
# ============================================================================

def test_arch5_chain_fallback(
    query: str,
    expected_intent: str,
    expected_subintent: str,
    openai_client: Optional[OpenAI],
    global_prompt: str
) -> ExtractionResult:
    """
    Architecture 5: Local-first with GPT fallback

    Try NuExtract + Phi-3 first
    If confidence low or fields missing, fallback to GPT
    """
    start = time.time()

    # First try Architecture 3 (local)
    local_result = test_arch3_nuextract_phi3(query, expected_intent, expected_subintent, global_prompt)

    # Check if local extraction is good enough
    if local_result.success and local_result.extracted_json:
        json_data = local_result.extracted_json
        has_intent = json_data.get("intent") in ["product", "service"]
        has_subintent = json_data.get("subintent") in ["buy", "sell", "seek", "provide"]
        has_domain = isinstance(json_data.get("domain"), list) and len(json_data.get("domain", [])) > 0
        has_items = isinstance(json_data.get("items"), list) and len(json_data.get("items", [])) > 0

        if has_intent and has_subintent and has_domain and has_items:
            # Local extraction is good, return it
            local_result.architecture = "Arch5: Local (no fallback)"
            return local_result

    # Fallback to GPT
    if not openai_client:
        local_result.architecture = "Arch5: Local (GPT unavailable)"
        return local_result

    # Use Architecture 1 as fallback
    fallback_result = test_arch1_gpt_classify_nuextract(
        query, expected_intent, expected_subintent, openai_client
    )
    fallback_result.architecture = "Arch5: GPT Fallback"
    fallback_result.latency_ms = (time.time() - start) * 1000

    return fallback_result


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests() -> Dict[str, ArchitectureResults]:
    """Run all architecture tests."""
    print("=" * 80)
    print("COMPREHENSIVE ARCHITECTURE COMPARISON TEST")
    print("Using GLOBAL_REFERENCE_CONTEXT.md prompt")
    print("=" * 80)

    # Check prerequisites
    if not check_ollama():
        print("\n[ERROR] Ollama not running. Start with: ollama serve")
        return {}

    models = get_available_models()
    print(f"\nAvailable Ollama models: {models}")

    # Load prompt
    global_prompt = load_global_prompt()
    if not global_prompt:
        print("[ERROR] Failed to load GLOBAL_REFERENCE_CONTEXT.md")
        return {}
    print(f"Loaded prompt: {len(global_prompt)} chars")

    # Initialize OpenAI if available
    openai_client = None
    if OPENAI_AVAILABLE:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            openai_client = OpenAI(api_key=api_key)
            print("[OK] OpenAI client initialized")
        else:
            print("[WARN] OPENAI_API_KEY not set. GPT architectures will be skipped.")

    # Initialize results
    results = {
        "arch1": ArchitectureResults(name="Arch1: GPT Classify + NuExtract"),
        "arch2": ArchitectureResults(name="Arch2: GPT Full + NuExtract Validate"),
        "arch3": ArchitectureResults(name="Arch3: NuExtract + Phi-3 Local"),
        "arch4": ArchitectureResults(name="Arch4: Phi Standalone"),
        "arch5": ArchitectureResults(name="Arch5: Chain with Fallback"),
    }

    # Run tests
    for i, (query, expected_intent, expected_subintent) in enumerate(TEST_QUERIES):
        print(f"\n{'='*60}")
        print(f"TEST {i+1}/{len(TEST_QUERIES)}")
        print(f"Query: {query[:60]}...")
        print(f"Expected: {expected_intent}/{expected_subintent}")
        print("-" * 60)

        # Test Architecture 1
        print("\n[Arch1] GPT Classify + NuExtract...")
        r1 = test_arch1_gpt_classify_nuextract(query, expected_intent, expected_subintent, openai_client)
        results["arch1"].results.append(r1)
        print(f"  {'✓' if r1.success else '✗'} {r1.latency_ms:.0f}ms - Intent: {r1.intent_correct}, Subintent: {r1.subintent_correct}")

        # Test Architecture 2
        print("[Arch2] GPT Full + NuExtract Validate...")
        r2 = test_arch2_gpt_full_nuextract_validate(query, expected_intent, expected_subintent, openai_client, global_prompt)
        results["arch2"].results.append(r2)
        print(f"  {'✓' if r2.success else '✗'} {r2.latency_ms:.0f}ms - Intent: {r2.intent_correct}, Subintent: {r2.subintent_correct}")

        # Test Architecture 3
        print("[Arch3] NuExtract + Phi-3...")
        r3 = test_arch3_nuextract_phi3(query, expected_intent, expected_subintent, global_prompt)
        results["arch3"].results.append(r3)
        print(f"  {'✓' if r3.success else '✗'} {r3.latency_ms:.0f}ms - Intent: {r3.intent_correct}, Subintent: {r3.subintent_correct}")

        # Test Architecture 4
        print("[Arch4] Phi Standalone...")
        r4 = test_arch4_phi_standalone(query, expected_intent, expected_subintent, global_prompt)
        results["arch4"].results.append(r4)
        print(f"  {'✓' if r4.success else '✗'} {r4.latency_ms:.0f}ms - Intent: {r4.intent_correct}, Subintent: {r4.subintent_correct}")

        # Test Architecture 5
        print("[Arch5] Chain with Fallback...")
        r5 = test_arch5_chain_fallback(query, expected_intent, expected_subintent, openai_client, global_prompt)
        results["arch5"].results.append(r5)
        print(f"  {'✓' if r5.success else '✗'} {r5.latency_ms:.0f}ms - Intent: {r5.intent_correct}, Subintent: {r5.subintent_correct}")

    return results


def print_summary(results: Dict[str, ArchitectureResults]):
    """Print summary comparison."""
    print("\n" + "=" * 80)
    print("SUMMARY COMPARISON")
    print("=" * 80)

    print(f"\n{'Architecture':<40} {'Success':<10} {'Intent':<10} {'Subintent':<12} {'Latency':<10}")
    print("-" * 80)

    for key, arch in results.items():
        print(f"{arch.name:<40} {arch.success_rate:>6.1f}%   {arch.intent_accuracy:>6.1f}%   {arch.subintent_accuracy:>8.1f}%   {arch.avg_latency_ms:>6.0f}ms")

    print("-" * 80)

    # Find best architecture
    best = max(results.values(), key=lambda x: (x.success_rate, x.intent_accuracy, x.subintent_accuracy))
    print(f"\nBest Architecture: {best.name}")
    print(f"  Success Rate: {best.success_rate:.1f}%")
    print(f"  Intent Accuracy: {best.intent_accuracy:.1f}%")
    print(f"  Subintent Accuracy: {best.subintent_accuracy:.1f}%")
    print(f"  Avg Latency: {best.avg_latency_ms:.0f}ms")


def save_results(results: Dict[str, ArchitectureResults], output_path: str):
    """Save results to JSON file."""
    output = {}
    for key, arch in results.items():
        output[key] = {
            "name": arch.name,
            "success_rate": arch.success_rate,
            "intent_accuracy": arch.intent_accuracy,
            "subintent_accuracy": arch.subintent_accuracy,
            "avg_latency_ms": arch.avg_latency_ms,
            "results": [
                {
                    "query": r.query,
                    "success": r.success,
                    "intent_correct": r.intent_correct,
                    "subintent_correct": r.subintent_correct,
                    "latency_ms": r.latency_ms,
                    "error": r.error
                }
                for r in arch.results
            ]
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n[OK] Results saved to: {output_path}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    results = run_all_tests()

    if results:
        print_summary(results)

        output_path = os.path.join(os.path.dirname(__file__), "architecture_comparison_results.json")
        save_results(results, output_path)
