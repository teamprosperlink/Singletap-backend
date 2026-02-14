"""
PHASE 2.X: LOCATION MATCHING (V3 - GEOCODING ENHANCED)

Responsibility:
- Match locations using coordinate-based distance calculation
- Handle location exclusions
- Support all 5 location modes (near_me, explicit, target_only, route, global)
- Fall back to string matching if geocoding fails

NEW Schema Location Structure:
- target_location: {"name": "bangalore", "coordinates": {"lat": 12.9716, "lng": 77.5946}}
- location_match_mode: "near_me" | "explicit" | "target_only" | "route" | "global"
- location_exclusions: ["whitefield", "airport"]

Matching Logic:
1. If coordinates available → use haversine distance (configurable threshold)
2. Fall back to canonical name matching
3. Final fallback to string equality
4. Exclusion list matching

Authority: GLOBAL_REFERENCE_CONTEXT.md (NEW schema)
Dependencies: src.services.external.geocoding_service

Author: Claude (Location Matcher V3)
Date: 2026-01-13 (Updated: 2026-02-05)
"""

from typing import Dict, List, Union, Optional
from src.services.external.geocoding_service import get_geocoding_service


# ============================================================================
# CONFIGURATION
# ============================================================================

# Default distance threshold for "same location" matching (in km)
# Locations within this distance are considered a match
DEFAULT_MAX_DISTANCE_KM = 50.0


# ============================================================================
# COORDINATE-BASED MATCHING
# ============================================================================

def match_location_by_coordinates(
    location1: Union[str, Dict],
    location2: Union[str, Dict],
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM
) -> Optional[bool]:
    """
    Match locations using coordinate-based distance calculation.

    Uses GeocodingService to:
    1. Get coordinates for both locations (from cache or API)
    2. Calculate haversine distance
    3. Return True if within threshold

    Args:
        location1: First location (string or dict with name/coordinates)
        location2: Second location (string or dict with name/coordinates)
        max_distance_km: Maximum distance in km to be considered a match

    Returns:
        True if within distance threshold
        False if outside distance threshold
        None if either location cannot be geocoded (trigger fallback)

    Examples:
        >>> match_location_by_coordinates("Bangalore", "Bengaluru", 50)
        True  # Same city, different names

        >>> match_location_by_coordinates("Mumbai", "Delhi", 50)
        False  # Different cities

        >>> match_location_by_coordinates("Unknown Place", "Mumbai", 50)
        None  # Geocoding failed, use fallback
    """
    geocoding = get_geocoding_service()

    # Extract coordinates or location names
    coords1 = _get_coordinates(location1, geocoding)
    coords2 = _get_coordinates(location2, geocoding)

    # If either location has no coordinates, return None (trigger fallback)
    if coords1 is None or coords2 is None:
        return None

    # Calculate distance using haversine formula
    distance = geocoding._haversine_distance(
        coords1["lat"], coords1["lng"],
        coords2["lat"], coords2["lng"]
    )

    return distance <= max_distance_km


def _get_coordinates(
    location: Union[str, Dict, None],
    geocoding
) -> Optional[Dict]:
    """
    Get coordinates for a location.

    Checks for pre-computed coordinates in dict, otherwise geocodes.

    Args:
        location: Location (string or dict)
        geocoding: GeocodingService instance

    Returns:
        Dict with lat/lng or None if not found
    """
    if not location:
        return None

    # If dict with pre-computed coordinates (from canonicalization)
    if isinstance(location, dict):
        if "coordinates" in location and location["coordinates"]:
            return location["coordinates"]

        # Try to geocode the name
        name = location.get("name") or location.get("canonical_name")
        if name:
            return geocoding.geocode(name)

        return None

    # String location - geocode it
    if isinstance(location, str) and location.strip():
        return geocoding.geocode(location)

    return None


# ============================================================================
# LOCATION MATCHING (HYBRID: COORDINATES + STRING FALLBACK)
# ============================================================================

