"""
E2E Test: Condition Matching Using ACTUAL Codebase Functions.

This test uses the real functions from the codebase to simulate user flow:

1. canonicalization.orchestrator._get_categorical_resolver()
   - Initializes the GenericCategoricalResolver
   - Loads condition_ontology.json into resolver

2. resolver.resolve(value, attribute_key="condition")
   - Resolves condition phrase to OntologyNode
   - Uses synonym_registry (populated from ontology JSON)
   - Falls back to WordNet/BabelNet/Wikidata

3. resolver.is_ancestor(parent, child)
   - Checks if parent is ancestor of child in hierarchy
   - Used for hierarchical matching

4. main.semantic_implies(candidate, required)
   - Full matching logic (exact, synonyms, hierarchy, WordNet, BabelNet)

Test Flow (simulating buyer-seller matching):
- Buyer wants: "used"
- Seller has: 5 different condition phrases (semantically similar, lexically different)
- All should match because they're children of "used" in the hierarchy
"""

import os
import sys
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def run_e2e_test():
    """Run E2E test using actual codebase functions."""
    print("=" * 70)
    print("E2E TEST: Condition Matching Using Codebase Functions")
    print("=" * 70)
    print(f"Test Date: {datetime.now().isoformat()}")
    print()

    # =========================================================================
    # STEP 1: Initialize the Categorical Resolver (loads ontology)
    # =========================================================================
    print("STEP 1: Initialize Categorical Resolver")
    print("-" * 70)

    from canonicalization.orchestrator import _get_categorical_resolver

    resolver = _get_categorical_resolver()
    print(f"  Resolver initialized: {type(resolver).__name__}")
    print(f"  Synonym registry size: {len(resolver._synonym_registry)}")
    print(f"  Concept paths size: {len(resolver._concept_paths)}")
    print()

    # =========================================================================
    # STEP 2: Test condition resolution via resolver.resolve()
    # =========================================================================
    print("STEP 2: Resolve 5 Semantically Similar but Lexically Different Phrases")
    print("-" * 70)

    # Test phrases (all should be under "used" in hierarchy)
    test_phrases = [
        ("gently worn", "very_good", "Ontology synonym for very_good"),
        ("barely touched", "like_new", "Ontology synonym for like_new"),
        ("mint condition", "like_new", "Ontology synonym for like_new"),
        ("fair condition", "acceptable", "Ontology synonym for acceptable"),
        ("excellent condition", "very_good", "Ontology synonym for very_good"),
    ]

    resolution_results = []

    for phrase, expected_concept, description in test_phrases:
        # Resolve using the actual codebase function
        node = resolver.resolve(phrase, attribute_key="condition")

        if node:
            concept_id = node.concept_id
            concept_path = node.concept_path
            source = node.source
            confidence = node.confidence
        else:
            concept_id = None
            concept_path = []
            source = "none"
            confidence = 0.0

        passed = concept_id == expected_concept
        resolution_results.append({
            "phrase": phrase,
            "expected": expected_concept,
            "actual": concept_id,
            "path": concept_path,
            "source": source,
            "confidence": confidence,
            "passed": passed,
        })

        status = "PASS" if passed else "FAIL"
        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Expected: {expected_concept}")
        print(f"  Actual: {concept_id}")
        print(f"  Path: {' -> '.join(concept_path) if concept_path else 'N/A'}")
        print(f"  Source: {source} (confidence: {confidence:.2f})")
        print(f"  Description: {description}")

    print()

    # =========================================================================
    # STEP 3: Test is_ancestor for hierarchical matching
    # =========================================================================
    print("STEP 3: Test is_ancestor() for Hierarchical Matching")
    print("-" * 70)

    # Target: "used" (buyer wants)
    target = "used"
    print(f"\nTarget (Buyer wants): '{target}'")

    ancestor_results = []

    for result in resolution_results:
        if result["actual"]:
            is_anc = resolver.is_ancestor(target, result["actual"])
            ancestor_results.append({
                "phrase": result["phrase"],
                "concept": result["actual"],
                "is_ancestor_of_used": is_anc
            })

            status = "MATCH" if is_anc else "NO MATCH"
            print(f"  is_ancestor('{target}', '{result['actual']}'): {is_anc} [{status}]")

    print()

    # =========================================================================
    # STEP 4: Test semantic_implies (full matching logic)
    # =========================================================================
    print("STEP 4: Test semantic_implies() for Full Matching")
    print("-" * 70)

    try:
        from main import semantic_implies

        print(f"\nUsing semantic_implies from main.py")
        print(f"Buyer wants: '{target}'")
        print()

        implies_results = []

        for result in resolution_results:
            if result["actual"]:
                # Test: does seller's condition imply buyer's requirement?
                seller_has = result["actual"].replace("_", " ")  # like_new -> like new
                implies = semantic_implies(seller_has, target)

                implies_results.append({
                    "phrase": result["phrase"],
                    "canonical": seller_has,
                    "implies_used": implies
                })

                status = "MATCH" if implies else "NO MATCH"
                print(f"  semantic_implies('{seller_has}', '{target}'): {implies} [{status}]")

    except ImportError as e:
        print(f"  Could not import semantic_implies: {e}")
        print("  (This is expected if running without full environment)")
        implies_results = []

    print()

    # =========================================================================
    # STEP 5: Cross-category tests (should NOT match "used")
    # =========================================================================
    print("STEP 5: Cross-Category Tests (Should NOT Match 'used')")
    print("-" * 70)

    cross_tests = [
        ("brand new", "new", False),
        ("factory sealed", "new", False),
        ("needs repair", "damaged", False),
    ]

    cross_results = []

    for phrase, expected_concept, should_match_used in cross_tests:
        node = resolver.resolve(phrase, attribute_key="condition")
        concept_id = node.concept_id if node else None

        if concept_id:
            is_anc = resolver.is_ancestor(target, concept_id)
        else:
            is_anc = False

        passed = (is_anc == should_match_used)
        cross_results.append({
            "phrase": phrase,
            "concept": concept_id,
            "matches_used": is_anc,
            "expected": should_match_used,
            "passed": passed
        })

        status = "PASS" if passed else "FAIL"
        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Concept: {concept_id}")
        print(f"  Matches '{target}': {is_anc} (expected: {should_match_used})")

    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    resolution_passed = sum(1 for r in resolution_results if r["passed"])
    resolution_total = len(resolution_results)

    ancestor_passed = sum(1 for r in ancestor_results if r["is_ancestor_of_used"])
    ancestor_total = len(ancestor_results)

    cross_passed = sum(1 for r in cross_results if r["passed"])
    cross_total = len(cross_results)

    print(f"\nResolution Tests: {resolution_passed}/{resolution_total} passed")
    print(f"Ancestor Tests: {ancestor_passed}/{ancestor_total} matched 'used'")
    print(f"Cross-Category Tests: {cross_passed}/{cross_total} passed")

    total_passed = resolution_passed + cross_passed
    total_tests = resolution_total + cross_total

    print(f"\nOverall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\nALL TESTS PASSED!")
        return True
    else:
        print("\nSOME TESTS FAILED")
        return False


