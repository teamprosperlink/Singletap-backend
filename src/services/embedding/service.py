"""
PHASE 3.3: EMBEDDING TEXT CONSTRUCTION

Responsibilities:
- Construct embedding text from normalized listing objects
- Product/Service: Natural language sentences (optimized for BAAI/bge models)
- Mutual: Semantic query meaning

IMPORTANT DESIGN DECISIONS:
1. Embedding text uses NATURAL LANGUAGE, not keyword bags
   - BAAI/bge models are trained on natural language sentences
   - Keyword bags ("product sell laptop dell") collapse semantic relationships
   - Natural language ("product listing in electronics offering laptop with brand dell")
     preserves meaning and improves retrieval quality

2. SUBINTENT (buy/sell) is EXCLUDED from embedding text
   - Including subintent creates unwanted vector distance
   - A buyer's query should find sellers (opposite subintent)
   - If "buy" is in the query embedding and "sell" is in the listing embedding,
     they push apart in vector space, hurting recall
   - Boolean matching (M-02) handles subintent reversal, not vector search

3. Vector search finds ALL relevant listings in the domain
   - Qdrant retrieves candidates by semantic similarity
   - Boolean matching then filters by business rules (subintent, constraints)
   - This two-phase approach gives best recall + precision

Authority: VRIDDHI Architecture Document
Dependencies: None (pure Python)

Author: Claude (Implementation Engine)
Date: 2026-01-12 (Updated: 2026-02-05)
"""

from typing import Dict, Any, List, Union


# ============================================================================
# HELPERS
# ============================================================================

def _iter_categorical(cat: Union[Dict, List, None]):
    """
    Iterate categorical in either format, yielding (key, value) pairs.

    Supports:
    - Dict format: {"brand": "dell", "color": "black"}
    - Array format: [{"attribute": "brand", "value": "dell"}, ...]
    """
    if not cat:
        return
    if isinstance(cat, dict):
        for k, v in cat.items():
            yield str(k), v
    elif isinstance(cat, list):
        for item in cat:
            if isinstance(item, dict):
                k = item.get("attribute", "")
                v = item.get("value", "")
                yield str(k), v


def _extract_value(val: Any) -> str:
    """
    Extract string value from various formats.

    Handles:
    - Simple strings: "apple" -> "apple"
    - Ontology dicts: {"concept_id": "apple", ...} -> "apple"
    - Other: str(val)
    """
    if isinstance(val, dict):
        if "concept_id" in val:
            return str(val["concept_id"])
        return ""
    return str(val) if val else ""


# ============================================================================
# EMBEDDING TEXT CONSTRUCTION
# ============================================================================

def build_embedding_text_product_service(listing: Dict[str, Any]) -> str:
    """
    Build embedding text for product or service listings.

    Strategy: Construct NATURAL LANGUAGE sentences for BAAI/bge models.

    Output format examples:
    - "product listing in electronics offering laptop with brand dell and color black"
    - "service listing in education offering tutoring with subject mathematics"

    IMPORTANT: Subintent (buy/sell/seek/provide) is EXCLUDED.
    - Vector search should find ALL relevant listings regardless of subintent
    - Boolean matching handles subintent reversal (buyer finds seller)
    - Including subintent creates unwanted distance in vector space

    Args:
        listing: Normalized listing object

    Returns:
        Natural language text string for embedding

    Examples:
        Input:
        {
            "intent": "product",
            "subintent": "sell",  # Ignored in embedding
            "domain": ["electronics"],
            "items": [{"type": "laptop", "categorical": {"brand": "dell", "color": "black"}}]
        }

        Output:
        "product listing in electronics offering laptop with brand dell and color black"
    """
    parts = []

    # 1. Intent context (natural language)
    intent = listing.get("intent", "")
    if intent:
        parts.append(f"{intent} listing")

    # 2. Domain context (natural language)
    # NOTE: Subintent (buy/sell) is intentionally EXCLUDED
    # Boolean matching handles subintent reversal, not vector search
    domains = listing.get("domain", [])
    if domains:
        domain_text = " and ".join(str(d) for d in domains if d)
        if domain_text:
            parts.append(f"in {domain_text}")

    # 3. Items (natural language description)
    items = listing.get("items", [])
    if items:
        item_descriptions = []

        for item in items:
            item_parts = []

            # Item type
            item_type = item.get("type", "")
            if item_type:
                item_parts.append(str(item_type))

            # Categorical attributes as "attr value" pairs
            categorical = item.get("categorical", {})
            if categorical:
                attr_parts = []
                for attr_key, attr_value in _iter_categorical(categorical):
                    val = _extract_value(attr_value)
                    if val:
                        attr_parts.append(f"{attr_key} {val}")

                if attr_parts:
                    item_parts.append("with " + " and ".join(attr_parts))

            # Numeric constraints as context (attribute names + values for searchability)
            constraint_parts = []

            # Min constraints
            min_constraints = item.get("min", {})
            for attr_key, attr_value in min_constraints.items():
                constraint_parts.append(f"minimum {attr_key} {attr_value}")

            # Max constraints
            max_constraints = item.get("max", {})
            for attr_key, attr_value in max_constraints.items():
                constraint_parts.append(f"maximum {attr_key} {attr_value}")

            # Range constraints
            range_constraints = item.get("range", {})
            for attr_key, attr_value in range_constraints.items():
                if isinstance(attr_value, (list, tuple)) and len(attr_value) == 2:
                    constraint_parts.append(f"{attr_key} between {attr_value[0]} and {attr_value[1]}")
                else:
                    constraint_parts.append(f"{attr_key} {attr_value}")

            if constraint_parts:
                item_parts.append(" ".join(constraint_parts))

            if item_parts:
                item_descriptions.append(" ".join(item_parts))

        if item_descriptions:
            parts.append("offering " + ", ".join(item_descriptions))

    # 4. Other party preferences (what user wants from counterparty)
    other = listing.get("other", {})
    if other:
        other_parts = []

        # Categorical requirements
        other_categorical = other.get("categorical", {})
        if other_categorical:
            for attr_key, attr_value in _iter_categorical(other_categorical):
                val = _extract_value(attr_value)
                if val:
                    other_parts.append(f"{attr_key} {val}")

        # Numeric requirements
        for attr_key, attr_value in other.get("min", {}).items():
            other_parts.append(f"minimum {attr_key} {attr_value}")
        for attr_key, attr_value in other.get("max", {}).items():
            other_parts.append(f"maximum {attr_key} {attr_value}")

        if other_parts:
            parts.append("wanting " + " and ".join(other_parts))

    # 5. Self attributes (what user offers about themselves)
    self_obj = listing.get("self", {})
    if self_obj:
        self_parts = []

        self_categorical = self_obj.get("categorical", {})
        if self_categorical:
            for attr_key, attr_value in _iter_categorical(self_categorical):
                val = _extract_value(attr_value)
                if val:
                    self_parts.append(f"{attr_key} {val}")

        if self_parts:
            parts.append("with " + " and ".join(self_parts))

    # Join into natural language
    return " ".join(parts)


