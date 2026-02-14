"""
Retrieval Service: Candidate selection using SQL and vector search.

Provides functions for:
- SQL filtering via Supabase
- Qdrant vector search with payload filters
- Combined retrieval of candidate listing IDs
"""

from .service import (
    sql_filter_product_service,
    sql_filter_mutual,
    qdrant_search_product_service,
    qdrant_search_mutual,
    retrieve_candidates,
    DEFAULT_LIMIT
)

__all__ = [
    "sql_filter_product_service",
    "sql_filter_mutual",
    "qdrant_search_product_service",
    "qdrant_search_mutual",
    "retrieve_candidates",
    "DEFAULT_LIMIT"
]
