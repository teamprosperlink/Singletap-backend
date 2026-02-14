"""
Reverse Hierarchy Test Suite

Tests the critical semantic matching behavior for hierarchy relationships:
- Broad query should match specific items (dog query matches puppy listing)
- Specific query should NOT match broad items (puppy query should NOT match dog listing)

This validates the Wikidata-based hierarchy checking via P31 (instance of) and P279 (subclass of).
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

from canonicalization.orchestrator import canonicalize_listing
from schema.schema_normalizer_v2 import normalize_and_validate_v2
from matching.listing_matcher_v2 import listing_matches_v2

from tests.utils.test_runner import StandardTestRunner, TestCase


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


# ============================================================================
# REVERSE HIERARCHY TEST CASES
# ============================================================================

REVERSE_HIERARCHY_TESTS = [
    # ============ BROAD QUERY -> SPECIFIC ITEMS (Should MATCH) ============

    # RH1: Buyer wants "dog" (broad), seller has "puppy" (specific)
    # Puppy IS a dog, so should match
    {
        "name": "RH1: dog (broad buyer) -> puppy (specific seller) = MATCH",
        "description": "A puppy IS a dog, so buyer wanting dog should match seller with puppy",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "pets", "dog"),
        "listing_b": make_product_listing("sell", "pets", "puppy"),
    },

    # RH2: Buyer wants "doctor" (broad), seller has "dentist" (specific)
    # Dentist IS a type of doctor, so should match
    {
        "name": "RH2: doctor (broad buyer) -> dentist (specific seller) = MATCH",
        "description": "A dentist IS a type of doctor, so buyer wanting doctor should match dentist",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "healthcare", "doctor"),
        "listing_b": make_service_listing("provide", "healthcare", "dentist"),
    },

    # RH3: Buyer wants "book" (broad), seller has "novel" (specific)
    # Novel IS a book, so should match
    {
        "name": "RH3: book (broad buyer) -> novel (specific seller) = MATCH",
        "description": "A novel IS a type of book, so buyer wanting book should match novel",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "books", "book"),
        "listing_b": make_product_listing("sell", "books", "novel"),
    },

    # RH4: Buyer wants "vehicle" (broad), seller has "car" (specific)
    # Car IS a vehicle, so should match
    {
        "name": "RH4: vehicle (broad buyer) -> car (specific seller) = MATCH",
        "description": "A car IS a vehicle, so buyer wanting vehicle should match car",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "vehicles", "vehicle"),
        "listing_b": make_product_listing("sell", "vehicles", "car"),
    },

    # RH5: Buyer wants "smartphone" (broad), seller has "iphone" (specific)
    # iPhone IS a smartphone, so should match
    {
        "name": "RH5: smartphone (broad buyer) -> iphone (specific seller) = MATCH",
        "description": "An iPhone IS a smartphone, so buyer wanting smartphone should match iPhone",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "electronics", "smartphone"),
        "listing_b": make_product_listing("sell", "electronics", "iphone"),
    },

    # ============ SPECIFIC QUERY -> BROAD ITEMS (Should NOT MATCH) ============

    # RH6: Buyer wants "puppy" (specific), seller has "dog" (broad)
    # Not every dog is a puppy, so should NOT match
    {
        "name": "RH6: puppy (specific buyer) -> dog (broad seller) = NO MATCH",
        "description": "Not every dog is a puppy - buyer wants puppy specifically",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "puppy"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # RH7: Buyer wants "dentist" (specific), seller has "doctor" (broad)
    # Not every doctor is a dentist, so should NOT match
    {
        "name": "RH7: dentist (specific buyer) -> doctor (broad seller) = NO MATCH",
        "description": "Not every doctor is a dentist - buyer wants dentist specifically",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "healthcare", "dentist"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
    },

    # RH8: Buyer wants "iphone" (specific), seller has "smartphone" (broad)
    # Not every smartphone is an iPhone, so should NOT match
    {
        "name": "RH8: iphone (specific buyer) -> smartphone (broad seller) = NO MATCH",
        "description": "Not every smartphone is an iPhone - buyer wants iPhone specifically",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "electronics", "iphone"),
        "listing_b": make_product_listing("sell", "electronics", "smartphone"),
    },
]


def run_single_test(test_case: dict) -> bool:
    """Run a single test case and return actual result."""
    can_a, norm_a = run_pipeline(test_case["listing_a"])
    can_b, norm_b = run_pipeline(test_case["listing_b"])
    result = listing_matches_v2(norm_a, norm_b, implies_fn=semantic_implies)
    return result


def main():
    """Run all reverse hierarchy tests with documentation and reporting."""
    output_dir = os.path.dirname(os.path.abspath(__file__))

    runner = StandardTestRunner(
        suite_name="Reverse Hierarchy Test Suite",
        suite_purpose="""This test suite validates the critical hierarchy matching behavior.

