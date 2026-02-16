"""
Model Comparison Test: Compare GPT vs Local Models for JSON extraction.

Phase 1: Compare extraction quality across models
- GPT-4o (baseline)
- NuExtract-2.0-2B
- Qwen3-0.6B
- SmolLM3-3B
- Phi-4-mini

All models use the same prompt: GLOBAL_REFERENCE_CONTEXT.md

Metrics:
- Extraction success rate
- Schema completeness (required fields present)
- Latency (ms)
- Field accuracy vs GPT baseline
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
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
    load_extraction_prompt
)
from src.core.extraction.gpt_extractor import GPTExtractor


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

TEST_QUERIES = [
    # Product Buy
    "Looking to buy a Dell laptop in Bangalore under 50000",
    "Want to purchase iPhone 15 Pro in Delhi, budget 90000",
    "Need 3 kg fresh organic vegetables in Mumbai under 500 rupees",

    # Product Sell
    "Selling HP laptop starting 40000 in Bangalore",
    "Selling iPhone 15 Pro in Delhi for 80000 to 100000",
    "Fresh organic vegetables available in Bangalore 100 rupees per kg",

    # Service Seek
    "Looking for a plumber in Bangalore who speaks Kannada",
    "Need electrician in Mumbai for AC repair, budget 2000",
    "Looking for yoga instructor in Delhi, 500 per session",

    # Service Provide
    "I am a plumber in Bangalore, charge 500 per hour",
    "Electrician available for AC repair in Mumbai",
    "Yoga instructor providing home sessions in Delhi",
]

REQUIRED_FIELDS = ["intent", "subintent", "domain", "items"]


@dataclass
class ModelResult:
    """Results for a single model across all queries."""
    model_name: str
    total_queries: int = 0
    successful_extractions: int = 0
    schema_complete: int = 0
    total_latency_ms: float = 0.0
    results: List[ExtractionResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.successful_extractions / self.total_queries * 100

    @property
    def completeness_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.schema_complete / self.total_queries * 100

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_extractions == 0:
            return 0.0
        return self.total_latency_ms / self.successful_extractions


@dataclass
class ComparisonReport:
    """Full comparison report across all models."""
    gpt_results: Optional[ModelResult] = None
    local_results: Dict[str, ModelResult] = field(default_factory=dict)
    test_queries: List[str] = field(default_factory=list)


# ============================================================================
# SCHEMA VALIDATION
# ============================================================================

def check_schema_completeness(extracted: Dict[str, Any]) -> bool:
    """Check if all required fields are present."""
    for field_name in REQUIRED_FIELDS:
        if field_name not in extracted:
            return False
        if extracted[field_name] is None:
            return False
    return True


def compare_extractions(gpt_json: Dict[str, Any], local_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare local extraction against GPT baseline.

    Returns dict with field-level comparison.
    """
    comparison = {
        "intent_match": gpt_json.get("intent") == local_json.get("intent"),
        "subintent_match": gpt_json.get("subintent") == local_json.get("subintent"),
        "domain_overlap": len(
            set(gpt_json.get("domain", [])) & set(local_json.get("domain", []))
        ) > 0 if gpt_json.get("domain") and local_json.get("domain") else False,
        "items_count_match": len(gpt_json.get("items", [])) == len(local_json.get("items", [])),
    }

    # Calculate overall similarity score
    matches = sum(1 for v in comparison.values() if v)
    comparison["similarity_score"] = matches / len(comparison) * 100

    return comparison


# ============================================================================
# TEST RUNNERS
# ============================================================================

def test_gpt_extraction(queries: List[str]) -> ModelResult:
    """Run extraction tests with GPT-4o."""
    print("\n" + "=" * 60)
    print("TESTING GPT-4o")
    print("=" * 60)

    result = ModelResult(model_name="gpt-4o")

    # Initialize GPT extractor
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

            result.successful_extractions += 1
            result.total_latency_ms += latency_ms

            if check_schema_completeness(extracted):
                result.schema_complete += 1

            result.results.append(ExtractionResult(
                model="gpt-4o",
                query=query,
                extracted_json=extracted,
                raw_output=json.dumps(extracted),
                latency_ms=latency_ms,
                success=True
            ))

            print(f"  ✓ Success ({latency_ms:.0f}ms)")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            result.results.append(ExtractionResult(
                model="gpt-4o",
                query=query,
                extracted_json=None,
                raw_output="",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            ))
            print(f"  ✗ Failed: {e}")

    return result


def test_local_model(model_key: str, queries: List[str]) -> ModelResult:
    """Run extraction tests with a local model."""
    print("\n" + "=" * 60)
    print(f"TESTING LOCAL MODEL: {model_key}")
    print("=" * 60)

    result = ModelResult(model_name=model_key)

    # Initialize local extractor
    extractor = LocalModelExtractor(model=model_key)
    if not extractor.initialize():
        print(f"[ERROR] Failed to initialize {model_key}")
        return result

    for query in queries:
        result.total_queries += 1
        print(f"\n[{result.total_queries}/{len(queries)}] {query[:50]}...")

        extraction_result = extractor.extract_with_metrics(query)
        result.results.append(extraction_result)

        if extraction_result.success:
            result.successful_extractions += 1
            result.total_latency_ms += extraction_result.latency_ms

            if check_schema_completeness(extraction_result.extracted_json):
                result.schema_complete += 1

            print(f"  ✓ Success ({extraction_result.latency_ms:.0f}ms)")
        else:
            print(f"  ✗ Failed: {extraction_result.error}")

    return result


# ============================================================================
# REPORT GENERATION
# ============================================================================

