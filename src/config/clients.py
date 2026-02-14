"""
Unified database and ML client manager for Vriddhi Matching Engine.

Consolidates the duplicate IngestionClients and RetrievalClients into a single
DatabaseClients class using singleton pattern.

Manages:
- Supabase (PostgreSQL with JSONB)
- Qdrant (Vector database)
- SentenceTransformer (Embedding model - BAAI/bge-*)
- CrossEncoder (Reranker model - optional, BAAI/bge-reranker-*)
"""

from typing import Optional
from supabase import Client, create_client
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder

from .settings import settings


class DatabaseClients:
    """
    Unified database and ML client manager (Singleton pattern).

    Manages connections to:
    - Supabase (PostgreSQL with JSONB)
    - Qdrant (Vector database)
    - SentenceTransformer (Embedding model - BAAI/bge-*)
    - CrossEncoder (Reranker model - optional, for top-k reranking)

    Usage:
        from src.config.clients import db_clients
        db_clients.initialize()
        # Access: db_clients.supabase, db_clients.qdrant, db_clients.embedding_model
        # Optional: db_clients.reranker (if settings.use_reranker=True)
    """

    _instance: Optional['DatabaseClients'] = None

    def __new__(cls):
        """Ensure only one instance exists (singleton)"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize client placeholders"""
        if not hasattr(self, 'initialized'):
            self.supabase: Optional[Client] = None
            self.qdrant: Optional[QdrantClient] = None
            self.embedding_model: Optional[SentenceTransformer] = None
            self.reranker: Optional[CrossEncoder] = None
            self.initialized = False

    def initialize(self):
        """
        Initialize all clients using settings from config/settings.py

        Raises:
            ValueError: If required environment variables are missing
        """
        if self.initialized:
            print("⚠️ Clients already initialized, skipping...")
            return

        # Initialize Supabase
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY environment variables required"
            )

        self.supabase = create_client(settings.supabase_url, settings.supabase_key)
        print(f"✅ Connected to Supabase: {settings.supabase_url}")

        # Initialize Qdrant Cloud
        if not settings.qdrant_endpoint or not settings.qdrant_api_key:
            raise ValueError(
                "QDRANT_ENDPOINT and QDRANT_API_KEY environment variables required"
            )

        self.qdrant = QdrantClient(
            url=settings.qdrant_endpoint,
            api_key=settings.qdrant_api_key
        )
        print(f"✅ Connected to Qdrant Cloud: {settings.qdrant_endpoint}")

        # Initialize Embedding Model (BAAI/bge-*)
        print(f"🚀 Loading embedding model: {settings.embedding_model_name}...")
        self.embedding_model = SentenceTransformer(settings.embedding_model_name)
        dim = self.embedding_model.get_sentence_embedding_dimension()
        print(f"✅ Loaded embedding model: {settings.embedding_model_name} ({dim}D)")

        # Initialize Reranker (optional, only if enabled)
        if settings.use_reranker:
            print(f"🚀 Loading reranker model: {settings.reranker_model_name}...")
            self.reranker = CrossEncoder(settings.reranker_model_name)
            print(f"✅ Loaded reranker model: {settings.reranker_model_name}")
            print(f"   Reranker will be applied to top-{settings.reranker_top_k} candidates")
        else:
            self.reranker = None
            print("ℹ️ Reranker disabled (set use_reranker=True in settings to enable)")

        self.initialized = True
        print("✅ All database clients initialized successfully")

    def close(self):
        """Close all client connections (if needed)"""
        # Supabase and Qdrant clients don't need explicit closing
        # but this method is here for future cleanup needs
        self.initialized = False
        self.reranker = None
        print("✅ All database clients closed")

    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension from the loaded model.

        Returns:
            int: Vector dimension (e.g., 384, 768, 1024)

        Raises:
            RuntimeError: If embedding model not initialized
        """
        if not self.embedding_model:
            raise RuntimeError("Embedding model not initialized. Call initialize() first.")
        return self.embedding_model.get_sentence_embedding_dimension()


# Global singleton instance
db_clients = DatabaseClients()