def match_location_simple(
    required_location: Union[str, Dict],
    candidate_location: Union[str, Dict],
    required_exclusions: List[str],
    candidate_exclusions: List[str],
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM
) -> bool:
    """
    Hybrid location matching: coordinates → canonical name → string fallback.

    Matching Rules:
    1. If required_location empty → always match (no location requirement)
    2. Try coordinate-based matching (if geocoding available)
    3. Fall back to canonical name matching
    4. Final fallback to string equality
    5. Check exclusions: candidate not in required exclusions, vice versa

    Args:
        required_location: Required location (string or dict with name/coordinates)
        candidate_location: Candidate location (string or dict)
        required_exclusions: Locations that requester excludes
        candidate_exclusions: Locations that candidate excludes
        max_distance_km: Maximum distance in km for coordinate matching

    Returns:
        True if location matches, False otherwise

    Examples:
        >>> match_location_simple("bangalore", "bengaluru", [], [])
        True  # Same coordinates via geocoding

        >>> match_location_simple("mumbai", "delhi", [], [])
        False  # Different locations

        >>> match_location_simple("bangalore", "bangalore", ["whitefield"], [])
        True  # bangalore not in exclusions

        >>> match_location_simple("whitefield", "whitefield", ["whitefield"], [])
        False  # whitefield is in required exclusions
    """
    # Normalize inputs
    required_name = _extract_location_name(required_location)
    candidate_name = _extract_location_name(candidate_location)

    # Rule 1: If no location requirement, always match
    if not required_name:
        return True

    # Rule 2: Try coordinate-based matching first
    coord_match = match_location_by_coordinates(
        required_location,
        candidate_location,
        max_distance_km
    )

    if coord_match is not None:
        # Coordinate matching succeeded (True or False)
        if not coord_match:
            return False
        # Coordinates match - continue to check exclusions
    else:
        # Coordinate matching failed - fall back to name matching

        # Try canonical name matching (from geocoding)
        canonical_match = _match_canonical_names(required_location, candidate_location)

        if canonical_match is not None:
            if not canonical_match:
                return False
            # Canonical names match - continue to check exclusions
        else:
            # Final fallback: simple string equality
            if required_name != candidate_name:
                return False

    # Rule 3: Check exclusions
    # Candidate location must not be in requester's exclusions
    if _is_location_in_exclusions(candidate_location, required_exclusions):
        return False

    # Requester's location must not be in candidate's exclusions
    if _is_location_in_exclusions(required_location, candidate_exclusions):
        return False

    return True


def _match_canonical_names(
    location1: Union[str, Dict],
    location2: Union[str, Dict]
) -> Optional[bool]:
    """
    Match locations using canonical names from geocoding.

    Canonical names are normalized official names (e.g., "Bengaluru" for "Bangalore").

    Args:
        location1: First location
        location2: Second location

    Returns:
        True if canonical names match
        False if canonical names differ
        None if canonical names not available
    """
    canonical1 = _get_canonical_name(location1)
    canonical2 = _get_canonical_name(location2)

    if canonical1 is None or canonical2 is None:
        return None

    return canonical1.lower() == canonical2.lower()


def _get_canonical_name(location: Union[str, Dict, None]) -> Optional[str]:
    """
    Get canonical name for a location.

    Checks for pre-computed canonical name in dict (from canonicalization).

    Args:
        location: Location (string or dict)

    Returns:
        Canonical name or None
    """
    if not location:
        return None

    if isinstance(location, dict):
        # Pre-computed canonical name from canonicalization
        if "canonical_name" in location and location["canonical_name"]:
            return location["canonical_name"]

    return None


def _is_location_in_exclusions(
    location: Union[str, Dict],
    exclusions: List[str]
) -> bool:
    """
    Check if a location is in the exclusion list.

    Uses coordinate-based matching for better accuracy.

    Args:
        location: Location to check
        exclusions: List of excluded location names

    Returns:
        True if location is in exclusions
    """
    if not exclusions:
        return False

    location_name = _extract_location_name(location)

    # Simple string match first
    if location_name in exclusions:
        return True

    # Try canonical name match
    canonical = _get_canonical_name(location)
    if canonical and canonical.lower() in exclusions:
        return True

    # Try coordinate-based exclusion check (more accurate)
    # Check if location is within threshold of any excluded location
    for excluded_name in exclusions:
        coord_match = match_location_by_coordinates(
            location,
            excluded_name,
            max_distance_km=DEFAULT_MAX_DISTANCE_KM
        )
        if coord_match is True:
            return True

    return False


