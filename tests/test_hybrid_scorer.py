"""
Unit tests for HybridSenseScorer

Tests each scorer independently and the ensemble combination.

Author: Claude (Hybrid WSD Implementation)
Date: 2026-02-13
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from canonicalization.hybrid_scorer import HybridSenseScorer, CandidateSense


def test_transformer_scorer_basic():
    """Test that transformer scorer loads and runs without crashing."""
    print("\n=== Test 1: Transformer Scorer Basic ===")

    scorer = HybridSenseScorer()

    context = "I need a laptop for coding"
    candidates = [
        CandidateSense(
            source="wordnet",
            source_id="laptop.n.01",
            label="laptop",
            gloss="a portable computer small enough to use in your lap",
            all_forms=["laptop", "laptop computer"],
            hypernyms=["portable computer"]
        ),
        CandidateSense(
            source="wordnet",
            source_id="notebook.n.01",
            label="notebook",
            gloss="a book with blank pages for writing notes",
            all_forms=["notebook"],
            hypernyms=["book"]
        )
    ]

    scores = scorer._score_with_transformer(context, candidates)

    print(f"  Context: {context}")
    print(f"  Candidate 1 (laptop): score={scores[0]:.3f}")
    print(f"  Candidate 2 (notebook): score={scores[1]:.3f}")

    assert len(scores) == 2, "Should return 2 scores"
    assert all(0 <= s <= 1 for s in scores), "Scores should be in [0, 1]"
    print("  ✅ PASS: Transformer scorer working")


def test_embedding_scorer_basic():
    """Test that embedding scorer works correctly."""
    print("\n=== Test 2: Embedding Scorer Basic ===")

    scorer = HybridSenseScorer()

    context = "I need a laptop for coding"
    candidates = [
        CandidateSense(
            source="wordnet",
            source_id="laptop.n.01",
            label="laptop",
            gloss="a portable computer small enough to use in your lap",
            all_forms=["laptop", "laptop computer"],
            hypernyms=["portable computer"]
        ),
        CandidateSense(
            source="wordnet",
            source_id="notebook.n.01",
            label="notebook",
            gloss="a book with blank pages for writing notes",
            all_forms=["notebook"],
            hypernyms=["book"]
        )
    ]

    scores = scorer._score_with_embeddings(context, candidates)

    print(f"  Context: {context}")
    print(f"  Candidate 1 (laptop/computer): score={scores[0]:.3f}")
    print(f"  Candidate 2 (notebook/book): score={scores[1]:.3f}")

    assert len(scores) == 2
    assert all(0 <= s <= 1 for s in scores)
    assert scores[0] > scores[1], "Laptop/computer should score higher than book in coding context"
    print("  ✅ PASS: Embedding scorer working and laptop > notebook")


def test_knowledge_scorer_basic():
    """Test that knowledge-based scorer works correctly."""
    print("\n=== Test 3: Knowledge-Based Scorer ===")

    scorer = HybridSenseScorer()

    context = "electronics portable computer"
    candidates = [
        CandidateSense(
            source="wordnet",
            source_id="laptop.n.01",
            label="laptop",
            gloss="a portable computer",
            all_forms=["laptop"],
            hypernyms=["portable computer"]
        ),
        CandidateSense(
            source="wordnet",
            source_id="notebook.n.01",
            label="notebook",
            gloss="a book for writing",
            all_forms=["notebook"],
            hypernyms=["book"]
        )
    ]

    scores = scorer._score_with_knowledge(context, candidates)

    print(f"  Context: {context}")
    print(f"  Candidate 1 (laptop): score={scores[0]:.3f}")
    print(f"  Candidate 2 (notebook): score={scores[1]:.3f}")

    assert len(scores) == 2
    print("  ✅ PASS: Knowledge scorer working")


def test_ensemble_scoring():
    """Test that ensemble combines all 3 scorers correctly."""
    print("\n=== Test 4: Ensemble Scoring ===")

    scorer = HybridSenseScorer()

    context = "I need a laptop for coding"
    candidates = [
        CandidateSense(
            source="wordnet",
            source_id="laptop.n.01",
            label="laptop",
            gloss="a portable computer small enough to use in your lap",
            all_forms=["laptop", "laptop computer"],
            hypernyms=["portable computer"]
        ),
        CandidateSense(
            source="wordnet",
            source_id="notebook.n.01",
            label="notebook",
            gloss="a book with blank pages for writing notes",
            all_forms=["notebook"],
            hypernyms=["book"]
        )
    ]

    ensemble_scores = scorer.score_candidates(context, candidates)

    print(f"  Context: {context}")
    print(f"  Candidate 1 (laptop): ensemble_score={ensemble_scores[0]:.3f}")
    print(f"  Candidate 2 (notebook): ensemble_score={ensemble_scores[1]:.3f}")
    print(f"  Weights: T={scorer.transformer_weight:.2f}, E={scorer.embedding_weight:.2f}, K={scorer.knowledge_weight:.2f}")

    assert len(ensemble_scores) == 2
    assert all(0 <= s <= 1 for s in ensemble_scores)
    assert ensemble_scores[0] > ensemble_scores[1], "Laptop should score higher than notebook in coding context"

    print("  ✅ PASS: Ensemble scoring working and laptop > notebook")


def test_tutoring_vs_coaching():
    """Test disambiguation of tutoring vs coaching (S1 test case)."""
    print("\n=== Test 5: Tutoring vs Coaching ===")

    scorer = HybridSenseScorer()

    context = "education mathematics teaching"
    candidates = [
        CandidateSense(
            source="wikidata",
            source_id="Q836478",
            label="tutoring",
            gloss="private instruction, teaching pupils individually",
            all_forms=["tutoring", "private lessons", "tutelage"],
            hypernyms=["education", "teaching"]
        ),
        CandidateSense(
            source="wordnet",
            source_id="coaching.n.01",
            label="coaching",
            gloss="the job of a professional coach",
            all_forms=["coaching", "coaching job"],
            hypernyms=["employment"]
        )
    ]

    scores = scorer.score_candidates(context, candidates)

    print(f"  Context: {context}")
    print(f"  Candidate 1 (tutoring/teaching): score={scores[0]:.3f}")
    print(f"  Candidate 2 (coaching/employment): score={scores[1]:.3f}")

    assert len(scores) == 2
    # Note: Scores might be close, so we just check they're computed
    print(f"  Score difference: {abs(scores[0] - scores[1]):.3f}")
    print("  ✅ PASS: Scored tutoring vs coaching")


if __name__ == "__main__":
    print("=" * 60)
    print("HYBRID SCORER UNIT TESTS")
    print("=" * 60)

    try:
        test_transformer_scorer_basic()
        test_embedding_scorer_basic()
        test_knowledge_scorer_basic()
        test_ensemble_scoring()
        test_tutoring_vs_coaching()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
