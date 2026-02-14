"""
Centralized configuration settings for Vriddhi Matching Engine.

All environment variables and configuration constants are defined here.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Supabase Configuration
    supabase_url: str
    supabase_key: str

    # Qdrant Configuration
    qdrant_endpoint: str  # Maps to QDRANT_ENDPOINT in .env
    qdrant_api_key: str

    # OpenAI Configuration
    openai_api_key: str

    # BabelNet Configuration (for ontology resolver)
    babelnet_api_key: Optional[str] = None

    # =========================================================================
    # EMBEDDING MODEL CONFIGURATION
    # =========================================================================
    # BAAI/bge models are optimized for retrieval tasks (query-document matching)
    # Dimension is detected at runtime from the model - no hardcoding needed
    #
    # Available options (uncomment to upgrade):
    # -------------------------------------------------------------------------
    # SMALL (384D, 33M params) - Fast, lightweight, current default
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    #
    # BASE (768D, 110M params) - Balanced quality/speed
    # embedding_model_name: str = "BAAI/bge-base-en-v1.5"
    #
    # LARGE (1024D, 335M params) - Best quality, more memory
    # embedding_model_name: str = "BAAI/bge-large-en-v1.5"
    #
    # LEGACY (384D, 22M params) - Original model, general-purpose
    # embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    # =========================================================================

    # =========================================================================
    # RERANKER (CROSS-ENCODER) CONFIGURATION
    # =========================================================================
    # Cross-encoders provide more accurate scoring but are expensive.
    # Only applied to top-k candidates after initial retrieval + boolean match.
    #
    # Available options:
    # -------------------------------------------------------------------------
    # BASE (278M params) - Good quality, reasonable speed
    reranker_model_name: str = "BAAI/bge-reranker-base"
    #
    # LARGE (560M params) - Best quality, slower
    # reranker_model_name: str = "BAAI/bge-reranker-large"
    #
    # Enable/disable reranker (disabled by default to save resources)
    use_reranker: bool = False
    reranker_top_k: int = 20  # Only rerank top-k candidates
    # =========================================================================

    # Qdrant Collection Names
    product_collection: str = "product_listings"
    service_collection: str = "service_listings"
    mutual_collection: str = "mutual_listings"

    # Matching Thresholds
    semantic_threshold: float = 0.82

    # =========================================================================
    # GEOCODING / LOCATION MATCHING CONFIGURATION
    # =========================================================================
    # Uses OpenStreetMap Nominatim API for geocoding (free, no API key)
    # Coordinates enable "Bangalore" to match "Bengaluru" via distance
    #
    # Settings:
    # -------------------------------------------------------------------------
    # Maximum distance (km) for two locations to be considered "same"
    location_max_distance_km: float = 50.0
    #
    # Path to geocoding cache file (stores API responses to avoid rate limits)
    geocoding_cache_file: str = "geocoding_cache.json"
    #
    # User agent for Nominatim API (required by their usage policy)
    geocoding_user_agent: str = "VriddhiMatchingEngine/1.0 (vriddhi@example.com)"
    # =========================================================================

    # =========================================================================
    # TYPE HIERARCHY CONFIGURATION
    # =========================================================================
    # Static type hierarchy file for hierarchical type matching
    # Maps product types to parent/children relationships for smart matching
    type_hierarchy_file: str = "src/data/type_hierarchy.json"
    # =========================================================================

    # Database Table Names
    product_table: str = "product_listings"
    service_table: str = "service_listings"
    mutual_table: str = "mutual_listings"
    matches_table: str = "matches"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env


# Global settings instance
settings = Settings()