def build_embedding_text_mutual(listing: Dict[str, Any]) -> str:
    """
    Build embedding text for mutual exchange listings.

    Strategy: Semantic meaning, NOT keyword bias.
    - Construct natural language description of exchange
    - Include what user offers (items)
    - Include what user wants (other)
    - Include self attributes (context)
    - NO slicing by item type

    Args:
        listing: Normalized listing object

    Returns:
        Natural language text for semantic embedding
    """
    parts = []

    # 1. Intent context
    parts.append("mutual exchange")

    # 2. Category (what kind of exchange)
    if "category" in listing and listing["category"]:
        category_text = " and ".join(listing["category"])
        parts.append(f"in categories: {category_text}")

    # 3. What user offers (items)
    if "items" in listing and listing["items"]:
        offer_parts = []
        for item in listing["items"]:
            item_desc = []

            # Type
            if "type" in item and item["type"]:
                item_desc.append(str(item["type"]))

            # Categorical attributes
            if "categorical" in item and item["categorical"]:
                for attr_key, attr_value in _iter_categorical(item["categorical"]):
                    if attr_value and not isinstance(attr_value, dict):
                        item_desc.append(f"{attr_key}: {attr_value}")

            if item_desc:
                offer_parts.append(" ".join(item_desc))

        if offer_parts:
            parts.append("offering " + ", ".join(offer_parts))

    # 4. What user wants (other)
    if "other" in listing:
        other = listing["other"]
        want_parts = []

        # Categorical requirements
        if "categorical" in other and other["categorical"]:
            for attr_key, attr_value in _iter_categorical(other["categorical"]):
                if attr_value and not isinstance(attr_value, dict):
                    want_parts.append(f"{attr_key}: {attr_value}")

        # Min requirements
        if "min" in other and other["min"]:
            for attr_key, attr_value in other["min"].items():
                want_parts.append(f"{attr_key} at least {attr_value}")

        # Max requirements
        if "max" in other and other["max"]:
            for attr_key, attr_value in other["max"].items():
                want_parts.append(f"{attr_key} at most {attr_value}")

        # Range requirements
        if "range" in other and other["range"]:
            for attr_key, attr_value in other["range"].items():
                if isinstance(attr_value, list) and len(attr_value) == 2:
                    want_parts.append(f"{attr_key} between {attr_value[0]} and {attr_value[1]}")

        if want_parts:
            parts.append("wanting " + ", ".join(want_parts))

    # 5. Self attributes (additional context)
    if "self" in listing:
        self_obj = listing["self"]
        self_parts = []

        # Categorical self-description
        if "categorical" in self_obj and self_obj["categorical"]:
            for attr_key, attr_value in _iter_categorical(self_obj["categorical"]):
                if attr_value and not isinstance(attr_value, dict):
                    self_parts.append(f"{attr_key}: {attr_value}")

        if self_parts:
            parts.append("with attributes " + ", ".join(self_parts))

    # Join into natural language
    return " ".join(parts)


def build_embedding_text(listing: Dict[str, Any]) -> str:
    """
    Build embedding text for any listing type.

    Routes to appropriate builder based on intent.

    Args:
        listing: Normalized listing object

    Returns:
        Text string for embedding generation

    Raises:
        ValueError: If intent field missing or unknown
    """
    if "intent" not in listing:
        raise ValueError("Listing missing 'intent' field")

    intent = listing["intent"]

    if intent == "product" or intent == "service":
        return build_embedding_text_product_service(listing)
    elif intent == "mutual":
        return build_embedding_text_mutual(listing)
    else:
        raise ValueError(f"Unknown intent: {intent}")


# ============================================================================
# UTILITIES
# ============================================================================

def preview_embedding_text(listing: Dict[str, Any]) -> None:
    """
    Print embedding text for a listing (debugging/verification).

    Args:
        listing: Normalized listing object
    """
    text = build_embedding_text(listing)
    print(f"Intent: {listing.get('intent')}")
    print(f"Embedding text ({len(text)} chars):")
    print(f"  {text}")
    print()
