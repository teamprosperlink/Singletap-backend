"""
Two-Layer Architecture Test: GPT + Local Model validation/normalization.

Architecture:
  Layer 1: GPT-4o extraction (natural language -> JSON)
  Layer 2: Local model validation/normalization (fix schema issues)

The local model (NuExtract/Qwen/etc.) acts as a "second layer" to:
- Validate GPT's JSON structure
- Fix schema inconsistencies
- Normalize field names/values
- Catch extraction errors before canonicalization

Both layers use the same prompt: GLOBAL_REFERENCE_CONTEXT.md
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
sys.path.insert(0, project_root)

from tests.model_comparison.local_model_extractor import (
    LocalModelExtractor,
    ExtractionResult,
    check_ollama_status,
    list_available_models,
    load_extraction_prompt,
    OLLAMA_BASE_URL
)
from src.core.extraction.gpt_extractor import GPTExtractor
import requests


# ============================================================================
# CONFIGURATION
# ============================================================================

# Target schema fields that must be present
REQUIRED_SCHEMA_FIELDS = {
    "intent": ["product", "service"],
    "subintent": ["buy", "sell", "seek", "provide"],
    "domain": list,  # Must be a list
    "items": list,   # Must be a list
}

# Validation prompt for Layer 2
VALIDATION_PROMPT_TEMPLATE = """You are a JSON schema validator and normalizer.

Your task is to validate and fix the following JSON extraction to match the required schema.

REQUIRED SCHEMA RULES:
1. "intent" must be one of: "product", "service"
2. "subintent" must be one of: "buy", "sell" (for product) or "seek", "provide" (for service)
3. "domain" must be a list of strings (e.g., ["technology & electronics"])
4. "items" must be a list of item objects
5. Each item must have at least a "type" field

ORIGINAL QUERY: {query}

GPT EXTRACTION (may have errors):
{gpt_json}

INSTRUCTIONS:
- If the JSON is valid and complete, return it unchanged
- If there are missing fields, add them with sensible defaults based on the query
- If there are incorrect field types, fix them
- If domain is missing or wrong, infer from the query context
- Ensure all required fields are present

Respond with ONLY the corrected JSON, no explanation.
"""


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TwoLayerResult:
    """Result of two-layer extraction."""
    query: str
    gpt_json: Optional[Dict[str, Any]]
    gpt_latency_ms: float
    gpt_success: bool
    validated_json: Optional[Dict[str, Any]]
    validation_latency_ms: float
    validation_success: bool
    total_latency_ms: float
    changes_made: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ArchitectureResult:
    """Results for an architecture across all queries."""
    architecture_name: str
    total_queries: int = 0
    successful: int = 0
    total_latency_ms: float = 0.0
    results: List[TwoLayerResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.successful / self.total_queries * 100

    @property
    def avg_latency_ms(self) -> float:
        if self.successful == 0:
            return 0.0
        return self.total_latency_ms / self.successful


# ============================================================================
# VALIDATION LAYER
# ============================================================================

def validate_schema(extracted: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate if schema meets requirements.

    Returns:
        (is_valid, list_of_issues)
    """
    issues = []

    # Check intent
    if "intent" not in extracted:
        issues.append("Missing 'intent' field")
    elif extracted["intent"] not in ["product", "service"]:
        issues.append(f"Invalid intent: {extracted['intent']}")

    # Check subintent
    if "subintent" not in extracted:
        issues.append("Missing 'subintent' field")
    elif extracted["subintent"] not in ["buy", "sell", "seek", "provide"]:
        issues.append(f"Invalid subintent: {extracted['subintent']}")

    # Check domain
    if "domain" not in extracted:
        issues.append("Missing 'domain' field")
    elif not isinstance(extracted["domain"], list):
        issues.append(f"'domain' should be list, got {type(extracted['domain']).__name__}")

    # Check items
    if "items" not in extracted:
        issues.append("Missing 'items' field")
    elif not isinstance(extracted["items"], list):
        issues.append(f"'items' should be list, got {type(extracted['items']).__name__}")

    return len(issues) == 0, issues


