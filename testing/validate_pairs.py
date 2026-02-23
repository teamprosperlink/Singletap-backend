"""
VRIDDHI API TESTING - Pair Validation Script

Purpose: Pre-validate test pairs using the /match endpoint to determine
which pairs should actually match vs not match.

This creates:
- Pairs that SHOULD match (for positive test cases)
- Pairs that SHOULD NOT match (for negative test cases)

Author: Claude
Date: 2025-02-23
"""

import json
import asyncio
import httpx
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict

# Configuration
TEST_DATA_DIR = Path(__file__).parent / "test_data"
API_URL = "https://singletap-backend.onrender.com"
REQUEST_TIMEOUT = 30.0


async def validate_pair(client: httpx.AsyncClient, pair: Dict) -> Tuple[bool, Dict]:
    """
    Validate a pair using the /match endpoint.
    Returns (is_match, response_data)
    """
    seed = pair["seed_entry"]
    query = pair["query_entry"]

    # Build match request
    # The seed is the seller/provider (listing_b)
    # The query is the buyer/seeker (listing_a)
    request_data = {
        "listing_a": query["stage3"],
        "listing_b": seed["stage3"]
    }

    try:
        response = await client.post(
            f"{API_URL}/match",
            json=request_data,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            is_match = data.get("match", False)
            return is_match, data
        else:
            return False, {"error": response.text[:200]}

    except Exception as e:
        return False, {"error": str(e)}


async def validate_all_pairs():
    """Validate all pairs and update expected_match field."""

    print("=" * 60)
    print("VRIDDHI API TESTING - Pair Validation")
    print("=" * 60)
    print(f"API: {API_URL}")

    # Load pairs
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
                all_pairs.append((filename, pairs))

    async with httpx.AsyncClient() as client:
        # Test API health
        try:
            health = await client.get(f"{API_URL}/ping")
            if health.status_code != 200:
                print(f"ERROR: API not responding")
                return
            print(f"API Status: OK\n")
        except Exception as e:
            print(f"ERROR: Cannot connect to API: {e}")
            return

        # Validate each file
        for filename, pairs in all_pairs:
            print(f"\n--- Validating {filename} ({len(pairs)} pairs) ---")

            match_count = 0
            no_match_count = 0
            error_count = 0

            for i, pair in enumerate(pairs):
                is_match, response = await validate_pair(client, pair)

                if "error" in response:
                    error_count += 1
                    pair["expected_match"] = False
                    pair["validation_error"] = response["error"]
                else:
                    pair["expected_match"] = is_match
                    pair["validation_response"] = response

                    if is_match:
                        match_count += 1
                    else:
                        no_match_count += 1

                # Progress
                if (i + 1) % 10 == 0:
                    print(f"  Progress: {i+1}/{len(pairs)} (matches: {match_count}, no-match: {no_match_count})")

            # Save updated pairs
            with open(TEST_DATA_DIR / filename, "w", encoding="utf-8") as f:
                json.dump(pairs, f, indent=2, ensure_ascii=False)

            print(f"  Results: {match_count} matches, {no_match_count} no-match, {error_count} errors")

    # Summary
    print("\n" + "=" * 60)
    print("Validation Complete!")
    print("=" * 60)
    print("\nPairs have been updated with expected_match field.")
    print("Now you can run tests and compare actual vs expected results.")


def analyze_current_pairs():
    """Analyze current pairs to show what we have."""
    print("\n=== Current Pair Analysis ===\n")

    for filename in ["product_pairs.json", "service_pairs.json", "mutual_pairs.json"]:
        filepath = TEST_DATA_DIR / filename
        if not filepath.exists():
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            pairs = json.load(f)

        print(f"{filename}:")
        print(f"  Total pairs: {len(pairs)}")

        # Sample first 3 pairs
        print(f"  Sample pairs:")
        for i, pair in enumerate(pairs[:3]):
            seed = pair["seed_entry"]
            query = pair["query_entry"]

            seed_type = seed["stage3"].get("items", [{}])[0].get("type", "?") if seed["stage3"].get("items") else "?"
            query_type = query["stage3"].get("items", [{}])[0].get("type", "?") if query["stage3"].get("items") else "?"

            print(f"    {i+1}. Seed: {seed['subintent']} {seed_type}")
            print(f"       Query: {query['subintent']} {query_type}")
            print(f"       Same type? {seed_type == query_type}")
        print()


if __name__ == "__main__":
    # First analyze what we have
    analyze_current_pairs()

    # Then validate
    print("\nStarting validation against API...")
    asyncio.run(validate_all_pairs())
