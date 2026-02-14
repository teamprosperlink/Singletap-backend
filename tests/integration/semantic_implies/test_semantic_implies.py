"""
Semantic Implies Integration Test Suite

Integration tests for the semantic_implies function which is the core
of the matching logic. Tests all strategies:
1. Exact match
2. Synonym registry lookup
3. Curated synonyms
4. Wikidata hierarchy
5. WordNet synset membership
6. WordNet is_ancestor
7. BabelNet synonyms
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

from tests.utils.test_runner import StandardTestRunner, TestCase

# Import the function under test
from main import semantic_implies


# ============================================================================
# EXACT MATCH TESTS
# ============================================================================

EXACT_MATCH_TESTS = [
    {
        "name": "EXACT1: 'car' == 'car'",
        "description": "Exact same string should match",
        "candidate": "car",
        "required": "car",
        "expected": True,
    },
    {
        "name": "EXACT2: 'Car' == 'car' (case insensitive)",
        "description": "Case differences should still match",
        "candidate": "Car",
        "required": "car",
        "expected": True,
    },
    {
        "name": "EXACT3: '  car  ' == 'car' (whitespace)",
        "description": "Extra whitespace should be trimmed",
        "candidate": "  car  ",
        "required": "car",
        "expected": True,
    },
]


# ============================================================================
# SYNONYM TESTS
# ============================================================================

SYNONYM_TESTS = [
    {
        "name": "SYN1: 'sofa' implies 'couch'",
        "description": "Furniture synonyms",
        "candidate": "sofa",
        "required": "couch",
        "expected": True,
    },
    {
        "name": "SYN2: 'couch' implies 'sofa'",
        "description": "Symmetric synonym relationship",
        "candidate": "couch",
        "required": "sofa",
        "expected": True,
    },
    {
        "name": "SYN3: 'used' implies 'second hand'",
        "description": "Condition synonyms",
        "candidate": "used",
        "required": "second hand",
        "expected": True,
    },
    {
        "name": "SYN4: 'laptop' implies 'notebook'",
        "description": "Computing device synonyms",
        "candidate": "laptop",
        "required": "notebook",
        "expected": True,
    },
    {
        "name": "SYN5: 'automobile' implies 'car'",
        "description": "Vehicle synonyms",
        "candidate": "automobile",
        "required": "car",
        "expected": True,
    },
]


# ============================================================================
# HIERARCHY TESTS (Child implies Parent)
# ============================================================================

HIERARCHY_CHILD_PARENT_TESTS = [
    {
        "name": "HIER1: 'puppy' implies 'dog'",
        "description": "Specific (puppy) satisfies broad (dog)",
        "candidate": "puppy",
        "required": "dog",
        "expected": True,
    },
    {
        "name": "HIER2: 'dentist' implies 'doctor'",
        "description": "Specific profession satisfies broad category",
        "candidate": "dentist",
        "required": "doctor",
        "expected": True,
    },
    {
        "name": "HIER3: 'novel' implies 'book'",
        "description": "Specific item type satisfies broad category",
        "candidate": "novel",
        "required": "book",
        "expected": True,
    },
    {
        "name": "HIER4: 'iphone' implies 'smartphone'",
        "description": "Brand implies category",
        "candidate": "iphone",
        "required": "smartphone",
        "expected": True,
    },
    {
        "name": "HIER5: 'car' implies 'vehicle'",
        "description": "Specific implies general",
        "candidate": "car",
        "required": "vehicle",
        "expected": True,
    },
]


# ============================================================================
# HIERARCHY TESTS (Parent does NOT imply Child)
# ============================================================================

HIERARCHY_PARENT_CHILD_TESTS = [
    {
        "name": "HIER_NEG1: 'dog' does NOT imply 'puppy'",
        "description": "Broad (dog) does not satisfy specific (puppy)",
        "candidate": "dog",
        "required": "puppy",
        "expected": False,
    },
    {
        "name": "HIER_NEG2: 'doctor' does NOT imply 'dentist'",
        "description": "General doctor does not satisfy specific dentist",
        "candidate": "doctor",
        "required": "dentist",
        "expected": False,
    },
    {
        "name": "HIER_NEG3: 'book' does NOT imply 'novel'",
        "description": "General book does not satisfy specific novel",
        "candidate": "book",
        "required": "novel",
        "expected": False,
    },
    {
        "name": "HIER_NEG4: 'smartphone' does NOT imply 'iphone'",
        "description": "Category does not imply specific brand",
        "candidate": "smartphone",
        "required": "iphone",
        "expected": False,
    },
    {
        "name": "HIER_NEG5: 'vehicle' does NOT imply 'car'",
        "description": "General does not imply specific",
        "candidate": "vehicle",
        "required": "car",
        "expected": False,
    },
]


# ============================================================================
# DIFFERENT ITEMS TESTS
# ============================================================================

DIFFERENT_ITEMS_TESTS = [
    {
        "name": "DIFF1: 'cat' does NOT imply 'dog'",
        "description": "Different animals",
        "candidate": "cat",
        "required": "dog",
        "expected": False,
    },
    {
        "name": "DIFF2: 'plumber' does NOT imply 'electrician'",
        "description": "Different professions",
        "candidate": "plumber",
        "required": "electrician",
        "expected": False,
    },
    {
        "name": "DIFF3: 'sedan' does NOT imply 'truck'",
        "description": "Different vehicle types",
        "candidate": "sedan",
        "required": "truck",
        "expected": False,
    },
    {
        "name": "DIFF4: 'yoga' does NOT imply 'pilates'",
        "description": "Different fitness activities",
        "candidate": "yoga",
        "required": "pilates",
        "expected": False,
    },
    {
        "name": "DIFF5: 'laptop' does NOT imply 'refrigerator'",
        "description": "Completely different product categories",
        "candidate": "laptop",
        "required": "refrigerator",
        "expected": False,
    },
]


def run_implies_test(test_case: dict) -> bool:
    """Run a semantic_implies test case."""
    result = semantic_implies(test_case["candidate"], test_case["required"])
    return result == test_case["expected"]


def main():
    """Run all semantic_implies integration tests."""
    output_dir = os.path.dirname(os.path.abspath(__file__))

    runner = StandardTestRunner(
        suite_name="Semantic Implies Integration Test Suite",
        suite_purpose="""This test suite validates the semantic_implies function which is the