The core principle being tested:
- **Broad buyer + Specific seller = MATCH**: If someone wants a "dog", they should see puppies (puppy is a dog)
- **Specific buyer + Broad seller = NO MATCH**: If someone wants a "puppy", a generic "dog" listing doesn't guarantee a puppy

This is implemented using:
1. Wikidata P31 (instance of) and P279 (subclass of) properties
2. BFS traversal through the hierarchy graph
3. Asymmetric matching: `implies(candidate, required)` checks if candidate satisfies required""",
        output_dir=output_dir,
        methodology="""The test methodology validates asymmetric hierarchy matching:

1. **Semantic Direction**:
   - `semantic_implies(candidate, required)` returns True if candidate satisfies required
   - For hierarchy: puppy satisfies dog, but dog does NOT satisfy puppy

2. **Wikidata Integration**:
   - Uses P31 (instance of) and P279 (subclass of) to traverse hierarchy
   - BFS search up to max_depth=3 to find parent-child relationships

3. **Test Pattern**:
   - Each test creates buyer (listing_a) and seller (listing_b)
   - Tests broad-buyer/specific-seller (should match)
   - Tests specific-buyer/broad-seller (should NOT match)

4. **Verification**:
   - Run full pipeline (canonicalize + normalize + match)
   - Compare actual match result against expected"""
    )

    # Add library dependencies
    runner.add_library("requests", "2.28+", "HTTP client for Wikidata SPARQL queries")
    runner.add_library("nltk", "3.8+", "WordNet for fallback hierarchy information")
    runner.add_library("sentence-transformers", "2.2+", "Embedding similarity for disambiguation")

    # Add prerequisites
    runner.add_prerequisite("Internet connection for Wikidata API access")
    runner.add_prerequisite("WordNet data downloaded")
    runner.add_prerequisite("Environment configured (.env file)")

    # Add limitations
    runner.add_limitation("Wikidata hierarchy depth limited to 3 levels")
    runner.add_limitation("Some niche items may not have Wikidata entries")
    runner.add_limitation("First run may be slower due to cache building")

    # Add execution notes
    runner.add_execution_note("Tests validate both directions of hierarchy matching")
    runner.add_execution_note("Results depend on Wikidata's current taxonomy")

    # Convert test cases to TestCase objects
    for tc in REVERSE_HIERARCHY_TESTS:
        runner.add_test(TestCase(
            name=tc["name"],
            description=tc["description"],
            test_fn=lambda t=tc: run_single_test(t),
            expected=tc["expected_match"],
            input_data={
                "listing_a": tc["listing_a"],
                "listing_b": tc["listing_b"]
            }
        ))

    # Run tests
    results = runner.run_all(generate_docs=True, generate_reports=True)

    # Print final status
    print("\n" + "="*80)
    if results["failed"] == 0 and results["errors"] == 0:
        print("ALL REVERSE HIERARCHY TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results['failed']} FAILURES AND {results['errors']} ERRORS")
    print("="*80)

    return results["passed"], results["failed"], results["errors"]


if __name__ == "__main__":
    main()
