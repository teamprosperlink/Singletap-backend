"""
Preprocessor Unit Test Suite

Unit tests for the canonicalization preprocessor module:
- Abbreviation expansion (ac -> air conditioning)
- MWE reduction (barely used -> used)
- Spelling normalization (colour -> color)
- Demonym resolution (indian -> india)
- Compound normalization (second-hand -> secondhand)
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

from tests.utils.test_runner import StandardTestRunner, TestCase

# Import preprocessor functions
from canonicalization.preprocessor import preprocess, normalize_for_registry_lookup


# ============================================================================
# ABBREVIATION EXPANSION TESTS
# ============================================================================

ABBREVIATION_TESTS = [
    {
        "name": "ABBR1: 'ac' -> 'air conditioning'",
        "description": "Common abbreviation expansion",
        "input": "ac",
        "expected": "air conditioning",
    },
    {
        "name": "ABBR2: 'tv' -> 'television'",
        "description": "Common abbreviation expansion",
        "input": "tv",
        "expected": "television",
    },
    {
        "name": "ABBR3: 'pc' -> 'personal computer'",
        "description": "Common abbreviation expansion",
        "input": "pc",
        "expected": "personal computer",
    },
    {
        "name": "ABBR4: 'suv' -> 'sport utility vehicle'",
        "description": "Vehicle abbreviation expansion",
        "input": "suv",
        "expected": "sport utility vehicle",
    },
    {
        "name": "ABBR5: 'ssd' -> 'solid state drive'",
        "description": "Tech abbreviation expansion",
        "input": "ssd",
        "expected": "solid state drive",
    },
]


# ============================================================================
# MWE REDUCTION TESTS
# ============================================================================

MWE_TESTS = [
    {
        "name": "MWE1: 'barely used' -> 'used'",
        "description": "Reduces multi-word expression to core meaning",
        "input": "barely used",
        "expected": "used",
    },
    {
        "name": "MWE2: 'brand new' -> 'new'",
        "description": "Reduces emphasis phrase to core meaning",
        "input": "brand new",
        "expected": "new",
    },
    {
        "name": "MWE3: 'mint condition' -> 'new'",
        "description": "Maps condition phrase to standard term",
        "input": "mint condition",
        "expected": "new",
    },
    {
        "name": "MWE4: 'pre-owned' -> 'used'",
        "description": "Maps euphemism to standard term",
        "input": "pre-owned",
        "expected": "used",
    },
    {
        "name": "MWE5: 'gently used' -> 'used'",
        "description": "Reduces qualified phrase to core meaning",
        "input": "gently used",
        "expected": "used",
    },
]


# ============================================================================
# SPELLING NORMALIZATION TESTS
# ============================================================================

SPELLING_TESTS = [
    {
        "name": "SPELL1: 'colour' -> 'color'",
        "description": "British to American spelling",
        "input": "colour",
        "expected": "color",
    },
    {
        "name": "SPELL2: 'grey' -> 'gray'",
        "description": "British to American spelling",
        "input": "grey",
        "expected": "gray",
    },
    {
        "name": "SPELL3: 'tyre' -> 'tire'",
        "description": "British to American spelling",
        "input": "tyre",
        "expected": "tire",
    },
    {
        "name": "SPELL4: 'aluminium' -> 'aluminum'",
        "description": "British to American spelling",
        "input": "aluminium",
        "expected": "aluminum",
    },
    {
        "name": "SPELL5: 'centre' -> 'center'",
        "description": "British to American spelling",
        "input": "centre",
        "expected": "center",
    },
]


# ============================================================================
# COMPOUND NORMALIZATION TESTS
# ============================================================================

COMPOUND_TESTS = [
    {
        "name": "COMP1: 'second hand' -> 'secondhand' (registry)",
        "description": "Spaces removed for registry lookup",
        "input": "second hand",
        "expected": "secondhand",
        "use_registry_fn": True,
    },
    {
        "name": "COMP2: 'second-hand' -> 'secondhand' (registry)",
        "description": "Hyphens removed for registry lookup",
        "input": "second-hand",
        "expected": "secondhand",
        "use_registry_fn": True,
    },
    {
        "name": "COMP3: 'air_conditioning' -> 'airconditioning' (registry)",
        "description": "Underscores removed for registry lookup",
        "input": "air_conditioning",
        "expected": "airconditioning",
        "use_registry_fn": True,
    },
]


# ============================================================================
# DEMONYM TESTS
# ============================================================================

DEMONYM_TESTS = [
    {
        "name": "DEM1: 'indian' + nationality -> 'india'",
        "description": "Demonym resolved when attribute is nationality",
        "input": "indian",
        "attribute_key": "nationality",
        "expected": "india",
    },
    {
        "name": "DEM2: 'french' + origin -> 'france'",
        "description": "Demonym resolved when attribute is origin",
        "input": "french",
        "attribute_key": "origin",
        "expected": "france",
    },
    {
        "name": "DEM3: 'japanese' + country -> 'japan'",
        "description": "Demonym resolved when attribute is country",
        "input": "japanese",
        "attribute_key": "country",
        "expected": "japan",
    },
    {
        "name": "DEM4: 'indian' + food (no resolution)",
        "description": "Demonym NOT resolved when attribute is not nationality-related",
        "input": "indian",
        "attribute_key": "cuisine",
        "expected": "indian",  # Should stay as 'indian' for cuisine
    },
]


def run_preprocess_test(test_case: dict) -> bool:
    """Run a preprocessor test case."""
    if test_case.get("use_registry_fn"):
        result = normalize_for_registry_lookup(test_case["input"])
    else:
        attribute_key = test_case.get("attribute_key")
        result = preprocess(test_case["input"], attribute_key)

    # Compare result to expected
    expected = test_case["expected"].lower().strip()
    actual = result.lower().strip()

    return actual == expected


def main():
    """Run all preprocessor unit tests with documentation and reporting."""
    output_dir = os.path.dirname(os.path.abspath(__file__))

    runner = StandardTestRunner(
        suite_name="Preprocessor Unit Test Suite",
        suite_purpose="""This test suite validates the canonicalization preprocessor module.

