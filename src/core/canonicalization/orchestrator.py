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
from src.utils.logging import get_logger

log = get_logger(__name__)
from src.core.canonicalization.resolvers.generic_categorical_resolver import GenericCategoricalResolver
from src.core.canonicalization.resolvers.quantitative_resolver import QuantitativeResolver
from src.core.canonicalization.resolvers.type_resolver import get_type_resolver
from src.data.loaders.gpc_loader import get_gpc_loader
from src.data.loaders.unspsc_loader import get_unspsc_loader
from src.services.external.wikidata_wrapper import get_wikidata_client
from src.services.external.geocoding_service import get_geocoding_service


def canonicalize_listing(
    listing: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Canonicalize NEW schema listing to resolve non-deterministic values.

    This function sits between GPT-4o extraction and schema normalization.

    Pipeline:
        GPT-4o → NEW Schema → CANONICALIZE → Canonical NEW → Normalize → OLD Schema

    Args:
        listing: NEW schema (14 fields) from GPT extraction
        context: Optional context (user location, preferences)

    Returns:
        Canonical NEW schema with resolved values
    """
    log.info("Starting canonicalization...", emoji="sync")

    canonical_listing = deepcopy(listing)

    # Initialize resolvers
    categorical_resolver = GenericCategoricalResolver()
    quantitative_resolver = QuantitativeResolver()

    try:
        # 1. Canonicalize domain (if using GPC/UNSPSC)
        if "domain" in canonical_listing and canonical_listing["domain"]:
            log.debug("Canonicalizing domain...")
            canonical_listing["domain"] = _canonicalize_domain(
                canonical_listing["domain"]
            )

        # 2. Canonicalize items
        if "items" in canonical_listing and canonical_listing["items"]:
            log.debug("Canonicalizing items", count=len(canonical_listing["items"]))
            canonical_listing["items"] = _canonicalize_items(
                canonical_listing["items"],
                categorical_resolver,
                quantitative_resolver
            )

        # 3. Canonicalize item_exclusions
        if "item_exclusions" in canonical_listing and canonical_listing["item_exclusions"]:
            log.debug("Canonicalizing item_exclusions...")
            canonical_listing["item_exclusions"] = _canonicalize_exclusions(
                canonical_listing["item_exclusions"],
                categorical_resolver
            )

        # 4. Canonicalize other_party_preferences
        if "other_party_preferences" in canonical_listing and canonical_listing["other_party_preferences"]:
            log.debug("Canonicalizing other_party_preferences...")
            canonical_listing["other_party_preferences"] = _canonicalize_preferences(
                canonical_listing["other_party_preferences"],
                categorical_resolver,
                quantitative_resolver
            )

        # 5. Canonicalize other_party_exclusions
        if "other_party_exclusions" in canonical_listing and canonical_listing["other_party_exclusions"]:
            log.debug("Canonicalizing other_party_exclusions...")
            canonical_listing["other_party_exclusions"] = _canonicalize_exclusions(
                canonical_listing["other_party_exclusions"],
                categorical_resolver
            )

        # 6. Canonicalize self_attributes
        if "self_attributes" in canonical_listing and canonical_listing["self_attributes"]:
            log.debug("Canonicalizing self_attributes...")
            canonical_listing["self_attributes"] = _canonicalize_preferences(
                canonical_listing["self_attributes"],
                categorical_resolver,
                quantitative_resolver
            )

        # 7. Canonicalize self_exclusions
        if "self_exclusions" in canonical_listing and canonical_listing["self_exclusions"]:
            log.debug("Canonicalizing self_exclusions...")
            canonical_listing["self_exclusions"] = _canonicalize_exclusions(
                canonical_listing["self_exclusions"],
                categorical_resolver
            )

        # 8. Canonicalize target_location (future: use geocoding API)
        # For now, just lowercase
        if "target_location" in canonical_listing and canonical_listing["target_location"]:
            log.debug("Canonicalizing location...")
            _canonicalize_location(canonical_listing["target_location"])

        # 9. Canonicalize location_exclusions (just lowercase for now)
        if "location_exclusions" in canonical_listing and canonical_listing["location_exclusions"]:
            log.debug("Canonicalizing location_exclusions...")
            canonical_listing["location_exclusions"] = [
                loc.lower() for loc in canonical_listing["location_exclusions"]
            ]

        log.info("Canonicalization complete!", emoji="success")
        return canonical_listing

    except Exception as e:
        log.warning("Canonicalization error. Returning original listing.",
                    emoji="warning", error=str(e))
        return listing


def _canonicalize_domain(domain: List[str]) -> List[str]:
    """Canonicalize domain using GPC/UNSPSC (placeholder for now)."""
    # For now, just lowercase
    return [d.lower() for d in domain]


def _canonicalize_items(
    items: List[Dict],
    categorical_resolver: GenericCategoricalResolver,
    quantitative_resolver: QuantitativeResolver
) -> List[Dict]:
    """
    Canonicalize items array.

    Each item has:
    - type: canonical market noun → resolve with TypeResolver (hierarchical)
    - categorical: {key: value} → resolve with ontology
    - min/max/range: numeric attributes → normalize units
    """
    canonical_items = []
    type_resolver = get_type_resolver()

    for item in items:
        canonical_item = deepcopy(item)

        # Canonicalize item type using TypeResolver (hierarchical matching)
        if "type" in item and item["type"]:
            type_node = type_resolver.resolve(item["type"])
            if type_node:
                # Store ontology-format type (same structure as categorical)
                canonical_item["type"] = type_resolver.to_schema_format(type_node)

        # Canonicalize categorical attributes
        if "categorical" in item and item["categorical"]:
            canonical_categorical = {}

            for key, value in item["categorical"].items():
                # Resolve value to ontology node
                node = categorical_resolver.resolve(value, attribute_key=key)

                if node:
                    # Store ontology format
                    canonical_categorical[key] = categorical_resolver.to_schema_format(node)
                else:
                    # Keep original if resolution fails
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
                # Quantulum3/Pint cannot handle currency — use resolve_currency()
                # which expands lakh/crore/k and preserves currency code.
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
                    # Value already numeric — ensure currency metadata is preserved.
                    # GPT sometimes puts currency code in the "unit" field.
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
    """
    Check if a string is a valid currency code (dynamic, API-backed).

    Uses CurrencyService.is_currency_code() which fetches the supported
    currency list from frankfurter.app /currencies endpoint (cached after
    first call). No hardcoded currency list.

    Args:
        code: String to check (e.g., "INR", "USD")

    Returns:
        True if the code is a recognized currency code.
    """
    if not code or len(code) != 3:
        return False
    from src.services.external.currency_service import get_currency_service
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
                        "value": categorical_resolver.to_schema_format(node)
                    })
                else:
                    canonical_identity.append(identity_item)

        canonical_prefs["identity"] = canonical_identity

    # Canonicalize lifestyle (categorical - ontology) ⭐ NEW
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
                        "value": categorical_resolver.to_schema_format(node)
                    })
                else:
                    canonical_lifestyle.append(lifestyle_item)

        canonical_prefs["lifestyle"] = canonical_lifestyle

    # habits field - pass through as-is (yes/no flags, not ontological)
    # Already in canonical_prefs from deepcopy

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

    Exclusions contain categorical values that should be resolved
    the same way as other categorical attributes.

    Args:
        exclusions: List of exclusion strings (e.g., ["refurbished laptops", "agents"])
        categorical_resolver: Generic categorical resolver

    Returns:
        List of ontology-structured exclusions
    """
    canonical_exclusions = []

    for exclusion_value in exclusions:
        # Resolve exclusion value to ontology node
        node = categorical_resolver.resolve(exclusion_value)

        if node:
            # Store ontology format
            canonical_exclusions.append(categorical_resolver.to_schema_format(node))
        else:
            # Keep original if resolution fails (as simple string for backward compatibility)
            canonical_exclusions.append(exclusion_value)

    return canonical_exclusions


def _canonicalize_location(location: Dict):
    """
    Canonicalize location using geocoding API.

    Converts location names to coordinates for distance-based matching.
    Falls back to lowercase normalization if geocoding fails.

    Location structure after canonicalization:
    {
        "name": "bangalore",
        "coordinates": {"lat": 12.9716, "lng": 77.5946},
        "canonical_name": "Bengaluru"
    }
    """
    geocoding = get_geocoding_service()

    if "name" in location and location["name"]:
        original_name = location["name"]
        location["name"] = original_name.lower()

        # Try to geocode for coordinates
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

        # Geocode origin
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

        # Geocode destination
        coords = geocoding.geocode(original_dest)
        if coords:
            location["destination_coordinates"] = {
                "lat": coords["lat"],
                "lng": coords["lng"]
            }
            location["destination_canonical"] = coords.get("canonical_name", original_dest)
