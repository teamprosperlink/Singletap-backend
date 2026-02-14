"""
Shared constants used throughout the Vriddhi Matching Engine.

Note: Unit normalization is handled dynamically by Quantulum3 + Pint.
No hardcoded unit mappings — Pint's .to_base_units() covers all units.
"""

# Matching Engine Constants
INTENT_TYPES = ["product", "service", "mutual"]
SUBINTENT_TYPES = {
    "product": ["buy", "sell"],
    "service": ["seek", "provide"],
    "mutual": ["connect"]
}

# ============================================================================
# VECTOR SEARCH CONSTANTS
# ============================================================================
# IMPORTANT: Vector dimension is now DYNAMIC - detected from model at runtime.
# Use: model.get_sentence_embedding_dimension()
#
# Reference dimensions by model:
# - BAAI/bge-small-en-v1.5: 384D
# - BAAI/bge-base-en-v1.5: 768D
# - BAAI/bge-large-en-v1.5: 1024D
# - sentence-transformers/all-MiniLM-L6-v2: 384D (legacy)
#
# DO NOT hardcode dimension - it will break when switching models.
# ============================================================================
DEFAULT_SEARCH_LIMIT = 100

# Matching Score Thresholds
MIN_SEMANTIC_SIMILARITY = 0.82
MIN_LOCATION_SIMILARITY = 0.7

# Currency Normalization
# All currency values are converted to this target before numeric comparison.
# Changing this value changes the normalization target for the entire engine.
MATCHING_TARGET_CURRENCY = "USD"

# Intent Mapping (NEW → OLD schema compatibility)
INTENT_MAPPING = {
    "product": {
        "buy": "product_buyer",
        "sell": "product_seller"
    },
    "service": {
        "seek": "service_seeker",
        "provide": "service_provider"
    },
    "mutual": {
        "connect": "mutual_seeker"
    }
}

# Domain Categories (subset of full domain list)
COMMON_DOMAINS = [
    "Technology & Electronics",
    "Automotive & Vehicles",
    "Home & Furniture",
    "Real Estate & Property",
    "Education & Training",
    "Sports & Outdoors",
    "Business Services & Consulting",
    "Construction & Trades",
    "Marketing, Advertising & Design"
]

# Location Match Modes
LOCATION_MODES = ["explicit", "near_me", "anywhere"]

# Mutual Categories
MUTUAL_CATEGORIES = [
    "Roommates",
    "Adventure",
    "Professional",
    "Social",
    "Study"
]