The preprocessor handles Phase 0 of the canonicalization pipeline:
- **Abbreviation Expansion**: ac -> air conditioning, tv -> television
- **MWE Reduction**: barely used -> used, brand new -> new
- **Spelling Normalization**: colour -> color (UK to US)
- **Compound Normalization**: second-hand / second hand -> secondhand
- **Demonym Resolution**: indian + nationality -> india

All transformations are static, deterministic, and require no API calls.""",
        output_dir=output_dir,
        methodology="""The unit test methodology follows standard practices:

1. **Input/Output Testing**:
   - Define input string and attribute key (if applicable)
   - Define expected output
   - Run preprocessor function
   - Compare actual vs expected

2. **Test Categories**:
   - Abbreviations: Static dictionary lookup
   - MWE Reductions: Pattern matching
   - Spelling: UK to US normalization
   - Compounds: Whitespace/hyphen handling
   - Demonyms: Context-aware resolution

3. **Assertion**:
   - Case-insensitive comparison
   - Whitespace trimmed
   - Pass if actual == expected"""
    )

    # Add library dependencies
    runner.add_library("nltk", "3.8+", "WordNetLemmatizer for lemmatization")

    # Add prerequisites
    runner.add_prerequisite("NLTK wordnet data downloaded")

    # Add execution notes
    runner.add_execution_note("All tests run locally without API calls")
    runner.add_execution_note("Tests are deterministic and repeatable")

    # Add all test cases
    all_tests = ABBREVIATION_TESTS + MWE_TESTS + SPELLING_TESTS + COMPOUND_TESTS + DEMONYM_TESTS

    for tc in all_tests:
        runner.add_test(TestCase(
            name=tc["name"],
            description=tc["description"],
            test_fn=lambda t=tc: run_preprocess_test(t),
            expected=True,  # We expect the test to pass
            input_data={"input": tc["input"], "expected": tc["expected"]}
        ))

    # Run tests
    results = runner.run_all(generate_docs=True, generate_reports=True)

    # Print final status
    print("\n" + "="*80)
    if results["failed"] == 0 and results["errors"] == 0:
        print("ALL PREPROCESSOR UNIT TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results['failed']} FAILURES AND {results['errors']} ERRORS")
    print("="*80)

    return results["passed"], results["failed"], results["errors"]


if __name__ == "__main__":
    main()
