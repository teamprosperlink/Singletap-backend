"""
Shared SentenceTransformer singleton.

Ensures both IngestionClients and SemanticResolver share ONE model
instance in memory instead of loading duplicates.
"""

import os

_model = None


def get_embedding_model():
    """Return singleton SentenceTransformer, shared across the app."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        print(f"Loading shared embedding model: {model_name}...")
        _model = SentenceTransformer(model_name)
        print(f"Loaded shared embedding model: {model_name}")
    return _model