def print_summary_report(report: ComparisonReport):
    """Print summary comparison report."""
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)

    # Header
    print(f"\n{'Model':<20} {'Success':<12} {'Complete':<12} {'Avg Latency':<15}")
    print("-" * 60)

    # GPT results
    if report.gpt_results:
        r = report.gpt_results
        print(f"{'GPT-4o (baseline)':<20} {r.success_rate:>6.1f}%     {r.completeness_rate:>6.1f}%     {r.avg_latency_ms:>8.0f}ms")

    # Local model results
    for model_name, r in report.local_results.items():
        print(f"{model_name:<20} {r.success_rate:>6.1f}%     {r.completeness_rate:>6.1f}%     {r.avg_latency_ms:>8.0f}ms")

    print("-" * 60)

    # Detailed comparison against GPT
    if report.gpt_results:
        print("\n" + "=" * 80)
        print("FIELD-LEVEL COMPARISON VS GPT BASELINE")
        print("=" * 80)

        for model_name, local_result in report.local_results.items():
            print(f"\n{model_name}:")

            intent_match = 0
            subintent_match = 0
            domain_match = 0
            total_compared = 0

            for i, gpt_r in enumerate(report.gpt_results.results):
                if not gpt_r.success:
                    continue

                if i >= len(local_result.results):
                    continue

                local_r = local_result.results[i]
                if not local_r.success:
                    continue

                total_compared += 1
                comparison = compare_extractions(gpt_r.extracted_json, local_r.extracted_json)

                if comparison["intent_match"]:
                    intent_match += 1
                if comparison["subintent_match"]:
                    subintent_match += 1
                if comparison["domain_overlap"]:
                    domain_match += 1

            if total_compared > 0:
                print(f"  Intent match:    {intent_match}/{total_compared} ({intent_match/total_compared*100:.1f}%)")
                print(f"  Subintent match: {subintent_match}/{total_compared} ({subintent_match/total_compared*100:.1f}%)")
                print(f"  Domain overlap:  {domain_match}/{total_compared} ({domain_match/total_compared*100:.1f}%)")


def save_detailed_results(report: ComparisonReport, output_path: str):
    """Save detailed results to JSON file."""
    output = {
        "test_queries": report.test_queries,
        "gpt_results": None,
        "local_results": {}
    }

    if report.gpt_results:
        output["gpt_results"] = {
            "model": report.gpt_results.model_name,
            "success_rate": report.gpt_results.success_rate,
            "completeness_rate": report.gpt_results.completeness_rate,
            "avg_latency_ms": report.gpt_results.avg_latency_ms,
            "extractions": [
                {
                    "query": r.query,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "extracted_json": r.extracted_json,
                    "error": r.error
                }
                for r in report.gpt_results.results
            ]
        }

    for model_name, model_result in report.local_results.items():
        output["local_results"][model_name] = {
            "model": model_result.model_name,
            "success_rate": model_result.success_rate,
            "completeness_rate": model_result.completeness_rate,
            "avg_latency_ms": model_result.avg_latency_ms,
            "extractions": [
                {
                    "query": r.query,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "extracted_json": r.extracted_json,
                    "error": r.error
                }
                for r in model_result.results
            ]
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n[OK] Detailed results saved to: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def run_comparison(
    include_gpt: bool = True,
    local_models: Optional[List[str]] = None,
    queries: Optional[List[str]] = None
) -> ComparisonReport:
    """
    Run full model comparison.

    Args:
        include_gpt: Whether to include GPT-4o baseline
        local_models: List of local model keys to test (default: all available)
        queries: Test queries (default: TEST_QUERIES)

    Returns:
        ComparisonReport with all results
    """
    if queries is None:
        queries = TEST_QUERIES

    report = ComparisonReport(test_queries=queries)

    # Test GPT baseline
    if include_gpt:
        report.gpt_results = test_gpt_extraction(queries)

    # Check Ollama availability
    if not check_ollama_status():
        print("\n[WARN] Ollama not running. Skipping local model tests.")
        print("Start Ollama with: ollama serve")
        return report

    # Determine which local models to test
    available_models = list_available_models()
    print(f"\n[INFO] Available Ollama models: {available_models}")

    if local_models is None:
        # Test all available models
        local_models = [m for m in available_models if m in ["nuextract", "qwen3:0.6b", "smollm3:3b", "phi4-mini"]]

    if not local_models:
        print("\n[WARN] No local models available for testing.")
        print("Pull models with: ollama pull nuextract")
        return report

    # Test each local model
    for model_key in local_models:
        result = test_local_model(model_key, queries)
        report.local_results[model_key] = result

    return report


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare GPT vs Local Models for JSON extraction")
    parser.add_argument("--no-gpt", action="store_true", help="Skip GPT-4o baseline test")
    parser.add_argument("--models", nargs="+", help="Specific local models to test")
    parser.add_argument("--output", default="comparison_results.json", help="Output file for detailed results")
    parser.add_argument("--quick", action="store_true", help="Run quick test with 3 queries only")

    args = parser.parse_args()

    queries = TEST_QUERIES[:3] if args.quick else TEST_QUERIES

    print("=" * 80)
    print("MODEL COMPARISON TEST")
    print("=" * 80)
    print(f"\nTest queries: {len(queries)}")
    print(f"Include GPT: {not args.no_gpt}")
    print(f"Local models: {args.models or 'all available'}")

    # Run comparison
    report = run_comparison(
        include_gpt=not args.no_gpt,
        local_models=args.models,
        queries=queries
    )

    # Print summary
    print_summary_report(report)

    # Save detailed results
    output_path = os.path.join(os.path.dirname(__file__), args.output)
    save_detailed_results(report, output_path)
