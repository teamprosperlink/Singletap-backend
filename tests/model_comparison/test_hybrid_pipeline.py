"""
Test Hybrid Extraction Pipeline: GPT Full Extract + NuExtract Validate

Tests the two-level hybrid architecture:
  Level 1: GPT-4o-mini extracts using FULL GLOBAL_REFERENCE_CONTEXT.md
  Level 2: NuExtract validates using SAME FULL prompt

CRITICAL: Both levels use the FULL prompt file.

Usage:
    python -m tests.model_comparison.test_hybrid_pipeline
    python -m tests.model_comparison.test_hybrid_pipeline --quick
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List
from dataclasses import dataclass, field

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
sys.path.insert(0, project_root)

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from src.core.extraction.hybrid_extractor import (
    HybridExtractor,
    HybridExtractionResult,
)


# ============================================================================
# TEST CASES
# ============================================================================

@dataclass
class TestCase:
    """Test case with query and expected values."""
    query: str
    expected_intent: str
    expected_subintent: str
    description: str


TEST_CASES = [
    # Product Buy
    TestCase(
        query="Looking to buy a Dell laptop in Bangalore under 50000",
        expected_intent="product",
        expected_subintent="buy",
        description="Product buy with brand, location, max price"
    ),
    TestCase(
        query="Want to purchase iPhone 15 Pro in Delhi, budget 90000",
        expected_intent="product",
        expected_subintent="buy",
        description="Product buy with model, location, budget"
    ),
    TestCase(
        query="Need 3 kg fresh organic vegetables in Mumbai under 500 rupees",
        expected_intent="product",
        expected_subintent="buy",
        description="Product buy with quantity, attributes, max price"
    ),

    # Product Sell
    TestCase(
        query="Selling HP laptop starting 40000 in Bangalore",
        expected_intent="product",
        expected_subintent="sell",
        description="Product sell with brand, min price, location"
    ),
    TestCase(
        query="Selling iPhone 15 Pro in Delhi for 80000 to 100000",
        expected_intent="product",
        expected_subintent="sell",
        description="Product sell with price range"
    ),
    TestCase(
        query="Fresh organic vegetables available in Bangalore 100 rupees per kg",
        expected_intent="product",
        expected_subintent="sell",
        description="Product sell with unit price"
    ),

    # Service Seek
    TestCase(
        query="Looking for a plumber in Bangalore who speaks Kannada",
        expected_intent="service",
        expected_subintent="seek",
        description="Service seek with language requirement"
    ),
    TestCase(
        query="Need electrician in Mumbai for AC repair, budget 2000",
        expected_intent="service",
        expected_subintent="seek",
        description="Service seek with specific task and budget"
    ),
    TestCase(
        query="Looking for yoga instructor in Delhi, 500 per session",
        expected_intent="service",
        expected_subintent="seek",
        description="Service seek with rate constraint"
    ),

    # Service Provide (CRITICAL - tests semantic understanding)
    TestCase(
        query="I am a plumber in Bangalore, charge 500 per hour",
        expected_intent="service",
        expected_subintent="provide",
        description="Service provide - 'I am a X' pattern"
    ),
    TestCase(
        query="Electrician available for AC repair in Mumbai",
        expected_intent="service",
        expected_subintent="provide",
        description="Service provide - availability pattern"
    ),
    TestCase(
        query="Yoga instructor providing home sessions in Delhi",
        expected_intent="service",
        expected_subintent="provide",
        description="Service provide - offering services"
    ),
]


# ============================================================================
# TEST RUNNER
# ============================================================================

@dataclass
class TestResult:
    """Result of a single test case."""
    test_case: TestCase
    extraction_result: HybridExtractionResult
    intent_correct: bool
    subintent_correct: bool
    passed: bool


@dataclass
class TestReport:
    """Full test report."""
    results: List[TestResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    intent_accuracy: float = 0.0
    subintent_accuracy: float = 0.0


def run_tests(test_cases: List[TestCase], skip_nuextract: bool = False) -> TestReport:
    """
    Run hybrid extraction tests.

    Args:
        test_cases: List of test cases
        skip_nuextract: If True, skip NuExtract validation (GPT-only mode)

    Returns:
        TestReport with all results
    """
    print("=" * 70)
    print("HYBRID PIPELINE TEST")
    print("=" * 70)
    print("Level 1: GPT-4o-mini Full Extraction")
    if skip_nuextract:
        print("Level 2: SKIPPED (GPT-only mode)")
    else:
        print("Level 2: NuExtract Validation")
    print("Prompt: FULL GLOBAL_REFERENCE_CONTEXT.md (BOTH levels)")
    print("=" * 70)

    # Initialize extractor
    extractor = HybridExtractor(skip_nuextract=skip_nuextract)
    if not extractor.initialize():
        print("\n[ERROR] Failed to initialize HybridExtractor")
        print("Check: OPENAI_API_KEY set, Ollama running")
        return TestReport()

    report = TestReport()

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}/{len(test_cases)}: {test_case.description}")
        print(f"Query: {test_case.query}")
        print("-" * 60)

        # Run extraction
        result = extractor.extract(test_case.query)

        # Check results
        intent_correct = False
        subintent_correct = False

        if result.success and result.final_json:
            actual_intent = result.final_json.get("intent", "").lower()
            actual_subintent = result.final_json.get("subintent", "").lower()

            intent_correct = actual_intent == test_case.expected_intent
            subintent_correct = actual_subintent == test_case.expected_subintent

            print(f"\nExtracted:")
            print(f"  intent: {actual_intent} {'✓' if intent_correct else '✗'} (expected: {test_case.expected_intent})")
            print(f"  subintent: {actual_subintent} {'✓' if subintent_correct else '✗'} (expected: {test_case.expected_subintent})")

            # Show other key fields
            if "domain" in result.final_json:
                print(f"  domain: {result.final_json.get('domain')}")
            if "items" in result.final_json and result.final_json["items"]:
                items = result.final_json["items"]
                if len(items) > 0:
                    print(f"  items[0].type: {items[0].get('type', 'N/A')}")

            print(f"\nLatency: Total={result.total_latency_ms:.0f}ms, GPT={result.gpt_latency_ms:.0f}ms")
            if result.fallback_used:
                print("  [NOTE] Used GPT fallback (NuExtract failed)")
        else:
            print(f"\n[FAILED] {result.gpt_error or result.nuextract_error}")

        passed = intent_correct and subintent_correct

        test_result = TestResult(
            test_case=test_case,
            extraction_result=result,
            intent_correct=intent_correct,
            subintent_correct=subintent_correct,
            passed=passed
        )
        report.results.append(test_result)
        report.total += 1
        if passed:
            report.passed += 1

    # Calculate accuracy
    if report.total > 0:
        report.intent_accuracy = sum(1 for r in report.results if r.intent_correct) / report.total * 100
        report.subintent_accuracy = sum(1 for r in report.results if r.subintent_correct) / report.total * 100

    return report


def print_report(report: TestReport):
    """Print test report summary."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"\nOverall: {report.passed}/{report.total} passed ({report.passed/max(report.total,1)*100:.1f}%)")
    print(f"Intent accuracy: {report.intent_accuracy:.1f}%")
    print(f"Subintent accuracy: {report.subintent_accuracy:.1f}%")

    # Show failed tests
    failed = [r for r in report.results if not r.passed]
    if failed:
        print(f"\nFailed tests ({len(failed)}):")
        for r in failed:
            print(f"  - {r.test_case.description}")
            if r.extraction_result.final_json:
                actual_intent = r.extraction_result.final_json.get("intent", "N/A")
                actual_subintent = r.extraction_result.final_json.get("subintent", "N/A")
                print(f"    Got: {actual_intent}/{actual_subintent}, Expected: {r.test_case.expected_intent}/{r.test_case.expected_subintent}")

    # Latency stats
    successful = [r for r in report.results if r.extraction_result.success]
    if successful:
        avg_total = sum(r.extraction_result.total_latency_ms for r in successful) / len(successful)
        avg_gpt = sum(r.extraction_result.gpt_latency_ms for r in successful) / len(successful)
        avg_nuextract = sum(r.extraction_result.nuextract_latency_ms for r in successful) / len(successful)
        fallback_count = sum(1 for r in successful if r.extraction_result.fallback_used)

        print(f"\nLatency (avg):")
        print(f"  Total: {avg_total:.0f}ms")
        print(f"  GPT (Level 1): {avg_gpt:.0f}ms")
        print(f"  NuExtract (Level 2): {avg_nuextract:.0f}ms")
        print(f"\nFallback to GPT: {fallback_count}/{len(successful)}")