def validate_with_local_model(
    query: str,
    gpt_json: Dict[str, Any],
    model_name: str,
    extraction_prompt: str,
    timeout: int = 60
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    """
    Use local model to validate and fix GPT extraction.

    Args:
        query: Original query
        gpt_json: GPT's extraction output
        model_name: Ollama model name
        extraction_prompt: Base prompt (GLOBAL_REFERENCE_CONTEXT.md)
        timeout: Request timeout

    Returns:
        (validated_json, latency_ms, error)
    """
    start_time = time.time()

    # Build validation prompt
    validation_prompt = f"""{extraction_prompt}

---

VALIDATION TASK:

Original query: {query}

GPT extracted this JSON:
```json
{json.dumps(gpt_json, indent=2)}
```

Your task:
1. Verify this JSON matches the schema defined above
2. Fix any errors or missing fields
3. Return the corrected JSON

Respond with ONLY valid JSON, no explanation.
"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": validation_prompt,
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
            return None, latency_ms, f"HTTP {response.status_code}"

        data = response.json()
        raw_output = data.get("response", "")

        # Parse JSON from output
        validated_json = parse_json_from_output(raw_output)

        if validated_json is None:
            return None, latency_ms, "Failed to parse JSON from validation output"

        return validated_json, latency_ms, None

    except requests.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, f"Timeout after {timeout}s"
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return None, latency_ms, str(e)


def parse_json_from_output(raw_output: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from model output (reused from local_model_extractor)."""
    output = raw_output.strip()

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


def detect_changes(original: Dict[str, Any], validated: Dict[str, Any]) -> List[str]:
    """Detect what changes the validation layer made."""
    changes = []

    # Check top-level fields
    for key in set(list(original.keys()) + list(validated.keys())):
        if key not in original:
            changes.append(f"Added field: {key}")
        elif key not in validated:
            changes.append(f"Removed field: {key}")
        elif original[key] != validated[key]:
            changes.append(f"Modified field: {key}")

    return changes


# ============================================================================
# ARCHITECTURE RUNNERS
# ============================================================================

def run_single_layer_gpt(queries: List[str]) -> ArchitectureResult:
    """
    Architecture A: GPT-only extraction.
    """
    print("\n" + "=" * 60)
    print("ARCHITECTURE A: GPT-4o ONLY")
    print("=" * 60)

    result = ArchitectureResult(architecture_name="GPT-only")

    extractor = GPTExtractor()
    if not extractor.initialize():
        print("[ERROR] Failed to initialize GPT extractor")
        return result

    for query in queries:
        result.total_queries += 1
        print(f"\n[{result.total_queries}/{len(queries)}] {query[:50]}...")

        start_time = time.time()
        try:
            extracted = extractor.extract(query)
            latency_ms = (time.time() - start_time) * 1000

            is_valid, issues = validate_schema(extracted)

            layer_result = TwoLayerResult(
                query=query,
                gpt_json=extracted,
                gpt_latency_ms=latency_ms,
                gpt_success=True,
                validated_json=extracted,  # No validation layer
                validation_latency_ms=0,
                validation_success=is_valid,
                total_latency_ms=latency_ms,
                changes_made=[],
                error=None if is_valid else f"Schema issues: {issues}"
            )

            if is_valid:
                result.successful += 1
                result.total_latency_ms += latency_ms
                print(f"  ✓ Valid ({latency_ms:.0f}ms)")
            else:
                print(f"  ⚠ Schema issues: {issues}")

            result.results.append(layer_result)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            result.results.append(TwoLayerResult(
                query=query,
                gpt_json=None,
                gpt_latency_ms=latency_ms,
                gpt_success=False,
                validated_json=None,
                validation_latency_ms=0,
                validation_success=False,
                total_latency_ms=latency_ms,
                error=str(e)
            ))
            print(f"  ✗ Failed: {e}")

    return result


def run_two_layer_architecture(
    queries: List[str],
    validation_model: str = "nuextract"
) -> ArchitectureResult:
    """
    Architecture B: GPT + Local Model validation.
    """
    print("\n" + "=" * 60)
    print(f"ARCHITECTURE B: GPT-4o + {validation_model} VALIDATION")
    print("=" * 60)

    result = ArchitectureResult(architecture_name=f"GPT + {validation_model}")

    # Initialize GPT
    gpt_extractor = GPTExtractor()
    if not gpt_extractor.initialize():
        print("[ERROR] Failed to initialize GPT extractor")
        return result

    # Check Ollama
    if not check_ollama_status():
        print("[ERROR] Ollama not running")
        return result

    # Load prompt for validation
    extraction_prompt = load_extraction_prompt()
    if not extraction_prompt:
        print("[ERROR] Failed to load extraction prompt")
        return result

    # Resolve model name
    from tests.model_comparison.local_model_extractor import SUPPORTED_MODELS
    model_name = SUPPORTED_MODELS.get(validation_model, validation_model)

    for query in queries:
        result.total_queries += 1
        print(f"\n[{result.total_queries}/{len(queries)}] {query[:50]}...")

        total_start = time.time()

        # Layer 1: GPT extraction
        gpt_start = time.time()
        try:
            gpt_json = gpt_extractor.extract(query)
            gpt_latency = (time.time() - gpt_start) * 1000
            gpt_success = True
            print(f"  Layer 1 (GPT): ✓ ({gpt_latency:.0f}ms)")
        except Exception as e:
            gpt_latency = (time.time() - gpt_start) * 1000
            gpt_json = None
            gpt_success = False
            print(f"  Layer 1 (GPT): ✗ ({e})")

            result.results.append(TwoLayerResult(
                query=query,
                gpt_json=None,
                gpt_latency_ms=gpt_latency,
                gpt_success=False,
                validated_json=None,
                validation_latency_ms=0,
                validation_success=False,
                total_latency_ms=gpt_latency,
                error=str(e)
            ))
            continue

        # Check if validation needed
        is_valid, issues = validate_schema(gpt_json)

        if is_valid:
            # Schema already valid, skip validation layer
            total_latency = (time.time() - total_start) * 1000
            print(f"  Layer 2 (validation): skipped (schema valid)")

            result.successful += 1
            result.total_latency_ms += total_latency

            result.results.append(TwoLayerResult(
                query=query,
                gpt_json=gpt_json,
                gpt_latency_ms=gpt_latency,
                gpt_success=True,
                validated_json=gpt_json,
                validation_latency_ms=0,
                validation_success=True,
                total_latency_ms=total_latency,
                changes_made=[]
            ))
            continue

        # Layer 2: Local model validation
        print(f"  Schema issues: {issues}")
        validated_json, validation_latency, validation_error = validate_with_local_model(
            query=query,
            gpt_json=gpt_json,
            model_name=model_name,
            extraction_prompt=extraction_prompt
        )

        total_latency = (time.time() - total_start) * 1000

        if validation_error:
            print(f"  Layer 2 ({validation_model}): ✗ ({validation_error})")
            result.results.append(TwoLayerResult(
                query=query,
                gpt_json=gpt_json,
                gpt_latency_ms=gpt_latency,
                gpt_success=True,
                validated_json=None,
                validation_latency_ms=validation_latency,
                validation_success=False,
                total_latency_ms=total_latency,
                error=validation_error
            ))
            continue

        # Check if validation fixed the issues
        is_valid_after, remaining_issues = validate_schema(validated_json)
        changes = detect_changes(gpt_json, validated_json)

        if is_valid_after:
            result.successful += 1
            result.total_latency_ms += total_latency
            print(f"  Layer 2 ({validation_model}): ✓ fixed ({validation_latency:.0f}ms)")
            if changes:
                print(f"    Changes: {changes}")
        else:
            print(f"  Layer 2 ({validation_model}): ⚠ still invalid ({remaining_issues})")

        result.results.append(TwoLayerResult(
            query=query,
            gpt_json=gpt_json,
            gpt_latency_ms=gpt_latency,
            gpt_success=True,
            validated_json=validated_json,
            validation_latency_ms=validation_latency,
            validation_success=is_valid_after,
            total_latency_ms=total_latency,
            changes_made=changes
        ))

    return result


# ============================================================================
# REPORT
# ============================================================================

def print_architecture_comparison(arch_a: ArchitectureResult, arch_b: ArchitectureResult):
    """Print comparison between architectures."""
    print("\n" + "=" * 80)
    print("ARCHITECTURE COMPARISON")
    print("=" * 80)

    print(f"\n{'Architecture':<30} {'Success Rate':<15} {'Avg Latency':<15}")
    print("-" * 60)

    print(f"{arch_a.architecture_name:<30} {arch_a.success_rate:>8.1f}%      {arch_a.avg_latency_ms:>8.0f}ms")
    print(f"{arch_b.architecture_name:<30} {arch_b.success_rate:>8.1f}%      {arch_b.avg_latency_ms:>8.0f}ms")

    print("-" * 60)

    # Summary
    latency_diff = arch_b.avg_latency_ms - arch_a.avg_latency_ms
    success_diff = arch_b.success_rate - arch_a.success_rate

    print(f"\nTwo-layer architecture adds {latency_diff:.0f}ms latency")
    print(f"Success rate difference: {success_diff:+.1f}%")

    if success_diff > 0:
        print(f"\n✓ Two-layer improves success rate by {success_diff:.1f}%")
    elif success_diff < 0:
        print(f"\n⚠ Two-layer reduces success rate by {abs(success_diff):.1f}%")
    else:
        print(f"\n= No change in success rate")

    # Count fixes
    fixes = sum(1 for r in arch_b.results if r.changes_made)
    print(f"\nValidation layer made fixes in {fixes}/{arch_b.total_queries} queries")


# ============================================================================
# TEST QUERIES
# ============================================================================

TEST_QUERIES = [
    "Looking to buy a Dell laptop in Bangalore under 50000",
    "Want to purchase iPhone 15 Pro in Delhi, budget 90000",
    "Selling HP laptop starting 40000 in Bangalore",
    "Looking for a plumber in Bangalore who speaks Kannada",
    "I am a plumber in Bangalore, charge 500 per hour",
    "Need electrician in Mumbai for AC repair",
]


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Two-Layer Architecture")
    parser.add_argument("--model", default="nuextract", help="Validation model (nuextract, qwen3, etc.)")
    parser.add_argument("--quick", action="store_true", help="Quick test with 3 queries")
    parser.add_argument("--output", default="two_layer_results.json", help="Output file")

    args = parser.parse_args()

    queries = TEST_QUERIES[:3] if args.quick else TEST_QUERIES

    print("=" * 80)
    print("TWO-LAYER ARCHITECTURE TEST")
    print("=" * 80)
    print(f"\nValidation model: {args.model}")
    print(f"Test queries: {len(queries)}")

    # Run Architecture A (GPT only)
    arch_a = run_single_layer_gpt(queries)

    # Run Architecture B (GPT + Local validation)
    arch_b = run_two_layer_architecture(queries, validation_model=args.model)

    # Print comparison
    print_architecture_comparison(arch_a, arch_b)

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "architecture_a": {
                "name": arch_a.architecture_name,
                "success_rate": arch_a.success_rate,
                "avg_latency_ms": arch_a.avg_latency_ms,
                "results": [
                    {
                        "query": r.query,
                        "gpt_success": r.gpt_success,
                        "validation_success": r.validation_success,
                        "total_latency_ms": r.total_latency_ms
                    }
                    for r in arch_a.results
                ]
            },
            "architecture_b": {
                "name": arch_b.architecture_name,
                "success_rate": arch_b.success_rate,
                "avg_latency_ms": arch_b.avg_latency_ms,
                "results": [
                    {
                        "query": r.query,
                        "gpt_success": r.gpt_success,
                        "validation_success": r.validation_success,
                        "total_latency_ms": r.total_latency_ms,
                        "changes_made": r.changes_made
                    }
                    for r in arch_b.results
                ]
            }
        }, f, indent=2)

    print(f"\n[OK] Results saved to: {output_path}")
