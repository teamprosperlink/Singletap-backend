"""
Embedding Service: Constructs embedding text from normalized listings.

Provides functions to build embedding text for:
- Product/Service listings (structured attributes)
- Mutual listings (semantic queries)
"""

from .service import (
    build_embedding_text,
    build_embedding_text_product_service,
    build_embedding_text_mutual,
    preview_embedding_text
)

__all__ = [
    "build_embedding_text",
    "build_embedding_text_product_service",
    "build_embedding_text_mutual",
    "preview_embedding_text"
]
