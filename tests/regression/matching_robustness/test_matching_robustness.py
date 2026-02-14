"""
Matching Robustness Test Suite

Tests the canonicalization + matching pipeline across various domains
to ensure robust handling of:
- Synonyms (sofa/couch, apartment/flat)
- Hyponyms (puppy/dog - specific vs broad)
- Different service types
- Cross-domain disambiguation
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
from tests.utils.report_generator import TestReportGenerator
from tests.utils.doc_generator import TestDocumentationGenerator
from tests.utils.hardware_detector import get_hardware_info, get_infrastructure_info


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
# 20 TEST CASES - DIVERSE DOMAINS
# ============================================================================

ROBUSTNESS_TESTS = [
    # ============ TRUE POSITIVES: Same thing, different words ============

    # R1: Furniture - 'sofa' vs 'couch' (synonyms)
    {
        "name": "R1: 'sofa' vs 'couch' (furniture synonyms)",
        "description": "Tests that sofa and couch are recognized as synonyms",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "furniture", "sofa"),
        "listing_b": make_product_listing("sell", "furniture", "couch"),
    },

    # R2: Real Estate - 'apartment' vs 'flat' (synonyms)
    {
        "name": "R2: 'apartment' vs 'flat' (real estate synonyms)",
        "description": "Tests that apartment and flat are recognized as synonyms",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "real estate", "apartment"),
        "listing_b": make_product_listing("sell", "real estate", "flat"),
    },

    # R3: Pets - 'puppy' vs 'dog' (hyponym - specific buyer, broad seller)
    # Buyer wants specific (puppy), seller has broad (dog) - should NOT match
    {
        "name": "R3: 'puppy' vs 'dog' (specific buyer, broad seller = NO MATCH)",
        "description": "Buyer wants puppy but seller only offers dog (not every dog is a puppy)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "puppy"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # R4: Healthcare - 'physician' vs 'doctor' (synonyms)
    {
        "name": "R4: 'physician' vs 'doctor' (healthcare synonyms)",
        "description": "Tests that physician and doctor are recognized as synonyms",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "healthcare", "physician"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
    },

    # R5: Vehicles - 'bicycle' vs 'bike' (abbreviation)
    {
        "name": "R5: 'bicycle' vs 'bike' (abbreviation synonym)",
        "description": "Tests that bicycle and bike are recognized as the same",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "vehicles", "bicycle"),
        "listing_b": make_product_listing("sell", "vehicles", "bike"),
    },

    # R6: Music - 'guitar' (broad) vs 'acoustic guitar' (specific)
    {
        "name": "R6: 'guitar' buyer vs 'acoustic guitar' seller = MATCH",
        "description": "Broad buyer (guitar) should match specific seller (acoustic guitar)",
        "expected_match": True,
        "listing_a": make_product_listing("buy", "music", "guitar"),
        "listing_b": make_product_listing("sell", "music", "acoustic guitar"),
    },

    # R7: Beauty - 'hairdresser' vs 'hair stylist' (synonyms)
    {
        "name": "R7: 'hairdresser' vs 'hair stylist' (beauty synonyms)",
        "description": "Tests that hairdresser and hair stylist are synonyms",
        "expected_match": True,
        "listing_a": make_service_listing("seek", "beauty", "hairdresser"),
        "listing_b": make_service_listing("provide", "beauty", "hair stylist"),
    },

    # R8: Agriculture - 'farmer' vs 'farm worker' (different roles)
    {
        "name": "R8: 'farmer' vs 'farm worker' (different roles = NO MATCH)",
        "description": "Farmer and farm worker are different roles",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "agriculture", "farmer"),
        "listing_b": make_service_listing("provide", "agriculture", "farm worker"),
    },

    # R9: Books - 'novel' vs 'book' (specific buyer, broad seller)
    {
        "name": "R9: 'novel' vs 'book' (specific buyer, broad seller = NO MATCH)",
        "description": "Buyer wants novel but seller only offers book (not every book is a novel)",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "books", "novel"),
        "listing_b": make_product_listing("sell", "books", "book"),
    },

    # R10: Fitness - 'gym trainer' vs 'fitness instructor' (specific vs broad)
    {
        "name": "R10: 'gym trainer' vs 'fitness instructor' (specific vs broad = NO MATCH)",
        "description": "Gym trainer is specific, fitness instructor is broader",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "fitness", "gym trainer"),
        "listing_b": make_service_listing("provide", "fitness", "fitness instructor"),
    },

    # ============ TRUE NEGATIVES: Different things ============

    # R11: Different pets (cat vs dog)
    {
        "name": "R11: 'cat' vs 'dog' (different pets = NO MATCH)",
        "description": "Cat and dog are completely different pets",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "pets", "cat"),
        "listing_b": make_product_listing("sell", "pets", "dog"),
    },

    # R12: Different trades (carpenter vs painter)
    {
        "name": "R12: 'carpenter' vs 'painter' (different trades = NO MATCH)",
        "description": "Carpenter and painter are different construction trades",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "construction", "carpenter"),
        "listing_b": make_service_listing("provide", "construction", "painter"),
    },

    # R13: Different domains (table furniture vs table reservation)
    {
        "name": "R13: 'table' furniture vs 'table reservation' (different domains = NO MATCH)",
        "description": "Same word but completely different meanings and domains",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "furniture", "table"),
        "listing_b": make_service_listing("seek", "hospitality", "table reservation"),
    },

    # R14: Same item but same subintent (both buyers)
    {
        "name": "R14: Both buyers for sofa (same subintent = NO MATCH)",
        "description": "Two buyers cannot match - need complementary subintents",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "furniture", "sofa"),
        "listing_b": make_product_listing("buy", "furniture", "sofa"),
    },

    # R15: Different fitness types (yoga vs pilates)
    {
        "name": "R15: 'yoga' vs 'pilates' instructor (different specialties = NO MATCH)",
        "description": "Yoga and pilates are different fitness disciplines",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "fitness", "instructor", {"specialty": "yoga"}),
        "listing_b": make_service_listing("provide", "fitness", "instructor", {"specialty": "pilates"}),
    },

    # R16: Same word different context (orange fruit vs orange color)
    {
        "name": "R16: Orange fruit vs Orange t-shirt (different contexts = NO MATCH)",
        "description": "Orange as fruit vs orange as color on t-shirt",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "food", "orange"),
        "listing_b": make_product_listing("sell", "fashion", "t-shirt", {"color": "orange"}),
    },

    # R17: Product vs service (piano vs piano lessons)
    {
        "name": "R17: 'piano' product vs 'piano lessons' service (different intents = NO MATCH)",
        "description": "Buying a piano is different from seeking piano lessons",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "music", "piano"),
        "listing_b": make_service_listing("provide", "education", "piano lessons"),
    },

    # R18: Same service word, different context (driving lessons vs delivery driving)
    {
        "name": "R18: 'driving lessons' vs 'delivery driving' (different services = NO MATCH)",
        "description": "Learning to drive vs providing delivery service",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "education", "driving lessons"),
        "listing_b": make_service_listing("provide", "transportation", "delivery driving"),
    },

    # R19: Different vehicle types (sedan vs truck)
    {
        "name": "R19: 'sedan' vs 'truck' (different vehicle types = NO MATCH)",
        "description": "Sedan and truck are different vehicle categories",
        "expected_match": False,
        "listing_a": make_product_listing("buy", "vehicles", "sedan"),
        "listing_b": make_product_listing("sell", "vehicles", "truck"),
    },

    # R20: Different medical specialists (dentist vs doctor)
    {
        "name": "R20: 'dentist' buyer vs 'doctor' seller (specific vs broad = NO MATCH)",
        "description": "Buyer wants dentist specifically, seller offers general doctor",
        "expected_match": False,
        "listing_a": make_service_listing("seek", "healthcare", "dentist"),
        "listing_b": make_service_listing("provide", "healthcare", "doctor"),
    },
]


def run_single_test(test_case: dict) -> bool:
    """Run a single test case and return actual result."""
    can_a, norm_a = run_pipeline(test_case["listing_a"])
    can_b, norm_b = run_pipeline(test_case["listing_b"])
    result = listing_matches_v2(norm_a, norm_b, implies_fn=semantic_implies)
    return result


def main():
    """Run all robustness tests with documentation and reporting."""
    output_dir = os.path.dirname(os.path.abspath(__file__))

    runner = StandardTestRunner(
        suite_name="Matching Robustness Test Suite",
        suite_purpose="""This test suite validates the robustness of the matching pipeline across diverse domains.