def match_location_route(
    required_route: Dict,
    candidate_route: Dict,
    required_exclusions: List[str],
    candidate_exclusions: List[str],
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM
) -> bool:
    """
    Match route-based locations (origin → destination) using coordinates.

    For route mode, both origin and destination must match within distance threshold.

    Args:
        required_route: Required route {"origin": "X", "destination": "Y", "origin_coordinates": {...}, ...}
        candidate_route: Candidate route {"origin": "A", "destination": "B", ...}
        required_exclusions: Location exclusions from requester
        candidate_exclusions: Location exclusions from candidate
        max_distance_km: Maximum distance in km for coordinate matching

    Returns:
        True if routes match, False otherwise

    Examples:
        >>> match_location_route(
        ...     {"origin": "bangalore", "destination": "goa"},
        ...     {"origin": "bengaluru", "destination": "goa"},  # Bangalore alias
        ...     [], []
        ... )
        True

        >>> match_location_route(
        ...     {"origin": "bangalore", "destination": "goa"},
        ...     {"origin": "delhi", "destination": "goa"},
        ...     [], []
        ... )
        False
    """
    # Build origin/destination location dicts for coordinate matching
    req_origin_loc = _build_route_point_location(required_route, "origin")
    req_dest_loc = _build_route_point_location(required_route, "destination")
    cand_origin_loc = _build_route_point_location(candidate_route, "origin")
    cand_dest_loc = _build_route_point_location(candidate_route, "destination")

    # Match origin using coordinate-based matching
    origin_match = _match_route_points(req_origin_loc, cand_origin_loc, max_distance_km)
    if not origin_match:
        return False

    # Match destination using coordinate-based matching
    dest_match = _match_route_points(req_dest_loc, cand_dest_loc, max_distance_km)
    if not dest_match:
        return False

    # Check exclusions for candidate origin/destination
    if _is_location_in_exclusions(cand_origin_loc, required_exclusions):
        return False
    if _is_location_in_exclusions(cand_dest_loc, required_exclusions):
        return False

    # Check exclusions for required origin/destination
    if _is_location_in_exclusions(req_origin_loc, candidate_exclusions):
        return False
    if _is_location_in_exclusions(req_dest_loc, candidate_exclusions):
        return False

    return True


def _build_route_point_location(route: Dict, point_type: str) -> Dict:
    """
    Build a location dict from route point (origin or destination).

    Args:
        route: Route dict with origin/destination fields
        point_type: "origin" or "destination"

    Returns:
        Location dict with name and coordinates (if available)
    """
    location = {}

    # Get name
    name = route.get(point_type, "")
    if name:
        location["name"] = name.lower().strip() if isinstance(name, str) else name

    # Get coordinates (from canonicalization)
    coord_key = f"{point_type}_coordinates"
    if coord_key in route and route[coord_key]:
        location["coordinates"] = route[coord_key]

    # Get canonical name (from canonicalization)
    canonical_key = f"{point_type}_canonical"
    if canonical_key in route and route[canonical_key]:
        location["canonical_name"] = route[canonical_key]

    return location


def _match_route_points(
    point1: Dict,
    point2: Dict,
    max_distance_km: float
) -> bool:
    """
    Match two route points (origin or destination).

    Uses coordinate matching with string fallback.

    Args:
        point1: First point location dict
        point2: Second point location dict
        max_distance_km: Maximum distance for match

    Returns:
        True if points match
    """
    # Try coordinate-based matching
    coord_match = match_location_by_coordinates(point1, point2, max_distance_km)
    if coord_match is not None:
        return coord_match

    # Try canonical name matching
    canonical_match = _match_canonical_names(point1, point2)
    if canonical_match is not None:
        return canonical_match

    # Final fallback: string equality
    name1 = _extract_location_name(point1)
    name2 = _extract_location_name(point2)

    return name1 == name2


