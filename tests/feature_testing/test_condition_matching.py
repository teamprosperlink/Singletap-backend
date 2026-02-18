"""
E2E Test: Condition Matching via /search-and-match-direct Endpoint

Tests 5 semantically similar but lexically different condition phrases:
- "gently worn" -> very_good -> should match "used"
- "barely touched" -> like_new -> should match "used"
- "mint condition" -> like_new -> should match "used"
- "fair condition" -> acceptable -> should match "used"
- "excellent condition" -> very_good -> should match "used"

TRAP:
- "brand new" -> new -> should NOT match "used"

All sellers have iPhone 128GB in Mumbai at prices <= 50k.
Buyer wants: "used" iPhone 128GB, max 50k, Mumbai.

Expected: 5 matches (all semantic variants of "used"), 0 traps.
"""

import json
import requests
from pathlib import Path
import time
import sys

# API Configuration
BASE_URL = "http://localhost:8000"
STORE_LISTING_URL = f"{BASE_URL}/store-listing"
SEARCH_DIRECT_URL = f"{BASE_URL}/search-and-match-direct"

# Test data directory
TEST_DIR = Path(__file__).parent.parent.parent / "test_queries"

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def load_json(filename):
    with open(TEST_DIR / filename, 'r') as f:
        return json.load(f)


def store_listing(listing_json, user_id):
    """Store a listing in the database."""
    payload = {"listing_json": listing_json, "user_id": user_id, "match_id": None}
    response = requests.post(STORE_LISTING_URL, json=payload)
    response.raise_for_status()
    return response.json()


def search_direct(query_json, user_id):
    """Search using pre-formatted query JSON (bypass GPT)."""
    payload = {"listing_json": query_json, "user_id": user_id}
    response = requests.post(SEARCH_DIRECT_URL, json=payload)
    response.raise_for_status()
    return response.json()


def print_header(title):
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")


def print_section(title):
    print(f"\n{CYAN}{'-'*60}{RESET}")
    print(f"{CYAN}{title}{RESET}")
    print(f"{CYAN}{'-'*60}{RESET}")


def print_success(message):
    print(f"{GREEN}[PASS] {message}{RESET}")


def print_fail(message):
    print(f"{RED}[FAIL] {message}{RESET}")


def print_info(message):
    print(f"{YELLOW}[INFO] {message}{RESET}")


