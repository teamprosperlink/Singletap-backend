"""
Core Matching Module: Multi-phase boolean matching logic.

This module orchestrates the complete matching pipeline:
- Intent/Domain gates
- Item array matching
- Other/Self attribute matching
- Mutual category matching
- Location matching
- Similar matching (when enabled)
"""

from .orchestrator import listing_matches_v2
from .item_matchers import item_matches
from .item_array_matchers import all_required_items_match
from .other_self_matchers import match_other_to_self
from .mutual_matcher import mutual_listing_matches
from .location_matcher import match_location_v2
from .similarity_scorer import (
    evaluate_similarity,
    SimilarityResult,
    ConstraintResult,
    ConstraintType
)

__all__ = [
    "listing_matches_v2",
    "item_matches",
    "all_required_items_match",
    "match_other_to_self",
    "mutual_listing_matches",
    "match_location_v2",
    # Similar matching
    "evaluate_similarity",
    "SimilarityResult",
    "ConstraintResult",
    "ConstraintType"
]