def save_results(report: TestReport, output_path: str):
    """Save detailed results to JSON."""
    output = {
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "pass_rate": report.passed / max(report.total, 1) * 100,
            "intent_accuracy": report.intent_accuracy,
            "subintent_accuracy": report.subintent_accuracy,
        },
        "tests": []
    }

    for r in report.results:
        output["tests"].append({
            "query": r.test_case.query,
            "description": r.test_case.description,
            "expected_intent": r.test_case.expected_intent,
            "expected_subintent": r.test_case.expected_subintent,
            "actual_intent": r.extraction_result.final_json.get("intent") if r.extraction_result.final_json else None,
            "actual_subintent": r.extraction_result.final_json.get("subintent") if r.extraction_result.final_json else None,
            "intent_correct": r.intent_correct,
            "subintent_correct": r.subintent_correct,
            "passed": r.passed,
            "latency_ms": {
                "total": r.extraction_result.total_latency_ms,
                "gpt": r.extraction_result.gpt_latency_ms,
                "nuextract": r.extraction_result.nuextract_latency_ms,
            },
            "fallback_used": r.extraction_result.fallback_used,
            "final_json": r.extraction_result.final_json,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n[OK] Results saved to: {output_path}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Hybrid Extraction Pipeline")
    parser.add_argument("--quick", action="store_true", help="Run quick test with 4 queries")
    parser.add_argument("--gpt-only", action="store_true", help="GPT-only mode (skip NuExtract)")
    parser.add_argument("--output", default="hybrid_test_results.json", help="Output file")

    args = parser.parse_args()

    # Select test cases
    if args.quick:
        # Quick test: one from each category
        test_cases = [
            TEST_CASES[0],  # product/buy
            TEST_CASES[3],  # product/sell
            TEST_CASES[6],  # service/seek
            TEST_CASES[9],  # service/provide (critical test)
        ]
    else:
        test_cases = TEST_CASES

    print(f"\nRunning {len(test_cases)} test cases...")
    if args.gpt_only:
        print("[MODE] GPT-only (NuExtract validation skipped)")

    # Run tests
    report = run_tests(test_cases, skip_nuextract=args.gpt_only)

    # Print summary
    print_report(report)

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), args.output)
    save_results(report, output_path)