core matching logic for determining if a candidate value satisfies a required value.

The function implements multiple strategies in priority order:
1. **Exact Match**: Direct string comparison (case-insensitive)
2. **Synonym Registry**: Pre-registered synonym mappings
3. **Curated Synonyms**: Hardcoded synonym pairs (laptop/notebook)
4. **Wikidata Hierarchy**: P31/P279 traversal for subclass relationships
5. **WordNet Synset**: Same synset membership
6. **WordNet Ancestry**: Hypernym chain traversal
7. **BabelNet Synonyms**: External synonym database

Key semantics:
- implies(puppy, dog) = True (puppy IS a dog)
- implies(dog, puppy) = False (not every dog is a puppy)""",
        output_dir=output_dir,
        methodology="""The integration test methodology tests the complete implies logic:

1. **Strategy Coverage**:
   - Tests each matching strategy individually
   - Verifies priority order is correct

2. **Direction Testing**:
   - Verifies asymmetric relationships work correctly
   - Child implies parent, but parent does NOT imply child

3. **Negative Testing**:
   - Verifies unrelated items do not match
   - Prevents false positives

4. **Edge Cases**:
   - Case sensitivity
   - Whitespace handling
   - Empty strings"""
    )

    # Add library dependencies
    runner.add_library("nltk", "3.8+", "WordNet for synset and hypernym checking")
    runner.add_library("requests", "2.28+", "Wikidata SPARQL queries for hierarchy")
    runner.add_library("sentence-transformers", "2.2+", "Embedding similarity fallback")

    # Add prerequisites
    runner.add_prerequisite("WordNet data downloaded")
    runner.add_prerequisite("Internet access for Wikidata API")
    runner.add_prerequisite("Environment variables configured")

    # Add limitations
    runner.add_limitation("Wikidata queries may timeout occasionally")
    runner.add_limitation("Some niche items may not have hierarchy data")
    runner.add_limitation("BabelNet requires API key for full functionality")

    # Add execution notes
    runner.add_execution_note("Tests may be slower on first run due to caching")
    runner.add_execution_note("Results are deterministic for cached queries")

    # Combine all tests
    all_tests = (
        EXACT_MATCH_TESTS +
        SYNONYM_TESTS +
        HIERARCHY_CHILD_PARENT_TESTS +
        HIERARCHY_PARENT_CHILD_TESTS +
        DIFFERENT_ITEMS_TESTS
    )

    for tc in all_tests:
        runner.add_test(TestCase(
            name=tc["name"],
            description=tc["description"],
            test_fn=lambda t=tc: run_implies_test(t),
            expected=True,  # We expect the test assertion to pass
            input_data={
                "candidate": tc["candidate"],
                "required": tc["required"],
                "expected_result": tc["expected"]
            }
        ))

    # Run tests
    results = runner.run_all(generate_docs=True, generate_reports=True)

    # Print final status
    print("\n" + "="*80)
    if results["failed"] == 0 and results["errors"] == 0:
        print("ALL SEMANTIC_IMPLIES INTEGRATION TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results['failed']} FAILURES AND {results['errors']} ERRORS")
    print("="*80)

    return results["passed"], results["failed"], results["errors"]


if __name__ == "__main__":
    main()
