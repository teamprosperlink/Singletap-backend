"""
E2E Canonicalization + Matching Test Suite

Tests the full pipeline from raw GPT-like JSON to final match decision:
  GPT JSON -> canonicalize_listing -> normalize_and_validate_v2 -> listing_matches_v2

Test coverage:
  1. Synonym matching (used/second-hand, laptop/notebook)
  2. Domain filtering (electronics vs furniture)
  3. Subintent compatibility (buy/sell, seek/provide)
  4. Categorical constraints (brand, condition, subject)
  5. Products and Services
"""

import sys
import os

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


def make_product_listing(subintent, domain, item_type, categorical=None,
                         min_cost=None, max_cost=None, location=None):
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
# PRODUCT TEST CASES
# ============================================================================

PRODUCT_TESTS = [
    # ---- TRUE POSITIVES: Same thing, different words ----
    {
        "name": "P1: 'used' vs 'second hand' smartphone",
        "description": "Tests synonym recognition for condition attribute",
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
        "name": "P2: 'laptop' vs 'notebook' (computing devices)",
        "description": "Tests synonym recognition for item types",
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
        "description": "Tests color synonym recognition",
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
        "description": "Tests vehicle synonym recognition",
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
        "description": "Baseline test - identical listings should match",
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

    # ---- TRUE NEGATIVES: Different things ----
    {
        "name": "P6: Different domain (electronics vs furniture)",
        "description": "Different domains should not match",
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
        "description": "Different items in same domain should not match",
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
        "name": "P8: Same item, different brand",
        "description": "Brand mismatch should not match",
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
        "name": "P9: Same subintent (both sellers)",
        "description": "Both sellers cannot match - need complementary subintents",
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
        "name": "P10: 'new' vs 'used' condition",
        "description": "Condition mismatch should not match",
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
# SERVICE TEST CASES
# ============================================================================

SERVICE_TESTS = [
    # ---- TRUE POSITIVES ----
    {
        "name": "S1: 'tutoring' vs 'coaching' (education)",
        "description": "Tests service synonym recognition",
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
        "description": "Tests profession vs service name recognition",
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
        "description": "Tests home service synonyms",
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
        "description": "Baseline - identical services should match",
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
        "name": "S5: Different service domain",
        "description": "Education vs health should not match",
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
        "name": "S6: Same domain, different service",
        "description": "Plumber vs electrician should not match",
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
        "name": "S7: Both seekers (same subintent)",
        "description": "Both seeking cannot match",
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
        "name": "S8: Math tutor vs Science tutor",
        "description": "Subject mismatch should not match",
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


def run_single_test(test_case: dict) -> bool:
    """Run a single test case and return actual result."""
    can_a, norm_a = run_pipeline(test_case["listing_a"])
    can_b, norm_b = run_pipeline(test_case["listing_b"])
    result = listing_matches_v2(norm_a, norm_b, implies_fn=semantic_implies)
    return result


def main():
    """Run all E2E tests with documentation and reporting."""
    output_dir = os.path.dirname(os.path.abspath(__file__))

    runner = StandardTestRunner(
        suite_name="E2E Canonicalization + Matching Test Suite",
        suite_purpose="""This test suite validates the complete end-to-end pipeline from raw JSON listings to final match decisions.

The pipeline stages tested:
1. **Canonicalization**: Converting raw terms to canonical forms
2. **Normalization**: Schema validation and normalization
3. **Matching**: Semantic comparison with implies function

Test categories:
- **Products**: Electronics, vehicles, fashion items
- **Services**: Education, home services, trades
- **True Positives**: Synonyms that should match (used/second-hand, laptop/notebook)
- **True Negatives**: Different items, brands, or subintents that should not match""",
        output_dir=output_dir,
        methodology="""The E2E test methodology validates the complete matching pipeline:

1. **Input Preparation**:
   - Create listing_a (typically buyer/seeker)
   - Create listing_b (typically seller/provider)
   - Define expected match outcome

2. **Pipeline Execution**:
   - Canonicalize: Convert terms to canonical forms
   - Normalize: Validate and normalize schema
   - Match: Run listing_matches_v2 with semantic_implies

3. **Assertion**:
   - Compare actual match result to expected
   - Verify concept_ids are consistent across synonyms

4. **Coverage Areas**:
   - Intent compatibility (product/service)
   - Subintent complementarity (buy/sell, seek/provide)
   - Domain matching
   - Item type synonym resolution
   - Categorical attribute matching"""
    )

    # Add library dependencies
    runner.add_library("nltk", "3.8+", "WordNet access for synonym resolution")
    runner.add_library("sentence-transformers", "2.2+", "Semantic similarity scoring")
    runner.add_library("requests", "2.28+", "External API access (Wikidata, BabelNet)")

    # Add prerequisites
    runner.add_prerequisite("Environment variables configured (.env file)")
    runner.add_prerequisite("WordNet data downloaded")
    runner.add_prerequisite("Python 3.9+ with all dependencies installed")

    # Add limitations
    runner.add_limitation("Requires network access for Wikidata/BabelNet enrichment")
    runner.add_limitation("First run may be slower due to model loading")

    # Combine all tests
    all_tests = PRODUCT_TESTS + SERVICE_TESTS

    # Convert test cases to TestCase objects
    for tc in all_tests:
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
        print("ALL E2E TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results['failed']} FAILURES AND {results['errors']} ERRORS")
    print("="*80)

    return results["passed"], results["failed"], results["errors"]


if __name__ == "__main__":
    main()