def run_condition_flow_simulation():
    """
    Simulate the actual user flow for condition matching.

    User Flow:
    1. User posts listing: "Selling iPhone, gently worn"
    2. GPT extracts: {"condition": "gently worn"}
    3. Canonicalization: "gently worn" -> "very_good"
    4. Matching: Buyer wants "used", seller has "very_good"
    5. Result: MATCH (very_good is child of used)
    """
    print()
    print("=" * 70)
    print("USER FLOW SIMULATION")
    print("=" * 70)
    print()

    from canonicalization.orchestrator import _get_categorical_resolver

    resolver = _get_categorical_resolver()

    # Simulate 5 different sellers with different condition descriptions
    sellers = [
        {"user": "Seller A", "raw_condition": "gently worn"},
        {"user": "Seller B", "raw_condition": "barely touched"},
        {"user": "Seller C", "raw_condition": "mint condition"},
        {"user": "Seller D", "raw_condition": "fair condition"},
        {"user": "Seller E", "raw_condition": "excellent condition"},
    ]

    # Buyer requirement
    buyer_wants = "used"

    print(f"BUYER: Looking for items in '{buyer_wants}' condition")
    print()
    print("SELLERS:")
    print("-" * 70)

    matches = []

    for seller in sellers:
        raw = seller["raw_condition"]
        user = seller["user"]

        # Step 1: Canonicalize seller's condition
        node = resolver.resolve(raw, attribute_key="condition")
        canonical = node.concept_id if node else raw

        # Step 2: Check hierarchy match
        is_match = resolver.is_ancestor(buyer_wants, canonical) if node else False

        matches.append({
            "user": user,
            "raw": raw,
            "canonical": canonical,
            "match": is_match
        })

        status = "MATCH" if is_match else "NO MATCH"
        print(f"  {user}: \"{raw}\" -> '{canonical}' [{status}]")

    print()
    print("MATCH RESULTS:")
    print("-" * 70)

    matched = [m for m in matches if m["match"]]
    not_matched = [m for m in matches if not m["match"]]

    print(f"  Matched: {len(matched)} sellers")
    for m in matched:
        print(f"    - {m['user']}: {m['raw']} (canonical: {m['canonical']})")

    if not_matched:
        print(f"  Not Matched: {len(not_matched)} sellers")
        for m in not_matched:
            print(f"    - {m['user']}: {m['raw']} (canonical: {m['canonical']})")

    print()
    print("HIERARCHY EXPLANATION:")
    print("-" * 70)
    print("""
  The matching works because of the hierarchical condition ontology:

  condition
  ├── new (eBay: 1000)
  ├── refurbished (eBay: 2000)
  ├── used (eBay: 3000) <- BUYER WANTS THIS
  │   ├── like_new (eBay: 2750) <- "barely touched", "mint condition"
  │   ├── very_good (eBay: 4000) <- "gently worn", "excellent condition"
  │   ├── good (eBay: 5000)
  │   └── acceptable (eBay: 6000) <- "fair condition"
  ├── damaged (eBay: 7000)
  └── for_parts (eBay: 7000)

  All matched sellers have conditions that are CHILDREN of 'used',
  so they satisfy the buyer's requirement (is_ancestor returns True).
""")


if __name__ == "__main__":
    # Run E2E test
    success = run_e2e_test()

    # Run user flow simulation
    run_condition_flow_simulation()

    # Exit with appropriate code
    sys.exit(0 if success else 1)