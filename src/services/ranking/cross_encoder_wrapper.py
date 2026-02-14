"""
PHASE 3.5: CROSS-ENCODER WRAPPER

Wrapper for cross-encoder reranking using BAAI/bge-reranker models.

Responsibility:
- Score query-candidate pairs using cross-encoder model
- Return scores for TOP-K candidates only (expensive operation)

BAAI Reranker Models:
- BAAI/bge-reranker-base (278M params) - Good quality, reasonable speed
- BAAI/bge-reranker-large (560M params) - Best quality, slower

Design:
- Cross-encoder runs query+candidate through full transformer (expensive)
- Only applied to top-k candidates after initial retrieval
- Provides more accurate relevance scores than bi-encoder similarity

Authority: VRIDDHI Architecture Document
Dependencies: sentence-transformers

Author: Claude (Ranking Engine)
Date: 2026-01-12 (Updated: 2026-02-05)
"""

from typing import List, Dict, Optional
from sentence_transformers import CrossEncoder
import numpy as np


# ============================================================================
# CROSS-ENCODER MODELS
# ============================================================================

# BAAI Reranker models (optimized for retrieval reranking)
# These are specifically trained for query-document relevance scoring
BAAI_RERANKER_BASE = "BAAI/bge-reranker-base"      # 278M params
BAAI_RERANKER_LARGE = "BAAI/bge-reranker-large"    # 560M params

# Legacy model (for backward compatibility)
LEGACY_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Default to BAAI base model
DEFAULT_CROSS_ENCODER_MODEL = BAAI_RERANKER_BASE


class CrossEncoderScorer:
    """
    Cross-encoder model wrapper for pairwise reranking.

    Uses BAAI/bge-reranker models by default for best retrieval performance.

    Usage:
        scorer = CrossEncoderScorer("BAAI/bge-reranker-base")
        scores = scorer.score_pairs("query text", ["candidate 1", "candidate 2"])
    """

    def __init__(self, model_name: str = DEFAULT_CROSS_ENCODER_MODEL):
        """
        Initialize cross-encoder model.

        Args:
            model_name: Hugging Face model name (default: BAAI/bge-reranker-base)
        """
        self.model = CrossEncoder(model_name)
        self.model_name = model_name

    def score_pairs(
        self,
        query_text: str,
        candidate_texts: List[str]
    ) -> np.ndarray:
        """
        Score query-candidate pairs.

        Args:
            query_text: Query text
            candidate_texts: List of candidate texts

        Returns:
            Array of scores (length = len(candidate_texts))
            Higher scores = more relevant
        """
        if not candidate_texts:
            return np.array([])

        # Create pairs: [(query, candidate1), (query, candidate2), ...]
        pairs = [(query_text, candidate_text) for candidate_text in candidate_texts]

        # Score all pairs
        scores = self.model.predict(pairs)

        return scores

    def score_single(self, query_text: str, candidate_text: str) -> float:
        """
        Score a single query-candidate pair.

        Args:
            query_text: Query text
            candidate_text: Candidate text

        Returns:
            Relevance score (higher = more relevant)
        """
        score = self.model.predict([(query_text, candidate_text)])
        return float(score[0])


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def score_with_cross_encoder(
    query_text: str,
    candidates: List[Dict],
    candidate_texts: Dict[str, str],
    cross_encoder: CrossEncoderScorer,
    top_k: Optional[int] = None
) -> Dict[str, float]:
    """
    Score candidates using cross-encoder model.

    Args:
        query_text: Query text (for cross-encoder input)
        candidates: List of candidate listings
        candidate_texts: Dict of listing_id → text (for cross-encoder input)
        cross_encoder: CrossEncoder model wrapper
        top_k: Score only top-k candidates (None = score all)

    Returns:
        Dict of listing_id → cross-encoder score

    Notes:
        - Cross-encoder is expensive (runs both texts through transformer)
        - Should be applied to TOP-K candidates only
        - Returns scores for all candidates that have text
    """
    scores = {}

    # Determine candidates to score
    candidates_to_score = candidates[:top_k] if top_k else candidates

    # Extract texts for scoring
    candidate_ids = []
    texts = []

    for candidate in candidates_to_score:
        listing_id = candidate.get("id") or candidate.get("listing_id")
        if not listing_id:
            continue

        # Get candidate text
        candidate_text = candidate_texts.get(listing_id)
        if not candidate_text:
            # Skip candidates without text
            continue

        candidate_ids.append(listing_id)
        texts.append(candidate_text)

    if not texts:
        # No candidates to score
        return scores

    # Score all pairs
    cross_encoder_scores = cross_encoder.score_pairs(query_text, texts)

    # Map scores to listing IDs
    for listing_id, score in zip(candidate_ids, cross_encoder_scores):
        scores[listing_id] = float(score)

    return scores


def rerank_candidates(
    query_text: str,
    candidates: List[Dict],
    cross_encoder: CrossEncoderScorer,
    text_field: str = "embedding_text",
    top_k: Optional[int] = None
) -> List[Dict]:
    """
    Rerank candidates using cross-encoder and return sorted list.

    Convenience function that:
    1. Extracts text from candidates
    2. Scores with cross-encoder
    3. Sorts by score (descending)
    4. Returns reranked list

    Args:
        query_text: Query text
        candidates: List of candidate dicts (must have listing_id and text)
        cross_encoder: CrossEncoder model wrapper
        text_field: Field name containing candidate text
        top_k: Rerank only top-k candidates

    Returns:
        List of candidates sorted by cross-encoder score (descending)
    """
    # Build candidate texts dict
    candidate_texts = {}
    for candidate in candidates:
        listing_id = candidate.get("id") or candidate.get("listing_id")
        if listing_id and text_field in candidate:
            candidate_texts[listing_id] = candidate[text_field]

    # Score candidates
    scores = score_with_cross_encoder(
        query_text=query_text,
        candidates=candidates,
        candidate_texts=candidate_texts,
        cross_encoder=cross_encoder,
        top_k=top_k
    )

    # Add scores to candidates
    for candidate in candidates:
        listing_id = candidate.get("id") or candidate.get("listing_id")
        candidate["cross_encoder_score"] = scores.get(listing_id, 0.0)

    # Sort by cross-encoder score (descending)
    reranked = sorted(
        candidates,
        key=lambda x: x.get("cross_encoder_score", 0.0),
        reverse=True
    )

    return reranked


# ============================================================================
# UTILITIES
# ============================================================================

def build_cross_encoder_text(listing: Dict) -> str:
    """
    Build text representation for cross-encoder input.

    Uses same logic as embedding text construction for consistency.

    Args:
        listing: Normalized listing object

    Returns:
        Text string for cross-encoder input
    """
    from src.services.embedding import build_embedding_text
    return build_embedding_text(listing)


def create_reranker_from_settings():
    """
    Create a CrossEncoderScorer from centralized settings.

    Returns:
        CrossEncoderScorer or None (if reranking disabled)
    """
    from src.config.settings import settings

    if not settings.use_reranker:
        return None

    return CrossEncoderScorer(settings.reranker_model_name)
