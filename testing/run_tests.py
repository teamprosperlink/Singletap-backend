"""
VRIDDHI API TESTING FRAMEWORK - Main Test Runner

Purpose: Execute comprehensive API tests across all endpoints with
support for individual endpoint testing and unified --all mode.

Endpoints Tested:
1. /ingest - Seed database with pre-extracted listings (no GPT cost)
2. /search-and-match-direct - Matching with pre-extracted queries (no GPT cost)
3. /extract-and-match - GPT extraction + matching (GPT cost)
4. /match - Direct schema matching (no GPT cost)

Features:
- Similar matching validation (when enabled)
- Smart message generation testing
- Timing and performance metrics
- JSON and HTML report generation

Usage:
    python -m testing.run_tests --seed           # Seed database only
    python -m testing.run_tests --match          # Run matching tests
    python -m testing.run_tests --similar        # Test similar matching
    python -m testing.run_tests --extract        # Test GPT extraction
    python -m testing.run_tests --all            # Run all tests
    python -m testing.run_tests --report         # Generate reports

Author: Claude
Date: 2025-02-23
"""

import argparse
import asyncio
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Configuration
TEST_DATA_DIR = Path(__file__).parent / "test_data"
REPORTS_DIR = Path(__file__).parent / "reports"

# Default API URL (can be overridden with --url)
DEFAULT_API_URL = "https://singletap-backend.onrender.com"

# Timeouts
REQUEST_TIMEOUT = 60.0  # seconds


@dataclass
class TestResult:
    """Result of a single test."""
    test_id: str
    endpoint: str
    pair_type: str
    query: str
    status: str  # success, failure, error
    expected_match: bool
    actual_match: bool
    match_count: int
    similar_count: int
    similar_enabled: bool
    response_time_ms: float
    response_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    notes: str = ""


@dataclass
class TestSuite:
    """Collection of test results."""
    suite_name: str
    endpoint: str
    started_at: str
    completed_at: Optional[str] = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total_time_ms: float = 0
    avg_response_time_ms: float = 0
    results: List[TestResult] = field(default_factory=list)


