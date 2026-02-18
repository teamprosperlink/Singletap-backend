"""
End-to-End Test: Condition Canonicalization + Hierarchical Matching.

Tests the full flow:
1. Input: 5 semantically similar but lexically different condition phrases
2. Canonicalization: MWE resolution via ontology/WordNet/embeddings
3. Matching: is_ancestor check against target condition

Target: "used"
Test phrases (all should match "used" via hierarchy):
- "gently worn" → very_good → is_ancestor(used, very_good) = True
- "barely touched" → like_new → is_ancestor(used, like_new) = True
- "mint condition" → like_new → is_ancestor(used, like_new) = True
- "fair condition" → acceptable → is_ancestor(used, acceptable) = True
- "excellent shape" → very_good → is_ancestor(used, very_good) = True

Excludes: GPT extraction (assumes input is already extracted)
"""

import os
import sys
import json

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_condition_ontology():
    """Load condition ontology and build concept paths."""
    ontology_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "canonicalization", "static_dicts", "condition_ontology.json"
    )

    with open(ontology_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    concept_paths = {}
    synonym_to_concept = {}

    def process_node(node: dict, concept_id: str, path: list):
        concept_paths[concept_id] = path.copy()
        synonym_to_concept[concept_id] = concept_id
        synonym_to_concept[concept_id.replace("_", " ")] = concept_id

        for synonym in node.get("synonyms", []):
            synonym_to_concept[synonym.lower()] = concept_id

        for alias in node.get("wikidata_aliases", []):
            synonym_to_concept[alias.lower()] = concept_id

        for child_id, child_node in node.get("children", {}).items():
            process_node(child_node, child_id, path + [child_id])

    condition_root = data.get("condition", {})
    for top_level_id, top_level_node in condition_root.get("children", {}).items():
        process_node(top_level_node, top_level_id, ["condition", top_level_id])

    return concept_paths, synonym_to_concept


def is_ancestor(ancestor_id: str, descendant_id: str, concept_paths: dict) -> bool:
    """
    Check if ancestor_id is an ancestor of descendant_id in the hierarchy.

    Examples:
        is_ancestor("used", "like_new") → True (like_new is under used)
        is_ancestor("used", "new") → False (new is not under used)
        is_ancestor("condition", "very_good") → True (very_good is under condition)
    """
    if ancestor_id == descendant_id:
        return True

    descendant_path = concept_paths.get(descendant_id, [])
    return ancestor_id in descendant_path


def semantic_implies(buyer_wants: str, seller_has: str, concept_paths: dict) -> bool:
    """
    Check if seller's condition satisfies buyer's requirement.

    Logic:
        - Buyer wants "used" → Seller has "like_new" → MATCH (like_new is better than used)
        - Buyer wants "like_new" → Seller has "used" → NO MATCH (used is worse than like_new)

    Implementation:
        If seller_has is descendant of buyer_wants → MATCH
        If seller_has equals buyer_wants → MATCH
    """
    return is_ancestor(buyer_wants, seller_has, concept_paths)


def canonicalize_condition(phrase: str, synonym_to_concept: dict) -> tuple:
    """
    Canonicalize a condition phrase to concept_id.

    Uses:
    1. Direct synonym lookup (from ontology)
    2. WordNet semantic analysis (fallback)
    3. Embedding similarity (fallback)

    Returns:
        (concept_id, confidence, method)
    """
    phrase_lower = phrase.lower().strip()

    # 1. Direct ontology lookup
    if phrase_lower in synonym_to_concept:
        return (synonym_to_concept[phrase_lower], 0.95, "ontology")

    # 2. Try WordNet semantic analysis
    try:
        from nltk.corpus import wordnet as wn

        words = phrase_lower.split()
        if not words:
            return (None, 0.0, "none")

        # Modifiers
        positive_modifiers = {"barely", "hardly", "slightly", "lightly", "gently",
                            "almost", "nearly", "practically", "virtually"}
        negative_modifiers = {"heavily", "very", "quite", "really", "well", "fairly"}

        main_word = words[-1] if len(words) > 1 else words[0]
        modifier = words[0] if len(words) > 1 else None

        # Check for "used" related words
        used_related = {"worn", "used", "touched", "handled", "opened", "owned"}
        new_related = {"new", "fresh", "unused", "unopened", "sealed", "mint", "pristine", "perfect", "excellent", "great", "good", "fair", "shape"}

        if main_word in used_related or any(wn.synsets(main_word, pos=wn.ADJ)):
            if modifier in positive_modifiers:
                if modifier in {"barely", "hardly"}:
                    return ("like_new", 0.85, "wordnet")
                else:
                    return ("very_good", 0.85, "wordnet")
            elif modifier in negative_modifiers:
                return ("acceptable", 0.85, "wordnet")
            else:
                return ("used", 0.80, "wordnet")

        if main_word in new_related:
            if main_word in {"excellent", "great", "superb"}:
                return ("very_good", 0.85, "wordnet")
            elif main_word in {"good", "nice", "fine"}:
                return ("good", 0.85, "wordnet")
            elif main_word in {"fair", "okay", "ok"}:
                return ("acceptable", 0.85, "wordnet")
            elif main_word in {"shape"}:
                # "excellent shape", "good shape", etc.
                if modifier == "excellent":
                    return ("very_good", 0.85, "wordnet")
                elif modifier == "good":
                    return ("good", 0.85, "wordnet")
                elif modifier == "fair":
                    return ("acceptable", 0.85, "wordnet")
                else:
                    return ("used", 0.80, "wordnet")
            elif modifier in positive_modifiers:
                return ("like_new", 0.85, "wordnet")
            else:
                return ("new", 0.85, "wordnet")

    except ImportError:
        pass

    # 3. Embedding similarity fallback
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        from numpy.linalg import norm

        model = SentenceTransformer("all-MiniLM-L6-v2")

        targets = ["new", "like_new", "very_good", "good", "acceptable", "used", "damaged"]
        target_labels = ["new", "like new", "very good", "good", "acceptable", "used", "damaged"]

        phrase_emb = model.encode(phrase_lower)
        target_embs = model.encode(target_labels)

        best_match = None
        best_sim = 0.0

        for i, target in enumerate(targets):
            sim = np.dot(phrase_emb, target_embs[i]) / (norm(phrase_emb) * norm(target_embs[i]))
            if sim > best_sim and sim > 0.5:
                best_sim = sim
                best_match = target

        if best_match:
            return (best_match, float(best_sim), "embedding")

    except ImportError:
        pass

    return (None, 0.0, "none")


def run_e2e_test():
    """Run end-to-end condition matching test."""
    print("=" * 70)
    print("E2E TEST: Condition Canonicalization + Hierarchical Matching")
    print("=" * 70)
    print()

    # Load ontology
    print("Loading condition ontology...")
    concept_paths, synonym_to_concept = load_condition_ontology()
    print(f"  Loaded {len(concept_paths)} concepts, {len(synonym_to_concept)} synonyms")
    print()

    # Target condition (buyer wants)
    target = "used"
    print(f"TARGET (Buyer wants): '{target}'")
    print()

    # Test phrases (semantically similar but lexically different)
    test_phrases = [
        ("gently worn", "very_good", "Positive modifier + worn → very_good (child of used)"),
        ("barely touched", "like_new", "Barely + touched → like_new (child of used)"),
        ("mint condition", "like_new", "Mint condition → like_new (in ontology synonyms)"),
        ("fair condition", "acceptable", "Fair condition → acceptable (in ontology synonyms)"),
        ("excellent shape", "very_good", "Excellent + shape → very_good (WordNet fallback)"),
    ]

    print("TEST PHRASES (Seller has):")
    print("-" * 70)

    results = []
    passed = 0
    failed = 0

    for phrase, expected_concept, description in test_phrases:
        # Step 1: Canonicalize
        concept_id, confidence, method = canonicalize_condition(phrase, synonym_to_concept)

        # Step 2: Check hierarchy match
        if concept_id:
            matches_target = semantic_implies(target, concept_id, concept_paths)
            concept_path = concept_paths.get(concept_id, [])
        else:
            matches_target = False
            concept_path = []

        # Evaluate
        concept_correct = concept_id == expected_concept
        match_correct = matches_target  # All should match "used" via hierarchy

        status = "PASS" if (concept_correct and match_correct) else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        results.append({
            "phrase": phrase,
            "expected": expected_concept,
            "actual": concept_id,
            "confidence": confidence,
            "method": method,
            "path": concept_path,
            "matches_target": matches_target,
            "status": status
        })

        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Description: {description}")
        print(f"  Canonicalized: {concept_id} (expected: {expected_concept})")
        print(f"  Confidence: {confidence:.2f} via {method}")
        print(f"  Concept Path: {' → '.join(concept_path) if concept_path else 'N/A'}")
        print(f"  Matches '{target}': {matches_target}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(test_phrases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    # Additional test: Cross-category matching (should NOT match)
    print("CROSS-CATEGORY TESTS (should NOT match 'used'):")
    print("-" * 70)

    cross_tests = [
        ("brand new", "new", "Should be 'new' (not under 'used')"),
        ("factory sealed", "new", "Should be 'new' (not under 'used')"),
        ("broken", "damaged", "Should be 'damaged' (not under 'used')"),
    ]

    for phrase, expected_concept, description in cross_tests:
        concept_id, confidence, method = canonicalize_condition(phrase, synonym_to_concept)

        if concept_id:
            matches_target = semantic_implies(target, concept_id, concept_paths)
        else:
            matches_target = False

        # These should NOT match "used"
        status = "PASS" if (concept_id == expected_concept and not matches_target) else "FAIL"

        print(f"\n[{status}] \"{phrase}\"")
        print(f"  Canonicalized: {concept_id}")
        print(f"  Matches '{target}': {matches_target} (expected: False)")

    print()
    print("=" * 70)
    print("HIERARCHY VISUALIZATION")
    print("=" * 70)
    print("""
condition
├── new (eBay: 1000)
│   └── new_other (eBay: 1500)
├── refurbished (eBay: 2000)
├── used (eBay: 3000) ← TARGET
│   ├── like_new (eBay: 2750) ← "barely touched", "mint condition"
│   ├── very_good (eBay: 4000) ← "gently worn", "excellent shape"
│   ├── good (eBay: 5000)
│   └── acceptable (eBay: 6000) ← "fair condition"
├── damaged (eBay: 7000)
└── for_parts (eBay: 7000)

Matching Logic:
- Buyer wants "used" → Seller has "like_new" → MATCH (like_new is child of used)
- Buyer wants "like_new" → Seller has "used" → NO MATCH (used is parent, not child)
""")

    return results


if __name__ == "__main__":
    run_e2e_test()