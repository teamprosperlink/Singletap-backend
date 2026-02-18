"""
Simple E2E Test: Condition Matching (No External Dependencies)

Demonstrates the hierarchical matching logic with ontology data.
This test uses only the JSON ontology - no WordNet/embeddings required.
"""

import os
import sys
import json

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 70)
    print("SIMPLE E2E TEST: Condition Matching via Ontology")
    print("=" * 70)
    print()

    # Load ontology
    ontology_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "canonicalization", "static_dicts", "condition_ontology.json"
    )

    with open(ontology_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build mappings
    concept_paths = {}
    synonym_to_concept = {}

    def process_node(node: dict, concept_id: str, path: list):
        concept_paths[concept_id] = path.copy()
        synonym_to_concept[concept_id] = concept_id
        synonym_to_concept[concept_id.replace("_", " ")] = concept_id

        for synonym in node.get("synonyms", []):
            synonym_to_concept[synonym.lower()] = concept_id

        for child_id, child_node in node.get("children", {}).items():
            process_node(child_node, child_id, path + [child_id])

    condition_root = data.get("condition", {})
    for top_level_id, top_level_node in condition_root.get("children", {}).items():
        process_node(top_level_node, top_level_id, ["condition", top_level_id])

    print(f"Loaded {len(concept_paths)} concepts, {len(synonym_to_concept)} synonym mappings")
    print()

    # Define is_ancestor function
    def is_ancestor(ancestor_id: str, descendant_id: str) -> bool:
        if ancestor_id == descendant_id:
            return True
        descendant_path = concept_paths.get(descendant_id, [])
        return ancestor_id in descendant_path

    # TARGET: Buyer wants "used"
    target = "used"
    print(f"TARGET (Buyer wants): '{target}'")
    print()

    # Test 5 semantically similar but lexically different phrases
    # All should be in the ontology as synonyms
    test_cases = [
        # (phrase, expected_concept, should_match_target)
        ("gently worn", "very_good", True),       # In very_good synonyms, child of used
        ("barely touched", "like_new", True),     # In like_new synonyms, child of used
        ("mint condition", "like_new", True),     # In like_new synonyms, child of used
        ("fair condition", "acceptable", True),   # In acceptable synonyms, child of used
        ("excellent condition", "very_good", True), # In very_good synonyms, child of used
    ]

    print("=" * 70)
    print("TEST: 5 Semantically Similar but Lexically Different Phrases")
    print("=" * 70)

    passed = 0
    failed = 0

    for phrase, expected_concept, should_match in test_cases:
        phrase_lower = phrase.lower()

        # Canonicalize via ontology lookup
        actual_concept = synonym_to_concept.get(phrase_lower, None)

        # Check match
        if actual_concept:
            matches = is_ancestor(target, actual_concept)
            path = concept_paths.get(actual_concept, [])
        else:
            matches = False
            path = []

        # Evaluate
        concept_ok = actual_concept == expected_concept
        match_ok = matches == should_match

        if concept_ok and match_ok:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Canonicalized: {actual_concept} (expected: {expected_concept})")
        print(f"  Concept Path: {' -> '.join(path)}")
        print(f"  Matches '{target}': {matches} (expected: {should_match})")

    print()
    print("=" * 70)
    print("CROSS-CATEGORY TESTS (Should NOT Match 'used')")
    print("=" * 70)

    cross_tests = [
        ("brand new", "new", False),          # new is not under used
        ("factory sealed", "new", False),     # new is not under used
        ("needs repair", "damaged", False),   # damaged is not under used
    ]

    for phrase, expected_concept, should_match in cross_tests:
        phrase_lower = phrase.lower()
        actual_concept = synonym_to_concept.get(phrase_lower, None)

        if actual_concept:
            matches = is_ancestor(target, actual_concept)
            path = concept_paths.get(actual_concept, [])
        else:
            matches = False
            path = []

        concept_ok = actual_concept == expected_concept
        match_ok = matches == should_match

        if concept_ok and match_ok:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Canonicalized: {actual_concept}")
        print(f"  Matches '{target}': {matches} (expected: {should_match})")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    print()

    # Show hierarchy
    print("CONDITION HIERARCHY (Amazon/eBay Standards):")
    print("-" * 70)
    print("""
condition
├── new (eBay: 1000) - "brand new", "factory sealed", "never used"
│   └── new_other (eBay: 1500) - "new without tags"
├── refurbished (eBay: 2000) - "renewed", "certified refurbished"
├── used (eBay: 3000) - "secondhand", "pre-owned" ← TARGET
│   ├── like_new (eBay: 2750) - "mint condition", "barely touched", "almost new"
│   ├── very_good (eBay: 4000) - "gently worn", "excellent condition", "lightly used"
│   ├── good (eBay: 5000) - "good condition", "well worn", "normal wear"
│   └── acceptable (eBay: 6000) - "fair condition", "heavily used", "very old"
├── damaged (eBay: 7000) - "broken", "defective", "needs repair"
└── for_parts (eBay: 7000) - "for parts only", "salvage"
""")

    print("MATCHING LOGIC:")
    print("-" * 70)
    print("""
is_ancestor(parent, child) checks if child is under parent in hierarchy.

Examples:
  is_ancestor("used", "like_new")  = True  (like_new is child of used)
  is_ancestor("used", "very_good") = True  (very_good is child of used)
  is_ancestor("used", "new")       = False (new is sibling, not child)
  is_ancestor("used", "damaged")   = False (damaged is sibling, not child)

Buyer-Seller Match:
  Buyer wants "used" + Seller has "like_new" → MATCH (like_new implies used)
  Buyer wants "like_new" + Seller has "used" → NO MATCH (used doesn't imply like_new)
""")

    return passed, failed


if __name__ == "__main__":
    passed, failed = main()
    sys.exit(0 if failed == 0 else 1)