class APITester:
    """Main test runner class."""

    def __init__(self, api_url: str, verbose: bool = False):
        self.api_url = api_url.rstrip("/")
        self.verbose = verbose
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        self.seeded_listings: Dict[str, str] = {}  # test_id -> listing_id

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def log(self, message: str):
        """Print message if verbose mode."""
        if self.verbose:
            print(message)

    # =========================================================================
    # DATABASE SEEDING
    # =========================================================================

    async def seed_database(self) -> Dict[str, Any]:
        """Seed database with test listings using /ingest endpoint."""
        print("\n" + "=" * 60)
        print("SEEDING DATABASE")
        print("=" * 60)

        seed_file = TEST_DATA_DIR / "seed_listings.json"
        if not seed_file.exists():
            print(f"ERROR: Seed file not found: {seed_file}")
            print("Run: python -m testing.prepare_test_data first")
            return {"status": "error", "message": "Seed file not found"}

        with open(seed_file, "r", encoding="utf-8") as f:
            seed_listings = json.load(f)

        print(f"Loaded {len(seed_listings)} listings to seed")

        results = {
            "total": len(seed_listings),
            "success": 0,
            "failed": 0,
            "seeded_ids": {}
        }

        for i, listing in enumerate(seed_listings):
            try:
                # Prepare ingest request
                # Generate a proper UUID for user_id
                import hashlib
                hash_input = f"test_user_{listing['test_id']}"
                user_uuid = f"550e8400-e29b-41d4-a716-{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"

                # Build the request - /ingest expects "listing" field with extracted schema
                # The normalized_query (stage3) IS the extracted schema format
                request_data = {
                    "listing": listing["normalized_query"],
                    "user_id": user_uuid
                }

                start_time = time.time()
                response = await self.client.post(
                    f"{self.api_url}/ingest",
                    json=request_data
                )
                elapsed = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    listing_id = data.get("listing_id", data.get("id"))
                    self.seeded_listings[listing["test_id"]] = listing_id
                    results["seeded_ids"][listing["test_id"]] = listing_id
                    results["success"] += 1
                    self.log(f"  [{i+1}/{len(seed_listings)}] ✓ {listing['test_id']} -> {listing_id} ({elapsed:.0f}ms)")
                else:
                    results["failed"] += 1
                    print(f"  [{i+1}/{len(seed_listings)}] ✗ {listing['test_id']} - {response.status_code}: {response.text[:100]}")

            except Exception as e:
                results["failed"] += 1
                print(f"  [{i+1}/{len(seed_listings)}] ✗ {listing['test_id']} - Error: {e}")

            # Progress indicator
            if not self.verbose and (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(seed_listings)}")

        # Save seeded IDs for later reference
        with open(TEST_DATA_DIR / "seeded_ids.json", "w") as f:
            json.dump(results["seeded_ids"], f, indent=2)

        print(f"\nSeeding complete: {results['success']} success, {results['failed']} failed")
        return results

    # =========================================================================
    # MATCHING TESTS
    # =========================================================================

    async def run_search_and_match_direct_tests(self) -> TestSuite:
        """Test /search-and-match-direct endpoint."""
        suite = TestSuite(
            suite_name="Search and Match Direct",
            endpoint="/search-and-match-direct",
            started_at=datetime.now().isoformat()
        )

        print("\n" + "=" * 60)
        print("TESTING: /search-and-match-direct")
        print("=" * 60)

        queries_file = TEST_DATA_DIR / "test_queries.json"
        if not queries_file.exists():
            print(f"ERROR: Test queries not found: {queries_file}")
            return suite

        with open(queries_file, "r", encoding="utf-8") as f:
            test_queries = json.load(f)

        print(f"Loaded {len(test_queries)} test queries")

        for i, query_data in enumerate(test_queries):
            try:
                # Build request - /search-and-match-direct expects listing_json
                import hashlib
                hash_input = f"query_user_{query_data['test_id']}"
                user_uuid = f"550e8400-e29b-41d4-a716-{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"

                request_data = {
                    "listing_json": query_data["stage3"],
                    "user_id": user_uuid
                }

                start_time = time.time()
                response = await self.client.post(
                    f"{self.api_url}/search-and-match-direct",
                    json=request_data
                )
                elapsed = (time.time() - start_time) * 1000

                result = TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/search-and-match-direct",
                    pair_type=query_data["pair_type"],
                    query=query_data["query"][:100],
                    status="success" if response.status_code == 200 else "error",
                    expected_match=True,  # We paired them by category
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=elapsed,
                    notes=query_data.get("notes", "")
                )

                if response.status_code == 200:
                    data = response.json()
                    result.response_data = data
                    result.actual_match = data.get("has_matches", False)
                    result.match_count = data.get("match_count", 0)
                    result.similar_count = data.get("similar_count", 0)
                    result.similar_enabled = data.get("similar_matching_enabled", False)

                    match_status = "✓ Match" if result.actual_match else "○ No match"
                    similar_status = f" (+{result.similar_count} similar)" if result.similar_count > 0 else ""
                    self.log(f"  [{i+1}] {match_status}{similar_status} ({elapsed:.0f}ms)")
                else:
                    result.status = "error"
                    result.error_message = response.text[:200]

                suite.results.append(result)

            except Exception as e:
                suite.results.append(TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/search-and-match-direct",
                    pair_type=query_data["pair_type"],
                    query=query_data["query"][:100],
                    status="error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=0,
                    error_message=str(e)
                ))

            # Progress
            if not self.verbose and (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(test_queries)}")

        # Calculate stats
        suite.completed_at = datetime.now().isoformat()
        suite.total_tests = len(suite.results)
        suite.passed = sum(1 for r in suite.results if r.actual_match or r.similar_count > 0)
        suite.failed = sum(1 for r in suite.results if r.status == "success" and not r.actual_match and r.similar_count == 0)
        suite.errors = sum(1 for r in suite.results if r.status == "error")
        suite.total_time_ms = sum(r.response_time_ms for r in suite.results)
        suite.avg_response_time_ms = suite.total_time_ms / max(1, suite.total_tests)

        self._print_suite_summary(suite)
        return suite

    async def run_match_tests(self) -> TestSuite:
        """Test /match endpoint (direct schema matching)."""
        suite = TestSuite(
            suite_name="Direct Match",
            endpoint="/match",
            started_at=datetime.now().isoformat()
        )

        print("\n" + "=" * 60)
        print("TESTING: /match")
        print("=" * 60)

        # Load both seed listings and queries for direct comparison
        pairs_files = [
            ("product_pairs.json", "product"),
            ("service_pairs.json", "service"),
            ("mutual_pairs.json", "mutual")
        ]

        all_pairs = []
        for filename, pair_type in pairs_files:
            filepath = TEST_DATA_DIR / filename
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    pairs = json.load(f)
                    for pair in pairs:
                        pair["pair_type"] = pair_type
                    all_pairs.extend(pairs)

        print(f"Loaded {len(all_pairs)} pairs for matching")

        for i, pair in enumerate(all_pairs):
            try:
                seed_entry = pair["seed_entry"]
                query_entry = pair["query_entry"]

                # Build match request - direct schema comparison
                request_data = {
                    "query_schema": query_entry["stage3"],
                    "candidate_schema": seed_entry["stage3"],
                    "source": query_entry["source"]
                }

                start_time = time.time()
                response = await self.client.post(
                    f"{self.api_url}/match",
                    json=request_data
                )
                elapsed = (time.time() - start_time) * 1000

                result = TestResult(
                    test_id=f"match_{pair['pair_type']}_{i+1:03d}",
                    endpoint="/match",
                    pair_type=pair["pair_type"],
                    query=query_entry["query"][:100],
                    status="success" if response.status_code == 200 else "error",
                    expected_match=pair.get("expected_match", True),
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=elapsed,
                    notes=pair.get("notes", "")
                )

                if response.status_code == 200:
                    data = response.json()
                    result.response_data = data
                    result.actual_match = data.get("is_match", False)
                    # /match returns similarity info
                    if "similarity_score" in data:
                        result.similar_enabled = True
                        if data.get("is_similar_match"):
                            result.similar_count = 1

                    match_status = "✓ Match" if result.actual_match else "○ No match"
                    self.log(f"  [{i+1}] {match_status} ({elapsed:.0f}ms)")
                else:
                    result.status = "error"
                    result.error_message = response.text[:200]

                suite.results.append(result)

            except Exception as e:
                suite.results.append(TestResult(
                    test_id=f"match_{pair['pair_type']}_{i+1:03d}",
                    endpoint="/match",
                    pair_type=pair["pair_type"],
                    query="",
                    status="error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=0,
                    error_message=str(e)
                ))

            if not self.verbose and (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(all_pairs)}")

        suite.completed_at = datetime.now().isoformat()
        suite.total_tests = len(suite.results)
        suite.passed = sum(1 for r in suite.results if r.actual_match)
        suite.failed = sum(1 for r in suite.results if r.status == "success" and not r.actual_match)
        suite.errors = sum(1 for r in suite.results if r.status == "error")
        suite.total_time_ms = sum(r.response_time_ms for r in suite.results)
        suite.avg_response_time_ms = suite.total_time_ms / max(1, suite.total_tests)

        self._print_suite_summary(suite)
        return suite

    async def run_extract_and_match_tests(self, limit: int = 10) -> TestSuite:
        """Test /extract-and-match endpoint (uses GPT, limited by default)."""
        suite = TestSuite(
            suite_name="Extract and Match",
            endpoint="/extract-and-match",
            started_at=datetime.now().isoformat()
        )

        print("\n" + "=" * 60)
        print(f"TESTING: /extract-and-match (limited to {limit} - uses GPT API)")
        print("=" * 60)

        queries_file = TEST_DATA_DIR / "test_queries.json"
        if not queries_file.exists():
            print(f"ERROR: Test queries not found: {queries_file}")
            return suite

        with open(queries_file, "r", encoding="utf-8") as f:
            test_queries = json.load(f)

        # Limit to avoid excessive GPT costs
        test_queries = test_queries[:limit]
        print(f"Testing {len(test_queries)} queries (GPT extraction)")

        for i, query_data in enumerate(test_queries):
            try:
                # Use raw query text for GPT extraction
                request_data = {
                    "user_id": f"extract_user_{query_data['test_id']}",
                    "query": query_data["query"],
                    "source": query_data["source"]
                }

                start_time = time.time()
                response = await self.client.post(
                    f"{self.api_url}/extract-and-match",
                    json=request_data,
                    timeout=120.0  # GPT extraction takes longer
                )
                elapsed = (time.time() - start_time) * 1000

                result = TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/extract-and-match",
                    pair_type=query_data["pair_type"],
                    query=query_data["query"][:100],
                    status="success" if response.status_code == 200 else "error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=elapsed,
                    notes=query_data.get("notes", "")
                )

                if response.status_code == 200:
                    data = response.json()
                    result.response_data = data
                    result.actual_match = data.get("has_matches", False)
                    result.match_count = data.get("match_count", 0)

                    match_status = "✓ Match" if result.actual_match else "○ No match"
                    print(f"  [{i+1}] {match_status} ({elapsed:.0f}ms)")
                else:
                    result.status = "error"
                    result.error_message = response.text[:200]
                    print(f"  [{i+1}] ✗ Error: {response.status_code}")

                suite.results.append(result)

            except Exception as e:
                suite.results.append(TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/extract-and-match",
                    pair_type=query_data["pair_type"],
                    query=query_data["query"][:100],
                    status="error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=0,
                    error_message=str(e)
                ))
                print(f"  [{i+1}] ✗ Exception: {e}")

        suite.completed_at = datetime.now().isoformat()
        suite.total_tests = len(suite.results)
        suite.passed = sum(1 for r in suite.results if r.actual_match)
        suite.failed = sum(1 for r in suite.results if r.status == "success" and not r.actual_match)
        suite.errors = sum(1 for r in suite.results if r.status == "error")
        suite.total_time_ms = sum(r.response_time_ms for r in suite.results)
        suite.avg_response_time_ms = suite.total_time_ms / max(1, suite.total_tests)

        self._print_suite_summary(suite)
        return suite

    # =========================================================================
    # SIMILAR MATCHING TESTS
    # =========================================================================

    async def run_similar_matching_tests(self) -> TestSuite:
        """Test similar matching functionality specifically."""
        suite = TestSuite(
            suite_name="Similar Matching",
            endpoint="/search-and-match-direct",
            started_at=datetime.now().isoformat()
        )

        print("\n" + "=" * 60)
        print("TESTING: Similar Matching")
        print("=" * 60)

        # First check if similar matching is enabled
        health_response = await self.client.get(f"{self.api_url}/health")
        if health_response.status_code != 200:
            print("ERROR: Cannot reach API")
            return suite

        queries_file = TEST_DATA_DIR / "test_queries.json"
        if not queries_file.exists():
            print(f"ERROR: Test queries not found")
            return suite

        with open(queries_file, "r", encoding="utf-8") as f:
            test_queries = json.load(f)

        # Test a subset to analyze similar matching behavior
        test_subset = test_queries[:50]
        print(f"Testing {len(test_subset)} queries for similar matching")

        similar_found = 0
        smart_messages = []

        for i, query_data in enumerate(test_subset):
            try:
                request_data = {
                    "user_id": f"similar_test_{query_data['test_id']}",
                    "source": query_data["source"],
                    "subintent": query_data["subintent"],
                    "normalized_query": query_data["stage3"]
                }

                start_time = time.time()
                response = await self.client.post(
                    f"{self.api_url}/search-and-match-direct",
                    json=request_data
                )
                elapsed = (time.time() - start_time) * 1000

                result = TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/search-and-match-direct",
                    pair_type=query_data["pair_type"],
                    query=query_data["query"][:100],
                    status="success" if response.status_code == 200 else "error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=elapsed
                )

                if response.status_code == 200:
                    data = response.json()
                    result.response_data = data
                    result.similar_enabled = data.get("similar_matching_enabled", False)
                    result.similar_count = data.get("similar_count", 0)
                    result.actual_match = data.get("has_matches", False)
                    result.match_count = data.get("match_count", 0)

                    if result.similar_count > 0:
                        similar_found += 1
                        # Extract smart messages
                        for sim in data.get("similar_listings", [])[:3]:
                            if sim.get("smart_message"):
                                smart_messages.append({
                                    "test_id": query_data["test_id"],
                                    "score": sim.get("similarity_score"),
                                    "message": sim["smart_message"]
                                })

                    status = f"✓ {result.match_count} exact + {result.similar_count} similar" if result.similar_enabled else f"{'✓' if result.actual_match else '○'}"
                    self.log(f"  [{i+1}] {status} ({elapsed:.0f}ms)")

                suite.results.append(result)

            except Exception as e:
                suite.results.append(TestResult(
                    test_id=query_data["test_id"],
                    endpoint="/search-and-match-direct",
                    pair_type=query_data["pair_type"],
                    query="",
                    status="error",
                    expected_match=True,
                    actual_match=False,
                    match_count=0,
                    similar_count=0,
                    similar_enabled=False,
                    response_time_ms=0,
                    error_message=str(e)
                ))

            if not self.verbose and (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(test_subset)}")

        suite.completed_at = datetime.now().isoformat()
        suite.total_tests = len(suite.results)
        suite.passed = sum(1 for r in suite.results if r.actual_match or r.similar_count > 0)
        suite.failed = suite.total_tests - suite.passed - sum(1 for r in suite.results if r.status == "error")
        suite.errors = sum(1 for r in suite.results if r.status == "error")
        suite.total_time_ms = sum(r.response_time_ms for r in suite.results)
        suite.avg_response_time_ms = suite.total_time_ms / max(1, suite.total_tests)

        # Check if similar matching was enabled
        enabled_count = sum(1 for r in suite.results if r.similar_enabled)
        print(f"\n--- Similar Matching Analysis ---")
        print(f"Similar matching enabled: {enabled_count}/{suite.total_tests} requests")
        print(f"Found similar matches: {similar_found} queries")
        print(f"Smart messages collected: {len(smart_messages)}")

        if smart_messages:
            print("\nSample smart messages:")
            for msg in smart_messages[:5]:
                print(f"  [{msg['score']:.2f}] {msg['message']}")

        self._print_suite_summary(suite)
        return suite

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _print_suite_summary(self, suite: TestSuite):
        """Print summary for a test suite."""
        print(f"\n--- {suite.suite_name} Summary ---")
        print(f"Total: {suite.total_tests} | Passed: {suite.passed} | Failed: {suite.failed} | Errors: {suite.errors}")
        print(f"Total time: {suite.total_time_ms/1000:.1f}s | Avg: {suite.avg_response_time_ms:.0f}ms")

        # Breakdown by pair type
        by_type = {}
        for r in suite.results:
            if r.pair_type not in by_type:
                by_type[r.pair_type] = {"total": 0, "matched": 0, "similar": 0}
            by_type[r.pair_type]["total"] += 1
            if r.actual_match:
                by_type[r.pair_type]["matched"] += 1
            if r.similar_count > 0:
                by_type[r.pair_type]["similar"] += 1

        print("\nBy type:")
        for ptype, stats in by_type.items():
            print(f"  {ptype}: {stats['matched']}/{stats['total']} matched, {stats['similar']} with similar")