def match_location_v2(
    required_location: Union[str, Dict],
    required_mode: str,
    required_exclusions: List[str],
    candidate_location: Union[str, Dict],
    candidate_mode: str,
    candidate_exclusions: List[str],
    max_distance_km: float = DEFAULT_MAX_DISTANCE_KM
) -> bool:
    """
    V3 location matching with mode support and coordinate-based distance.

    Modes:
    - near_me: Match if locations within distance threshold
    - explicit: Strict coordinate/name matching required
    - target_only: Match any candidate at/near target
    - route: Both origin and destination must match (within threshold)
    - global: Always match (remote/anywhere)

    Args:
        required_location: Requester's location
        required_mode: Requester's location mode
        required_exclusions: Requester's location exclusions
        candidate_location: Candidate's location
        candidate_mode: Candidate's location mode
        candidate_exclusions: Candidate's location exclusions
        max_distance_km: Maximum distance in km for coordinate matching

    Returns:
        True if locations compatible, False otherwise
    """
    # Normalize modes
    required_mode = required_mode.lower().strip() if required_mode else "near_me"
    candidate_mode = candidate_mode.lower().strip() if candidate_mode else "near_me"

    # Mode: global (remote/anywhere)
    # Always matches regardless of location
    if required_mode == "global" or candidate_mode == "global":
        return True

    # Mode: route
    # Both must have route structure
    if required_mode == "route" or candidate_mode == "route":
        # Check if both have route structure
        req_is_route = isinstance(required_location, dict) and "origin" in required_location
        cand_is_route = isinstance(candidate_location, dict) and "origin" in candidate_location

        if req_is_route and cand_is_route:
            return match_location_route(
                required_location,
                candidate_location,
                required_exclusions,
                candidate_exclusions,
                max_distance_km
            )
        else:
            # Route mode but missing route structure → no match
            return False

    # Mode: target_only
    # Requester is moving to target, will match any candidate at/near target
    if required_mode == "target_only":
        # Check if requester's target is in candidate's exclusions
        if _is_location_in_exclusions(required_location, candidate_exclusions):
            return False
        return True

    # Mode: explicit or near_me
    # Use coordinate-based matching with fallback
    return match_location_simple(
        required_location,
        candidate_location,
        required_exclusions,
        candidate_exclusions,
        max_distance_km
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_location_name(location: Union[str, Dict, None]) -> str:
    """
    Extract location name from location object or string.

    Args:
        location: Location (string or dict with "name" field)

    Returns:
        Normalized location name (lowercase, trimmed)

    Examples:
        >>> _extract_location_name("Bangalore")
        'bangalore'

        >>> _extract_location_name({"name": "Bangalore"})
        'bangalore'

        >>> _extract_location_name(None)
        ''

        >>> _extract_location_name({})
        ''
    """
    if not location:
        return ""

    if isinstance(location, str):
        return location.lower().strip()

    if isinstance(location, dict):
        name = location.get("name", "")
        return name.lower().strip() if name else ""

    return ""


def normalize_location_exclusions(exclusions: List[str]) -> List[str]:
    """
    Normalize location exclusions to lowercase, trimmed strings.

    Args:
        exclusions: List of location exclusions

    Returns:
        Normalized list

    Examples:
        >>> normalize_location_exclusions(["Whitefield", "  Airport  "])
        ['whitefield', 'airport']
    """
    if not exclusions:
        return []

    result = []
    for e in exclusions:
        if not e:
            continue
        if isinstance(e, dict) and "concept_id" in e:
            concept_id = e.get("concept_id", "")
            if concept_id:
                result.append(str(concept_id).lower().strip())
        elif isinstance(e, str):
            result.append(e.lower().strip())
    return result


# ============================================================================
# COMPATIBILITY WRAPPER (for existing code)
# ============================================================================

def match_location_constraints(
    required_location_obj: Dict,
    candidate_other_obj: Dict,
    location_exclusions: List[str] = None,
    other_location_exclusions: List[str] = None,
    max_distance_km: float = None
) -> bool:
    """
    Compatibility wrapper for OLD schema location matching interface.

    Maps OLD interface to V3 matching logic with coordinate support.

    OLD schema format (after transformation from NEW):
    {
        "location": "bangalore",  # string or dict with coordinates
        "locationmode": "explicit",
        "locationexclusions": ["whitefield"]
    }

    Args:
        required_location_obj: Dict with "location", "locationmode", "locationexclusions"
        candidate_other_obj: Dict with "location", "locationmode", "locationexclusions"
        location_exclusions: Optional override for required exclusions
        other_location_exclusions: Optional override for candidate exclusions
        max_distance_km: Maximum distance for matching (uses settings default if None)

    Returns:
        True if locations match, False otherwise
    """
    # Get max_distance_km from settings if not provided
    if max_distance_km is None:
        max_distance_km = _get_max_distance_from_settings()

    # Extract from dicts
    required_location = required_location_obj.get("location", "")
    required_mode = required_location_obj.get("locationmode", "near_me")
    required_exclusions = location_exclusions or required_location_obj.get("locationexclusions", [])

    candidate_location = candidate_other_obj.get("location", "")
    candidate_mode = candidate_other_obj.get("locationmode", "near_me")
    candidate_exclusions = other_location_exclusions or candidate_other_obj.get("locationexclusions", [])

    # Normalize exclusions
    required_exclusions = normalize_location_exclusions(required_exclusions)
    candidate_exclusions = normalize_location_exclusions(candidate_exclusions)

    # Call v3 matching
    return match_location_v2(
        required_location,
        required_mode,
        required_exclusions,
        candidate_location,
        candidate_mode,
        candidate_exclusions,
        max_distance_km
    )


def _get_max_distance_from_settings() -> float:
    """
    Get max_distance_km from centralized settings.

    Returns:
        Max distance in km (default 50.0 if settings unavailable)
    """
    try:
        from src.config.settings import settings
        return getattr(settings, "location_max_distance_km", DEFAULT_MAX_DISTANCE_KM)
    except (ImportError, AttributeError):
        return DEFAULT_MAX_DISTANCE_KM
