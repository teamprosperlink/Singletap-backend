"""
Reverse Hierarchy Test: Broad query should match specific items

Tests the user's exact scenarios:
- "dog" query should match "puppy" listings (puppy is a dog)
- "doctor" query should match "dentist" listings (dentist is a type of doctor)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from canonicalization.orchestrator import canonicalize_listing
from schema.schema_normalizer_v2 import normalize_and_validate_v2
from matching.listing_matcher_v2 import listing_matches_v2


def semantic_implies(candidate_val: str, required_val: str) -> bool:
    from main import semantic_implies as _implies
    return _implies(candidate_val, required_val)


def run_pipeline(listing):
    canonical = canonicalize_listing(listing)
    normalized = normalize_and_validate_v2(canonical)
    return canonical, normalized


def make_product_listing(subintent, domain, item_type):
    return {
        "intent": "product",
        "subintent": subintent,
        "domain": [domain],
        "primary_mutual_category": [],
        "items": [{"type": item_type, "categorical": {}, "min": {}, "max": {}, "range": {}}],
        "item_exclusions": [],
        "other_party_preferences": {},
        "other_party_exclusions": [],
        "self_attributes": {},
        "self_exclusions": [],
        "target_location": {},
        "location_match_mode": "global",
        "location_exclusions": [],
        "reasoning": ""
    }


def make_service_listing(subintent, domain, item_type):
    return {
        "intent": "service",
        "subintent": subintent,
        "domain": [domain],
        "primary_mutual_category": [],
        "items": [{"type": item_type, "categorical": {}, "min": {}, "max": {}, "range": {}}],
        "item_exclusions": [],
        "other_party_preferences": {},
        "other_party_exclusions": [],
        "self_attributes": {},
        "self_exclusions": [],
        "target_location": {},
        "location_match_mode": "global",
        "location_exclusions": [],
        "reasoning": ""
    }


REVERSE_HIERARCHY_TESTS = [
    # ============ BROAD QUERY → SPECIFIC ITEMS (Should MATCH) ============

    # RH1: Buyer wants "dog" (broad), seller has "puppy" (specific)
    # Puppy IS a dog, so should match
    {
        "name": "RH1: dog (broad) → puppy (specific) = MATCH",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "pets", "dog"),
        "listing_b": make_product_listing("sell", "pets", "puppy"),
    },

    # RH2: Buyer wants "doctor" (broad), seller has "dentist" (specific)
    # Dentist IS a type of doctor, so should match
    {
        "name": "RH2: doctor (broad) → dentist (specific) = MATCH",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "healthcare", "doctor"),
        "listing_b": make_service_listing("provide", "healthcare", "dentist"),
    },

    # RH3: Buyer wants "book" (broad), seller has "novel" (specific)
    # Novel IS a book, so should match
    {
        "name": "RH3: book (broad) → novel (specific) = MATCH",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "books", "book"),
        "listing_b": make_product_listing("sell", "books", "novel"),
    },

    # RH4: Buyer wants "vehicle" (broad), seller has "car" (specific)
    # Car IS a vehicle, so should match
    {
        "name": "RH4: vehicle (broad) → car (specific) = MATCH",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "vehicles", "vehicle"),
        "listing_b": make_product_listing("sell", "vehicles", "car"),
    },

    # RH5: Buyer wants "smartphone" (broad), seller has "iphone" (specific)
    # iPhone IS a smartphone, so should match
    {
        "name": "RH5: smartphone (broad) → iphone (specific) = MATCH",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "electronics", "smartphone"),
        "listing_b": make_product_listing("sell", "electronics", "iphone"),
    },

    # ============ SPECIFIC QUERY → BROAD ITEMS (Should NOT MATCH) ============

    # RH6: Buyer wants "puppy" (specific), seller has "dog" (broad)
    # Not every dog is a puppy, so should NOT match
    {
        "name": "RH6: puppy (specific) → dog (broad) = NO MATCH",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "puppy"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # RH7: Buyer wants "dentist" (specific), seller has "doctor" (broad)
    # Not every doctor is a dentist, so should NOT match
    {
        "name": "RH7: dentist (specific) → doctor (broad) = NO MATCH",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "healthcare", "dentist"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
    },

    # RH8: Buyer wants "iphone" (specific), seller has "smartphone" (broad)
    # Not every smartphone is an iPhone, so should NOT match
    {
        "name": "RH8: iphone (specific) → smartphone (broad) = NO MATCH",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "electronics", "iphone"),
        "listing_b": make_product_listing("sell", "electronics", "smartphone"),
    },
]


def run_test(test_case):
    """Run a single test case through the full pipeline."""
    name = test_case["name"]
    expected = test_case["expected_match"]

    try:
        can_a, norm_a = run_pipeline(test_case["listing_a"])
        can_b, norm_b = run_pipeline(test_case["listing_b"])
        result = listing_matches_v2(norm_a, norm_b, implies_fn=semantic_implies)
        passed = result == expected

        return {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "expected": expected,
            "actual": result,
            "passed": passed,
            "type_a": can_a["items"][0]["type"] if can_a.get("items") else "?",
            "type_b": can_b["items"][0]["type"] if can_b.get("items") else "?",
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
        }


def main():
    print("=" * 80)
    print("REVERSE HIERARCHY TEST")
    print("Testing: Broad query → Specific items (should MATCH)")
    print("         Specific query → Broad items (should NOT MATCH)")
    print("=" * 80)

    results = []
    pass_count = 0
    fail_count = 0

    for test_case in REVERSE_HIERARCHY_TESTS:
        print(f"\n--- {test_case['name']} ---")
        result = run_test(test_case)
        results.append(result)

        if result["passed"]:
            pass_count += 1
            print(f"  ✅ PASS")
        else:
            fail_count += 1
            print(f"  ❌ FAIL")
            print(f"     Expected: {'MATCH' if result['expected'] else 'NO MATCH'}")
            print(f"     Actual:   {'MATCH' if result.get('actual') else 'NO MATCH'}")

        if "type_a" in result:
            print(f"     A type: {result['type_a']}, B type: {result['type_b']}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total:  {len(REVERSE_HIERARCHY_TESTS)}")
    print(f"  Passed: {pass_count}")
    print(f"  Failed: {fail_count}")

    if fail_count == 0:
        print("\n✅ ALL REVERSE HIERARCHY TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED - Logic needs adjustment")

    return pass_count, fail_count


if __name__ == "__main__":
    main()
