"""
Robustness Test: 20 Additional Diverse Test Cases

Tests the canonicalization + matching pipeline across various domains
beyond the core E2E tests (electronics, fashion, education, trades).

Domains covered:
- Food & Cuisine
- Real Estate & Rentals
- Pets & Animals
- Sports & Fitness
- Healthcare & Medical
- Transportation
- Agriculture & Farming
- Beauty & Personal Care
- Books & Literature
- Music & Instruments
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


def make_product_listing(subintent, domain, item_type, categorical=None):
    return {
        "intent": "product",
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
        "other_party_preferences": {},
        "other_party_exclusions": [],
        "self_attributes": {},
        "self_exclusions": [],
        "target_location": {},
        "location_match_mode": "global",
        "location_exclusions": [],
        "reasoning": ""
    }


def make_service_listing(subintent, domain, item_type, categorical=None):
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
        "other_party_preferences": {},
        "other_party_exclusions": [],
        "self_attributes": {},
        "self_exclusions": [],
        "target_location": {},
        "location_match_mode": "global",
        "location_exclusions": [],
        "reasoning": ""
    }


# ============================================================================
# 20 NEW TEST CASES - DIVERSE DOMAINS
# ============================================================================

ROBUSTNESS_TESTS = [
    # ============ TRUE POSITIVES: Same thing, different words ============

    # R1: Food domain - 'sofa' vs 'couch' (furniture synonyms)
    {
        "name": "R1: 'sofa' vs 'couch' (furniture)",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "furniture", "sofa"),
        "listing_b": make_product_listing("sell", "furniture", "couch"),
    },

    # R2: Real Estate - 'apartment' vs 'flat' (housing synonyms)
    {
        "name": "R2: 'apartment' vs 'flat' (real estate)",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "real estate", "apartment"),
        "listing_b": make_product_listing("sell", "real estate", "flat"),
    },

    # R3: Pets - 'puppy' vs 'dog' (hyponym relationship)
    # Buyer wants specific (puppy), seller has broad (dog) - should NOT match
    # Because: not every dog is a puppy
    {
        "name": "R3: 'puppy' vs 'dog' (pets - specific→broad NO MATCH)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "puppy"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # R4: Sports - 'physician' vs 'doctor' (medical synonyms)
    {
        "name": "R4: 'physician' vs 'doctor' (healthcare service)",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "healthcare", "physician"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
    },

    # R5: Transportation - 'bicycle' vs 'bike' (common abbreviation)
    {
        "name": "R5: 'bicycle' vs 'bike' (vehicles)",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "vehicles", "bicycle"),
        "listing_b": make_product_listing("sell", "vehicles", "bike"),
    },

    # R6: Music - 'guitar' vs 'acoustic guitar' (specific vs general)
    {
        "name": "R6: 'guitar' (buyer) vs 'acoustic guitar' (seller)",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "music", "guitar"),
        "listing_b": make_product_listing("sell", "music", "acoustic guitar"),
    },

    # R7: Beauty - 'hairdresser' vs 'hair stylist' (service synonyms)
    {
        "name": "R7: 'hairdresser' vs 'hair stylist' (beauty)",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "beauty", "hairdresser"),
        "listing_b": make_service_listing("provide", "beauty", "hair stylist"),
    },

    # R8: Agriculture - 'farm worker' vs 'farmer' (different roles)
    # Farmer (owns/manages) vs Farm worker (employed on farm) - different roles
    # This follows the pattern: not every farm worker is a farmer
    {
        "name": "R8: 'farmer' vs 'farm worker' (different roles - NO MATCH)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "agriculture", "farmer"),
        "listing_b": make_service_listing("provide", "agriculture", "farm worker"),
    },

    # R9: Books - 'novel' vs 'book' (hyponym relationship)
    # Buyer wants specific (novel), seller has broad (book) - should NOT match
    # Because: not every book is a novel
    {
        "name": "R9: 'novel' vs 'book' (literature - specific→broad NO MATCH)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "books", "novel"),
        "listing_b": make_product_listing("sell", "books", "book"),
    },

    # R10: Fitness - 'gym trainer' vs 'fitness instructor' (service synonyms)
    # Buyer wants specific (gym trainer), seller has broad (fitness instructor) - should NOT match
    # Because: not every fitness instructor is a gym trainer (could be yoga, pilates, etc.)
    {
        "name": "R10: 'gym trainer' vs 'fitness instructor' (specific→broad NO MATCH)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "fitness", "gym trainer"),
        "listing_b": make_service_listing("provide", "fitness", "fitness instructor"),
    },

    # ============ TRUE NEGATIVES: Different things ============

    # R11: Same domain, different items (cat vs dog)
    {
        "name": "R11: 'cat' vs 'dog' (different pets)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "cat"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # R12: Same domain, different services (plumber vs carpenter)
    {
        "name": "R12: 'carpenter' vs 'painter' (different trades)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "construction", "carpenter"),
        "listing_b": make_service_listing("provide", "construction", "painter"),
    },

    # R13: Different domains entirely (food vs furniture)
    {
        "name": "R13: 'table' (furniture) vs 'table' (restaurant booking)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "furniture", "table"),
        "listing_b": make_service_listing("seek", "hospitality", "table reservation"),
    },

    # R14: Same item, different subintent (both buyers)
    {
        "name": "R14: Both buyers for sofa (same subintent)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "furniture", "sofa"),
        "listing_b": make_product_listing("buy", "furniture", "sofa"),
    },

    # R15: Same service, different categorical (yoga vs pilates)
    {
        "name": "R15: 'yoga' vs 'pilates' instructor (different fitness types)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "fitness", "instructor", {"specialty": "yoga"}),
        "listing_b": make_service_listing("provide", "fitness", "instructor", {"specialty": "pilates"}),
    },

    # R16: Similar words but different meanings (orange fruit vs orange color)
    {
        "name": "R16: Orange (fruit) vs Orange (t-shirt color)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "food", "orange"),
        "listing_b": make_product_listing("sell", "fashion", "t-shirt", {"color": "orange"}),
    },

    # R17: Piano (instrument) vs Piano lessons (service)
    {
        "name": "R17: 'piano' (product) vs 'piano lessons' (service)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "music", "piano"),
        "listing_b": make_service_listing("provide", "education", "piano lessons"),
    },

    # R18: Same service, different domain context
    {
        "name": "R18: 'driving' (lessons) vs 'driving' (delivery service)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "education", "driving lessons"),
        "listing_b": make_service_listing("provide", "transportation", "delivery driving"),
    },

    # R19: Specific vs unrelated specific (sedan vs truck)
    {
        "name": "R19: 'sedan' vs 'truck' (different vehicle types)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "vehicles", "sedan"),
        "listing_b": make_product_listing("sell", "vehicles", "truck"),
    },

    # R20: Similar category but different (dentist vs doctor)
    {
        "name": "R20: 'dentist' vs 'doctor' (different medical specialists)",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "healthcare", "dentist"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
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
            "canonical_a": can_a,
            "canonical_b": can_b,
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
    """Print key concept_ids from canonical listings."""
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
    print("ROBUSTNESS TEST: 20 ADDITIONAL DIVERSE TEST CASES")
    print("=" * 80)

    results = []
    pass_count = 0
    fail_count = 0
    error_count = 0

    for test_case in ROBUSTNESS_TESTS:
        print(f"\n--- {test_case['name']} ---")
        print(f"  Expected: {'MATCH' if test_case['expected_match'] else 'NO MATCH'}")

        result = run_test(test_case)
        results.append(result)

        if result["status"] == "ERROR":
            error_count += 1
            print(f"  Result: ERROR - {result['error']}")
        else:
            if result["passed"]:
                pass_count += 1
            else:
                fail_count += 1
            actual_str = "MATCH" if result["actual"] else "NO MATCH"
            print(f"  Result: {actual_str}")
            print(f"  Status: {result['status']}")
            print_concept_ids(result)

    # Summary
    print("\n" + "=" * 80)
    print("ROBUSTNESS TEST SUMMARY")
    print("=" * 80)
    total = len(ROBUSTNESS_TESTS)
    print(f"  Total:   {total}")
    print(f"  Passed:  {pass_count} ({100*pass_count/total:.1f}%)")
    print(f"  Failed:  {fail_count}")
    print(f"  Errors:  {error_count}")

    # Breakdown by type (dynamic based on expected_match)
    tp_tests = [(t, r) for t, r in zip(ROBUSTNESS_TESTS, results) if t["expected_match"]]
    tn_tests = [(t, r) for t, r in zip(ROBUSTNESS_TESTS, results) if not t["expected_match"]]
    tp_pass = sum(1 for _, r in tp_tests if r["passed"])
    tn_pass = sum(1 for _, r in tn_tests if r["passed"])
    print(f"\n  True Positives (should match):   {tp_pass}/{len(tp_tests)}")
    print(f"  True Negatives (should NOT match): {tn_pass}/{len(tn_tests)}")

    # Print failures
    failures = [r for r in results if not r["passed"]]
    if failures:
        print("\n" + "-" * 40)
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
        print("\nALL 20 ROBUSTNESS TESTS PASSED!")

    return pass_count, fail_count, error_count


if __name__ == "__main__":
    main()
