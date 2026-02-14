"""
Canonicalization Orchestrator.

Main entry point for canonicalizing NEW schema listings from GPT-4o extraction.
Coordinates all resolution steps:
1. Domain canonicalization
2. Item type canonicalization
3. Categorical attribute resolution
4. Quantitative normalization
5. Location canonicalization
"""

from typing import Dict, Any, Optional, List
from copy import deepcopy
from canonicalization.resolvers.generic_categorical_resolver import GenericCategoricalResolver
from canonicalization.resolvers.quantitative_resolver import QuantitativeResolver
from services.external.geocoding_service import get_geocoding_service

# Shared resolver singletons — synonym registrations persist across listings
_categorical_resolver = None
_quantitative_resolver = None


def _get_categorical_resolver():
    global _categorical_resolver
    if _categorical_resolver is None:
        _categorical_resolver = GenericCategoricalResolver()
    return _categorical_resolver


def _get_quantitative_resolver():
    global _quantitative_resolver
    if _quantitative_resolver is None:
        _quantitative_resolver = QuantitativeResolver()
    return _quantitative_resolver


def canonicalize_listing(
    listing: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Canonicalize NEW schema listing to resolve non-deterministic values.

    This function sits between GPT-4o extraction and schema normalization.

    Pipeline:
        GPT-4o -> NEW Schema -> CANONICALIZE -> Canonical NEW -> Normalize -> OLD Schema

    Args:
        listing: NEW schema (14 fields) from GPT extraction
        context: Optional context (user location, preferences)

    Returns:
        Canonical NEW schema with resolved values
    """
    print("Starting canonicalization...")

    canonical_listing = deepcopy(listing)

    # Use shared resolver singletons (synonym registrations persist across calls)
    categorical_resolver = _get_categorical_resolver()
    quantitative_resolver = _get_quantitative_resolver()

    try:
        # 1. Canonicalize domain
        if "domain" in canonical_listing and canonical_listing["domain"]:
            print("  -> Canonicalizing domain...")
            canonical_listing["domain"] = _canonicalize_domain(
                canonical_listing["domain"]
            )

        # 2. Canonicalize items
        if "items" in canonical_listing and canonical_listing["items"]:
            print(f"  -> Canonicalizing {len(canonical_listing['items'])} items...")
            domain_context = canonical_listing.get("domain", [])
            canonical_listing["items"] = _canonicalize_items(
                canonical_listing["items"],
                categorical_resolver,
                quantitative_resolver,
                domain_context=domain_context
            )

        # 3. Canonicalize item_exclusions
        if "item_exclusions" in canonical_listing and canonical_listing["item_exclusions"]:
            print("  -> Canonicalizing item_exclusions...")
            canonical_listing["item_exclusions"] = _canonicalize_exclusions(
                canonical_listing["item_exclusions"],
                categorical_resolver
            )

        # 4. Canonicalize other_party_preferences
        if "other_party_preferences" in canonical_listing and canonical_listing["other_party_preferences"]:
            print("  -> Canonicalizing other_party_preferences...")
            canonical_listing["other_party_preferences"] = _canonicalize_preferences(
                canonical_listing["other_party_preferences"],
                categorical_resolver,
                quantitative_resolver
            )

        # 5. Canonicalize other_party_exclusions
        if "other_party_exclusions" in canonical_listing and canonical_listing["other_party_exclusions"]:
            print("  -> Canonicalizing other_party_exclusions...")
            canonical_listing["other_party_exclusions"] = _canonicalize_exclusions(
                canonical_listing["other_party_exclusions"],
                categorical_resolver
            )

        # 6. Canonicalize self_attributes
        if "self_attributes" in canonical_listing and canonical_listing["self_attributes"]:
            print("  -> Canonicalizing self_attributes...")
            canonical_listing["self_attributes"] = _canonicalize_preferences(
                canonical_listing["self_attributes"],
                categorical_resolver,
                quantitative_resolver
            )

        # 7. Canonicalize self_exclusions
        if "self_exclusions" in canonical_listing and canonical_listing["self_exclusions"]:
            print("  -> Canonicalizing self_exclusions...")
            canonical_listing["self_exclusions"] = _canonicalize_exclusions(
                canonical_listing["self_exclusions"],
                categorical_resolver
            )

        # 8. Canonicalize target_location (use geocoding API)
        if "target_location" in canonical_listing and canonical_listing["target_location"]:
            print("  -> Canonicalizing location...")
            _canonicalize_location(canonical_listing["target_location"])

        # 9. Canonicalize location_exclusions
        if "location_exclusions" in canonical_listing and canonical_listing["location_exclusions"]:
            print("  -> Canonicalizing location_exclusions...")
            canonical_listing["location_exclusions"] = [
                loc.lower() for loc in canonical_listing["location_exclusions"]
            ]

        # Flush any new concepts to DB (write-behind)
        _flush_ontology_to_db()

        print("Canonicalization complete!")
        return canonical_listing

    except Exception as e:
        print(f"Canonicalization error: {e}. Applying lowercase fallback.")
        # Lowercase fallback for categorical values when resolver cascade fails
        fallback = deepcopy(listing)
        try:
            if "items" in fallback and fallback["items"]:
                for item in fallback["items"]:
                    if "type" in item and isinstance(item["type"], str):
                        item["type"] = item["type"].lower()
                    if "categorical" in item and isinstance(item["categorical"], dict):
                        item["categorical"] = {
                            k: v.lower() if isinstance(v, str) else v
                            for k, v in item["categorical"].items()
                        }
        except Exception:
            pass
        return fallback


def _canonicalize_domain(domain: List[str]) -> List[str]:
    """Canonicalize domain (lowercase for now)."""
    return [d.lower() for d in domain]


def _canonicalize_items(
    items: List[Dict],
    categorical_resolver: GenericCategoricalResolver,
    quantitative_resolver: QuantitativeResolver,
    domain_context: Optional[List[str]] = None
) -> List[Dict]:
    """
    Canonicalize items array.

    Each item has:
    - type: canonical market noun -> resolve via Wikidata with domain context
    - categorical: {key: value} -> resolve with ontology
    - min/max/range: numeric attributes -> normalize units
    """
    canonical_items = []
    # Build context string from domain for type disambiguation
    type_context = " ".join(domain_context) if domain_context else None

    for item in items:
        canonical_item = deepcopy(item)

        # Canonicalize item type using Wikidata with domain context for disambiguation
        if "type" in item and item["type"]:
            canonical_item["type"] = _canonicalize_type(item["type"], context=type_context)

        # Canonicalize categorical attributes
        # IMPORTANT: Store just concept_id (string), not full ontology dict.
        # The matching engine expects categorical values to be plain strings.
        if "categorical" in item and item["categorical"]:
            canonical_categorical = {}

            for key, value in item["categorical"].items():
                node = categorical_resolver.resolve(value, attribute_key=key)

                if node:
                    canonical_categorical[key] = node.concept_id
                else:
                    canonical_categorical[key] = value

            canonical_item["categorical"] = canonical_categorical

        # Canonicalize numeric attributes (min/max/range)
        for constraint_type in ["min", "max", "range"]:
            if constraint_type in item and item[constraint_type]:
                canonical_item[constraint_type] = _canonicalize_constraints(
                    item[constraint_type],
                    quantitative_resolver
                )

        canonical_items.append(canonical_item)

    return canonical_items


def _canonicalize_type(item_type: str, context: Optional[str] = None) -> str:
    """
    Canonicalize item type using the resolver pipeline.

    Routes through the same 3-phase pipeline as categorical attributes:
    preprocessing, multi-source disambiguation, and cross-tier propagation.

    Falls back to lowercased type if resolution fails.
    """
    try:
        resolver = _get_categorical_resolver()
        node = resolver.resolve(item_type, attribute_key=context or "item_type")
        if node and node.source != "fallback":
            return node.concept_id
    except Exception as e:
        print(f"Type canonicalization error for '{item_type}': {e}")

    return item_type.lower()


def _canonicalize_constraints(
    constraints: Dict[str, List[Dict]],
    quantitative_resolver: QuantitativeResolver
) -> Dict[str, List[Dict]]:
    """Canonicalize min/max/range constraints."""
    canonical_constraints = {}

    for axis, attributes in constraints.items():
        canonical_attrs = []

        for attr in attributes:
            canonical_attr = deepcopy(attr)

            if axis == "cost":
                # Cost axis: currency, not a physical unit.
                if "value" in attr and isinstance(attr["value"], str):
                    currency = attr.get("currency") or attr.get("unit")
                    resolved = quantitative_resolver.resolve_currency(
                        attr["value"], currency=currency
                    )
                    if resolved:
                        canonical_attr["value"] = resolved["value"]
                        canonical_attr["currency"] = resolved["currency"]
                        canonical_attr.pop("unit", None)
                elif "value" in attr and isinstance(attr["value"], (int, float)):
                    if "currency" not in canonical_attr:
                        unit_val = str(attr.get("unit", "")).upper()
                        if _is_currency_code(unit_val):
                            canonical_attr["currency"] = unit_val
                            canonical_attr.pop("unit", None)
            else:
                # Non-cost axes: physical units via Quantulum3 + Pint
                if "value" in attr and isinstance(attr["value"], str):
                    resolved = quantitative_resolver.resolve(attr["value"])

                    if resolved:
                        canonical_attr["value"] = resolved["value"]
                        canonical_attr["unit"] = resolved["unit"]

            canonical_attrs.append(canonical_attr)

        canonical_constraints[axis] = canonical_attrs

    return canonical_constraints


def _is_currency_code(code: str) -> bool:
    """Check if a string is a valid currency code (dynamic, API-backed)."""
    if not code or len(code) != 3:
        return False
    from services.external.currency_service import get_currency_service
    return get_currency_service().is_currency_code(code)


def _canonicalize_preferences(
    preferences: Dict,
    categorical_resolver: GenericCategoricalResolver,
    quantitative_resolver: QuantitativeResolver
) -> Dict:
    """
    Canonicalize other_party_preferences or self_attributes.

    Handles:
    - identity (ontology)
    - lifestyle (ontology)
    - habits (pass-through flags)
    - min/max/range (quantitative)
    """
    canonical_prefs = deepcopy(preferences)

    # Canonicalize identity (categorical - ontology)
    if "identity" in preferences and preferences["identity"]:
        canonical_identity = []

        for identity_item in preferences["identity"]:
            if "value" in identity_item:
                node = categorical_resolver.resolve(
                    identity_item["value"],
                    attribute_key=identity_item.get("type")
                )

                if node:
                    canonical_identity.append({
                        "type": identity_item.get("type"),
                        "value": node.concept_id
                    })
                else:
                    canonical_identity.append(identity_item)

        canonical_prefs["identity"] = canonical_identity

    # Canonicalize lifestyle (categorical - ontology)
    if "lifestyle" in preferences and preferences["lifestyle"]:
        canonical_lifestyle = []

        for lifestyle_item in preferences["lifestyle"]:
            if "value" in lifestyle_item:
                node = categorical_resolver.resolve(
                    lifestyle_item["value"],
                    attribute_key=lifestyle_item.get("type")
                )

                if node:
                    canonical_lifestyle.append({
                        "type": lifestyle_item.get("type"),
                        "value": node.concept_id
                    })
                else:
                    canonical_lifestyle.append(lifestyle_item)

        canonical_prefs["lifestyle"] = canonical_lifestyle

    # habits field - pass through as-is (yes/no flags, not ontological)

    # Canonicalize numeric constraints (min/max/range)
    for constraint_type in ["min", "max", "range"]:
        if constraint_type in preferences and preferences[constraint_type]:
            canonical_prefs[constraint_type] = _canonicalize_constraints(
                preferences[constraint_type],
                quantitative_resolver
            )

    return canonical_prefs


def _canonicalize_exclusions(
    exclusions: List[str],
    categorical_resolver: GenericCategoricalResolver
) -> List[Dict]:
    """
    Canonicalize exclusion lists with ontology.

    Args:
        exclusions: List of exclusion strings
        categorical_resolver: Generic categorical resolver

    Returns:
        List of ontology-structured exclusions
    """
    canonical_exclusions = []

    for exclusion_value in exclusions:
        node = categorical_resolver.resolve(exclusion_value)

        if node:
            canonical_exclusions.append(node.concept_id)
        else:
            canonical_exclusions.append(exclusion_value)

    return canonical_exclusions


def _canonicalize_location(location: Dict):
    """
    Canonicalize location using geocoding API.

    Converts location names to coordinates for distance-based matching.
    Falls back to lowercase normalization if geocoding fails.
    """
    geocoding = get_geocoding_service()

    if "name" in location and location["name"]:
        original_name = location["name"]
        location["name"] = original_name.lower()

        coords = geocoding.geocode(original_name)
        if coords:
            location["coordinates"] = {
                "lat": coords["lat"],
                "lng": coords["lng"]
            }
            location["canonical_name"] = coords.get("canonical_name", original_name)

    if "origin" in location and location["origin"]:
        original_origin = location["origin"]
        location["origin"] = original_origin.lower()

        coords = geocoding.geocode(original_origin)
        if coords:
            location["origin_coordinates"] = {
                "lat": coords["lat"],
                "lng": coords["lng"]
            }
            location["origin_canonical"] = coords.get("canonical_name", original_origin)

    if "destination" in location and location["destination"]:
        original_dest = location["destination"]
        location["destination"] = original_dest.lower()

        coords = geocoding.geocode(original_dest)
        if coords:
            location["destination_coordinates"] = {
                "lat": coords["lat"],
                "lng": coords["lng"]
            }
            location["destination_canonical"] = coords.get("canonical_name", original_dest)


def _flush_ontology_to_db():
    """Flush buffered concepts from OntologyStore to Supabase (write-behind)."""
    try:
        from canonicalization.ontology_store import get_ontology_store
        store = get_ontology_store()
        if store.is_initialized:
            flushed = store.flush_to_db()
            if flushed > 0:
                print(f"  -> Flushed {flushed} concepts to DB")
    except Exception as e:
        print(f"  -> Ontology flush skipped: {e}")