def run_condition_matching_test():
    """
    Test condition matching using the actual /search-and-match-direct endpoint.

    This simulates the real user flow:
    1. Sellers store listings with various condition descriptions
    2. Buyer searches for "used" condition
    3. Matching engine canonicalizes conditions and uses is_ancestor matching
    4. All semantic variants of "used" should match
    """
    print_header("E2E TEST: Condition Matching via /search-and-match-direct")

    results = {"total": 0, "passed": 0, "failed": 0}

    # =========================================================================
    # PHASE 1: Store seller listings with different condition phrases
    # =========================================================================
    print_section("PHASE 1: Storing Seller Listings (5 conditions + 1 trap)")

    sellers = [
        # Expected to match "used"
        ("condition_seller_gently_worn.json", "seller-gently-worn", "gently worn", True),
        ("condition_seller_barely_touched.json", "seller-barely-touched", "barely touched", True),
        ("condition_seller_mint_condition.json", "seller-mint-condition", "mint condition", True),
        ("condition_seller_fair_condition.json", "seller-fair-condition", "fair condition", True),
        ("condition_seller_excellent_condition.json", "seller-excellent-condition", "excellent condition", True),
        # TRAP: Should NOT match "used"
        ("condition_trap_brand_new.json", "seller-brand-new-trap", "brand new (TRAP)", False),
    ]

    stored_sellers = {}
    expected_matches = []
    expected_non_matches = []

    for filename, user_id, condition_desc, should_match in sellers:
        try:
            listing_json = load_json(filename)
            result = store_listing(listing_json, user_id)
            stored_sellers[user_id] = {
                "listing_id": result["listing_id"],
                "condition": condition_desc,
                "should_match": should_match
            }
            print_info(f"Stored: {condition_desc} -> {user_id}")

            if should_match:
                expected_matches.append(user_id)
            else:
                expected_non_matches.append(user_id)

        except FileNotFoundError:
            print_fail(f"File not found: {filename}")
            return results
        except Exception as e:
            print_fail(f"Failed to store {filename}: {e}")
            return results

    print_info(f"Stored {len(stored_sellers)} sellers")
    print_info(f"Expected matches: {len(expected_matches)}")
    print_info(f"Expected traps (non-matches): {len(expected_non_matches)}")

    # Wait for indexing
    print_info("Waiting for indexing...")
    time.sleep(3)

    # =========================================================================
    # PHASE 2: Search with buyer wanting "used" condition
    # =========================================================================
    print_section("PHASE 2: Buyer Search (wants 'used' condition)")

    try:
        buyer_query = load_json("condition_buyer_wants_used.json")
        print_info("Buyer: Looking for 'used' iPhone, 128GB+, max 50k, Mumbai")
        print_info("Canonicalization: 'used' -> used (root condition)")
        print_info("Matching: is_ancestor('used', seller_condition) = ?")

        search_result = search_direct(buyer_query, "buyer-wants-used")
        matches = search_result.get("matches", [])

        print_info(f"Search returned {len(matches)} matches")

    except FileNotFoundError:
        print_fail("Buyer query file not found")
        return results
    except Exception as e:
        print_fail(f"Search failed: {e}")
        return results

    # =========================================================================
    # PHASE 3: Verify matches
    # =========================================================================
    print_section("PHASE 3: Verifying Matches")

    # Extract user_ids from matches
    matched_user_ids = set()
    for match in matches:
        if isinstance(match, str):
            matched_user_ids.add(match)
        elif isinstance(match, dict):
            matched_user_ids.add(match.get("user_id"))

    print_info(f"Matched user_ids: {matched_user_ids}")

    # Check expected matches
    print("\nExpected Matches (should match 'used'):")
    for user_id in expected_matches:
        results["total"] += 1
        seller_info = stored_sellers[user_id]
        condition = seller_info["condition"]

        if user_id in matched_user_ids:
            print_success(f"'{condition}' -> MATCHED 'used' (is_ancestor check passed)")
            results["passed"] += 1
        else:
            print_fail(f"'{condition}' -> DID NOT MATCH 'used' (should have matched)")
            results["failed"] += 1

    # Check traps (should NOT match)
    print("\nTraps (should NOT match 'used'):")
    for user_id in expected_non_matches:
        results["total"] += 1
        seller_info = stored_sellers[user_id]
        condition = seller_info["condition"]

        if user_id not in matched_user_ids:
            print_success(f"'{condition}' -> DID NOT MATCH 'used' (correctly rejected)")
            results["passed"] += 1
        else:
            print_fail(f"'{condition}' -> MATCHED 'used' (should NOT have matched)")
            results["failed"] += 1

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_header("TEST SUMMARY")

    print(f"Total Tests: {results['total']}")
    print(f"{GREEN}Passed: {results['passed']}{RESET}")
    print(f"{RED}Failed: {results['failed']}{RESET}")

    print("\nHierarchy Explanation:")
    print("""
    condition
    ├── new (eBay: 1000) <- "brand new" (TRAP - not under "used")
    ├── refurbished (eBay: 2000)
    ├── used (eBay: 3000) <- BUYER WANTS THIS
    │   ├── like_new (eBay: 2750) <- "barely touched", "mint condition"
    │   ├── very_good (eBay: 4000) <- "gently worn", "excellent condition"
    │   ├── good (eBay: 5000)
    │   └── acceptable (eBay: 6000) <- "fair condition"
    ├── damaged (eBay: 7000)
    └── for_parts (eBay: 7000)

    is_ancestor("used", "like_new") = True  -> MATCH
    is_ancestor("used", "very_good") = True -> MATCH
    is_ancestor("used", "acceptable") = True -> MATCH
    is_ancestor("used", "new") = False -> NO MATCH (trap)
    """)

    if results["failed"] == 0:
        print(f"\n{GREEN}ALL TESTS PASSED!{RESET}")
        return results
    else:
        print(f"\n{RED}{results['failed']} TESTS FAILED{RESET}")
        return results


if __name__ == "__main__":
    try:
        # Check server health
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print(f"{GREEN}Server running at {BASE_URL}{RESET}\n")

        # Run test
        results = run_condition_matching_test()
        sys.exit(0 if results["failed"] == 0 else 1)

    except requests.exceptions.ConnectionError:
        print(f"{RED}Server not running! Start with: uvicorn main:app --reload{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Test failed: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)