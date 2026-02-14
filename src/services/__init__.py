"""
Services Layer: External services for embedding, storage, and retrieval.

Sub-modules:
- embedding: Embedding text construction
- retrieval: Candidate selection via SQL and vector search
"""

# Import key functions for convenience
from .embedding import build_embedding_text
from .retrieval import retrieve_candidates

__all__ = [
    "build_embedding_text",
    "retrieve_candidates"
]
