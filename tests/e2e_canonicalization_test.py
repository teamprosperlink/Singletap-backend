"""
E2E Canonicalization + Matching Tests

Tests the full pipeline:
  GPT-like JSON -> canonicalize_listing -> normalize_and_validate_v2 -> listing_matches_v2

Test matrix:
  1. SAME thing, DIFFERENT words (should match) — True Positives
  2. DIFFERENT things (should NOT match) — True Negatives
  3. Products: buy/sell pairs
  4. Services: seek/provide pairs
  5. Short vs long phrasing
  6. Verify concept_ids after canonicalization
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from canonicalization.orchestrator import canonicalize_listing
from schema.schema_normalizer_v2 import normalize_and_validate_v2
from matching.listing_matcher_v2 import listing_matches_v2


# ============================================================================
# HELPER
# ============================================================================

def semantic_implies(candidate_val: str, required_val: str) -> bool:
    """Exact match + hierarchy check — matches main.py's semantic_implies."""
    from main import semantic_implies as _implies
    return _implies(candidate_val, required_val)


def run_pipeline(listing):
    """Run canonicalize -> normalize -> return OLD schema."""
    canonical = canonicalize_listing(listing)
    normalized = normalize_and_validate_v2(canonical)
    return canonical, normalized


def make_product_listing(subintent, domain, item_type, categorical=None,
                         min_cost=None, max_cost=None, location=None):
    """Create a minimal product listing."""
    item = {
        "type": item_type,
        "categorical": categorical or {},
        "min": {},
        "max": {},
        "range": {}
    }
    if min_cost:
        item["min"] = {"cost": [{"type": "price", "value": min_cost, "unit": "INR"}]}
    if max_cost:
        item["max"] = {"cost": [{"type": "price", "value": max_cost, "unit": "INR"}]}

    return {
        "intent": "product",
        "subintent": subintent,
        "domain": domain if isinstance(domain, list) else [domain],
        "primary_mutual_category": [],
        "items": [item],
        "item_exclusions": [],
        "other_party_preferences": {},
        "other_party_exclusions": [],
        "self_attributes": {},
        "self_exclusions": [],
        "target_location": {"name": location} if location else {},
        "location_match_mode": "explicit" if location else "global",
        "location_exclusions": [],
        "reasoning": ""
    }


def make_service_listing(subintent, domain, item_type, categorical=None,
                         self_attrs=None, other_prefs=None, location=None):
    """Create a minimal service listing."""
    return {
        "intent": "service",
        "subintent": subintent,
        "domain": domain if isinstance(domain, list) else [domain],
        "primary_mutual_category": [],
        "items": [{
            "type": item_type,
            "categorical": categorical or {},
            "min": {},
            "max": {},
            "range": {}
        }],
        "item_exclusions": [],
        "other_party_preferences": other_prefs or {},
        "other_party_exclusions": [],
        "self_attributes": self_attrs or {},
        "self_exclusions": [],
        "target_location": {"name": location} if location else {},
        "location_match_mode": "explicit" if location else "global",
        "location_exclusions": [],
        "reasoning": ""
    }


# ============================================================================
# TEST DATA — PRODUCTS
# ============================================================================

PRODUCT_TESTS = [
    # ---- TRUE POSITIVES: Same thing, different words (should match) ----
    {
        "name": "P1: 'used' vs 'second hand' smartphone",
        "expected_match": True,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="smartphone",
            categorical={"condition": "used", "brand": "apple"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="smartphone",
            categorical={"condition": "second hand", "brand": "apple"},
        ),
    },
    {
        "name": "P2: 'laptop' vs 'notebook' (long form)",
        "expected_match": True,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="laptop",
            categorical={"brand": "dell"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="notebook",
            categorical={"brand": "dell"},
        ),
    },
    {
        "name": "P3: 'red' vs 'scarlet' clothing",
        "expected_match": True,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="fashion",
            item_type="dress",
            categorical={"color": "red"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="fashion",
            item_type="dress",
            categorical={"color": "scarlet"},
        ),
    },
    {
        "name": "P4: 'automobile' vs 'car'",
        "expected_match": True,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="vehicles",
            item_type="automobile",
            categorical={"fuel": "petrol"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="vehicles",
            item_type="car",
            categorical={"fuel": "petrol"},
        ),
    },
    {
        "name": "P5: Exact same terms (baseline)",
        "expected_match": True,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="phone",
            categorical={"brand": "samsung", "condition": "new"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="phone",
            categorical={"brand": "samsung", "condition": "new"},
        ),
    },

    # ---- TRUE NEGATIVES: Different things (should NOT match) ----
    {
        "name": "P6: Different domain (electronics vs furniture)",
        "expected_match": False,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="laptop",
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="furniture",
            item_type="table",
        ),
    },
    {
        "name": "P7: Same domain, different item type",
        "expected_match": False,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="laptop",
            categorical={"brand": "apple"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="refrigerator",
            categorical={"brand": "lg"},
        ),
    },
    {
        "name": "P8: Same item, different brand (buyer wants apple, seller has samsung)",
        "expected_match": False,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="phone",
            categorical={"brand": "apple"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="phone",
            categorical={"brand": "samsung"},
        ),
    },
    {
        "name": "P9: Same subintent (both sellers — should NOT match)",
        "expected_match": False,
        "listing_a": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="phone",
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="phone",
        ),
    },
    {
        "name": "P10: 'new' vs 'used' condition (different conditions)",
        "expected_match": False,
        "listing_a": make_product_listing(
            subintent="buy",
            domain="electronics",
            item_type="phone",
            categorical={"condition": "new"},
        ),
        "listing_b": make_product_listing(
            subintent="sell",
            domain="electronics",
            item_type="phone",
            categorical={"condition": "used"},
        ),
    },
]