It tests:
1. **Synonym Recognition**: sofa/couch, apartment/flat, physician/doctor
2. **Hyponym Handling**: puppy vs dog (specific vs broad semantics)
3. **Cross-Domain Disambiguation**: table (furniture) vs table (reservation)
4. **Subintent Compatibility**: buy/sell pairs vs same subintent
5. **Categorical Constraints**: yoga vs pilates specialties""",
        output_dir=output_dir,
        methodology="""The test methodology follows a data-driven approach:

1. **Test Case Definition**: Each test defines two listings (A and B) with:
   - Intent (product/service)
   - Subintent (buy/sell, seek/provide)
   - Domain (pets, healthcare, furniture, etc.)
   - Item type and optional categorical constraints

2. **Pipeline Execution**:
   - Canonicalization: Preprocessing, disambiguation, normalization
   - Matching: listing_matches_v2 with semantic_implies function

3. **Expected Behavior**:
   - TRUE POSITIVES: Same/synonymous items with complementary subintents
   - TRUE NEGATIVES: Different items, same subintents, or incompatible categories

4. **Assertion Model**:
   - Expected: Whether listings should match (True/False)
   - Actual: Result from matching pipeline
   - Pass: actual == expected"""
    )

    # Add library dependencies
    runner.add_library("nltk", "3.8+", "Natural language processing and WordNet access")
    runner.add_library("sentence-transformers", "2.2+", "Embedding model for semantic similarity")
    runner.add_library("requests", "2.28+", "HTTP client for Wikidata/BabelNet API calls")
    runner.add_library("numpy", "1.24+", "Numerical operations for cosine similarity")

    # Add prerequisites
    runner.add_prerequisite("WordNet data downloaded via `python -c \"import nltk; nltk.download('wordnet')\"")
    runner.add_prerequisite("Environment variables set: BABELNET_API_KEY (optional)")
    runner.add_prerequisite("Python 3.9+ with project dependencies installed")

    # Add limitations
    runner.add_limitation("BabelNet API has rate limits (1000 requests/day for free tier)")
    runner.add_limitation("Wikidata SPARQL endpoint may have occasional timeouts")
    runner.add_limitation("First run may be slower due to model loading")

    # Add execution notes
    runner.add_execution_note("Tests run in isolation - no shared state between tests")
    runner.add_execution_note("Each test creates fresh listing objects")
    runner.add_execution_note("Results are deterministic for same input data")

    # Convert test cases to TestCase objects
    for tc in ROBUSTNESS_TESTS:
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
        print("ALL ROBUSTNESS TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results['failed']} FAILURES AND {results['errors']} ERRORS")
    print("="*80)

    return results["passed"], results["failed"], results["errors"]


if __name__ == "__main__":
    main()