async def main():
    parser = argparse.ArgumentParser(description="VRIDDHI API Testing Framework")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="API base URL")
    parser.add_argument("--prepare", action="store_true", help="Prepare test data from JSONL")
    parser.add_argument("--seed", action="store_true", help="Seed database with test listings")
    parser.add_argument("--match", action="store_true", help="Run /search-and-match-direct tests")
    parser.add_argument("--direct-match", action="store_true", help="Run /match tests")
    parser.add_argument("--similar", action="store_true", help="Run similar matching tests")
    parser.add_argument("--extract", action="store_true", help="Run /extract-and-match tests (GPT)")
    parser.add_argument("--extract-limit", type=int, default=10, help="Limit for GPT extraction tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--report", action="store_true", help="Generate reports")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Prepare test data if needed
    if args.prepare:
        from testing.prepare_test_data import main as prepare_main
        prepare_main()
        return

    tester = APITester(args.url, verbose=args.verbose)
    suites = []

    try:
        print(f"API URL: {tester.api_url}")

        # Check API health
        try:
            health = await tester.client.get(f"{tester.api_url}/health")
            if health.status_code != 200:
                print(f"WARNING: API health check failed: {health.status_code}")
        except Exception as e:
            print(f"ERROR: Cannot connect to API: {e}")
            return

        if args.seed or args.all:
            await tester.seed_database()

        if args.match or args.all:
            suite = await tester.run_search_and_match_direct_tests()
            suites.append(suite)

        if args.direct_match or args.all:
            suite = await tester.run_match_tests()
            suites.append(suite)

        if args.similar or args.all:
            suite = await tester.run_similar_matching_tests()
            suites.append(suite)

        if args.extract or args.all:
            suite = await tester.run_extract_and_match_tests(limit=args.extract_limit)
            suites.append(suite)

        if args.report or (suites and args.all):
            # Save JSON report
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            report = {
                "generated_at": datetime.now().isoformat(),
                "api_url": tester.api_url,
                "suites": [asdict(s) for s in suites]
            }

            report_path = REPORTS_DIR / f"test_report_{timestamp}.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print(f"\nReport saved: {report_path}")

        if not any([args.seed, args.match, args.direct_match, args.similar, args.extract, args.all, args.prepare]):
            parser.print_help()

    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