# ============================================================================
# TEST DATA — SERVICES
# ============================================================================

SERVICE_TESTS = [
    # ---- TRUE POSITIVES ----
    {
        "name": "S1: 'tutoring' vs 'coaching' (seek/provide)",
        "expected_match": True,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="education",
            item_type="tutoring",
            categorical={"subject": "mathematics"},
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="education",
            item_type="coaching",
            categorical={"subject": "mathematics"},
        ),
    },
    {
        "name": "S2: 'plumber' vs 'plumbing' service",
        "expected_match": True,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="construction & trades",
            item_type="plumber",
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="construction & trades",
            item_type="plumbing",
        ),
    },
    {
        "name": "S3: 'cleaning' vs 'housekeeping'",
        "expected_match": True,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="home services",
            item_type="cleaning",
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="home services",
            item_type="housekeeping",
        ),
    },
    {
        "name": "S4: Exact same service (baseline)",
        "expected_match": True,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="repair & maintenance",
            item_type="electrical repair",
            categorical={"service_type": "home wiring"},
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="repair & maintenance",
            item_type="electrical repair",
            categorical={"service_type": "home wiring"},
        ),
    },

    # ---- TRUE NEGATIVES ----
    {
        "name": "S5: Different service domain (education vs health)",
        "expected_match": False,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="education",
            item_type="tutoring",
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="health",
            item_type="physiotherapy",
        ),
    },
    {
        "name": "S6: Same domain, different service (plumber vs electrician)",
        "expected_match": False,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="construction & trades",
            item_type="plumber",
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="construction & trades",
            item_type="electrician",
        ),
    },
    {
        "name": "S7: Both seekers (same subintent — should NOT match)",
        "expected_match": False,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="education",
            item_type="tutoring",
        ),
        "listing_b": make_service_listing(
            subintent="seek",
            domain="education",
            item_type="tutoring",
        ),
    },
    {
        "name": "S8: Math tutor vs Science tutor (different subjects)",
        "expected_match": False,
        "listing_a": make_service_listing(
            subintent="seek",
            domain="education",
            item_type="tutoring",
            categorical={"subject": "mathematics"},
        ),
        "listing_b": make_service_listing(
            subintent="provide",
            domain="education",
            item_type="tutoring",
            categorical={"subject": "science"},
        ),
    },
]


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_test(test_case):
    """Run a single test case through the full pipeline."""
    name = test_case["name"]
    expected = test_case["expected_match"]

    try:
        # Canonicalize + normalize both listings
        can_a, norm_a = run_pipeline(test_case["listing_a"])
        can_b, norm_b = run_pipeline(test_case["listing_b"])

        # Run matching
        result = listing_matches_v2(norm_a, norm_b, implies_fn=semantic_implies)

        # Determine pass/fail
        passed = result == expected
        status = "PASS" if passed else "FAIL"

        return {
            "name": name,
            "status": status,
            "expected": expected,
            "actual": result,
            "passed": passed,
            "canonical_a": can_a,
            "canonical_b": can_b,
            "normalized_a": norm_a,
            "normalized_b": norm_b,
        }

    except Exception as e:
        import traceback
        return {
            "name": name,
            "status": "ERROR",
            "expected": expected,
            "actual": None,
            "passed": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def print_concept_ids(result):
    """Print key concept_ids from canonical listings for verification."""
    for label, canonical in [("A", result.get("canonical_a")), ("B", result.get("canonical_b"))]:
        if not canonical:
            continue
        items = canonical.get("items", [])
        for i, item in enumerate(items):
            item_type = item.get("type", "?")
            categoricals = item.get("categorical", {})
            cat_str = ", ".join(f"{k}={v}" for k, v in categoricals.items())
            print(f"    {label}.items[{i}]: type={item_type}, {cat_str}")


def main():
    print("=" * 80)
    print("E2E CANONICALIZATION + MATCHING TESTS")
    print("=" * 80)

    all_tests = PRODUCT_TESTS + SERVICE_TESTS
    results = []
    pass_count = 0
    fail_count = 0
    error_count = 0

    for test_case in all_tests:
        print(f"\n--- {test_case['name']} ---")
        print(f"  Expected: {'MATCH' if test_case['expected_match'] else 'NO MATCH'}")

        result = run_test(test_case)
        results.append(result)

        if result["status"] == "ERROR":
            error_count += 1
            print(f"  Result: ERROR - {result['error']}")
            print(f"  {result.get('traceback', '')[:200]}")
        else:
            if result["passed"]:
                pass_count += 1
            else:
                fail_count += 1

            actual_str = "MATCH" if result["actual"] else "NO MATCH"
            print(f"  Result: {actual_str}")
            print(f"  Status: {result['status']}")

            # Print concept_ids for verification
            print_concept_ids(result)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total:  {len(all_tests)}")
    print(f"  Passed: {pass_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Errors: {error_count}")
    print()

    # Print failures in detail
    failures = [r for r in results if not r["passed"]]
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"\n  {f['name']}")
            print(f"    Expected: {'MATCH' if f['expected'] else 'NO MATCH'}")
            print(f"    Actual:   {'MATCH' if f.get('actual') else 'NO MATCH' if f.get('actual') is not None else 'ERROR'}")
            if "error" in f:
                print(f"    Error: {f['error']}")
            else:
                print_concept_ids(f)
    else:
        print("ALL TESTS PASSED!")

    return pass_count, fail_count, error_count


if __name__ == "__main__":
    main()
