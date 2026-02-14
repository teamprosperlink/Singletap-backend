"""
Ranking Service: Advanced ranking and reranking algorithms.

This module contains ranking algorithms for post-matching result ordering:
- RRF (Reciprocal Rank Fusion) for combining multiple ranking signals
- Ranking Engine for multi-signal ranking pipeline
- Cross-Encoder for pairwise reranking

Note: These are future features not yet integrated into the main pipeline.
"""

from .rrf import reciprocal_rank_fusion, validate_rrf_weights, create_rankings_from_scores
from .cross_encoder_wrapper import CrossEncoderScorer
from .ranking_engine import RankingEngine

__all__ = [
    "reciprocal_rank_fusion",
    "validate_rrf_weights",
    "create_rankings_from_scores",
    "CrossEncoderScorer",
    "RankingEngine",
]
