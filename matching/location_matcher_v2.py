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
1. If coordinates available -> use haversine distance (configurable threshold)
2. Fall back to canonical name matching
3. Final fallback to string equality
4. Exclusion list matching

Authority: GLOBAL_REFERENCE_CONTEXT.md (NEW schema)
Dependencies: services.external.geocoding_service
"""

from typing import Dict, List, Union, Optional
from services.external.geocoding_service import get_geocoding_service


# ============================================================================
# CONFIGURATION
# ============================================================================

# Default distance threshold for "same location" matching (in km)
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

    Returns:
        True if within distance threshold
        False if outside distance threshold
        None if either location cannot be geocoded (trigger fallback)
    """
    geocoding = get_geocoding_service()

    coords1 = _get_coordinates(location1, geocoding)
    coords2 = _get_coordinates(location2, geocoding)

    if coords1 is None or coords2 is None:
        return None

    distance = geocoding._haversine_distance(
        coords1["lat"], coords1["lng"],
        coords2["lat"], coords2["lng"]
    )

    return distance <= max_distance_km


def _get_coordinates(
    location: Union[str, Dict, None],
    geocoding
) -> Optional[Dict]:
    """Get coordinates for a location (from pre-computed dict or geocoding API)."""
    if not location:
        return None

    if isinstance(location, dict):
        if "coordinates" in location and location["coordinates"]:
            return location["coordinates"]

        name = location.get("name") or location.get("canonical_name")
        if name:
            return geocoding.geocode(name)

        return None

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
    Hybrid location matching: coordinates -> canonical name -> string fallback.

    Matching Rules:
    1. If required_location empty -> always match (no location requirement)
    2. Try coordinate-based matching (if geocoding available)
    3. Fall back to canonical name matching
    4. Final fallback to string equality
    5. Check exclusions: candidate not in required exclusions, vice versa
    """
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
        if not coord_match:
            return False
        # Coordinates match - continue to check exclusions
    else:
        # Coordinate matching failed - fall back to name matching
        canonical_match = _match_canonical_names(required_location, candidate_location)

        if canonical_match is not None:
            if not canonical_match:
                return False
        else:
            # Final fallback: simple string equality
            if required_name != candidate_name:
                return False

    # Rule 3: Check exclusions
    if _is_location_in_exclusions(candidate_location, required_exclusions):
        return False

    if _is_location_in_exclusions(required_location, candidate_exclusions):
        return False

    return True


def _match_canonical_names(
    location1: Union[str, Dict],
    location2: Union[str, Dict]
) -> Optional[bool]:
    """Match locations using canonical names from geocoding."""
    canonical1 = _get_canonical_name(location1)
    canonical2 = _get_canonical_name(location2)

    if canonical1 is None or canonical2 is None:
        return None

    return canonical1.lower() == canonical2.lower()


def _get_canonical_name(location: Union[str, Dict, None]) -> Optional[str]:
    """Get canonical name for a location."""
    if not location:
        return None

    if isinstance(location, dict):
        if "canonical_name" in location and location["canonical_name"]:
            return location["canonical_name"]

    return None


def _is_location_in_exclusions(
    location: Union[str, Dict],
    exclusions: List[str]
) -> bool:
    """Check if a location is in the exclusion list."""
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

    # Try coordinate-based exclusion check
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
    Match route-based locations (origin -> destination) using coordinates.

    For route mode, both origin and destination must match within distance threshold.
    """
    req_origin_loc = _build_route_point_location(required_route, "origin")
    req_dest_loc = _build_route_point_location(required_route, "destination")
    cand_origin_loc = _build_route_point_location(candidate_route, "origin")
    cand_dest_loc = _build_route_point_location(candidate_route, "destination")

    # Match origin
    origin_match = _match_route_points(req_origin_loc, cand_origin_loc, max_distance_km)
    if not origin_match:
        return False

    # Match destination
    dest_match = _match_route_points(req_dest_loc, cand_dest_loc, max_distance_km)
    if not dest_match:
        return False

    # Check exclusions
    if _is_location_in_exclusions(cand_origin_loc, required_exclusions):
        return False
    if _is_location_in_exclusions(cand_dest_loc, required_exclusions):
        return False
    if _is_location_in_exclusions(req_origin_loc, candidate_exclusions):
        return False
    if _is_location_in_exclusions(req_dest_loc, candidate_exclusions):
        return False

    return True


def _build_route_point_location(route: Dict, point_type: str) -> Dict:
    """Build a location dict from route point (origin or destination)."""
    location = {}

    name = route.get(point_type, "")
    if name:
        location["name"] = name.lower().strip() if isinstance(name, str) else name

    coord_key = f"{point_type}_coordinates"
    if coord_key in route and route[coord_key]:
        location["coordinates"] = route[coord_key]

    canonical_key = f"{point_type}_canonical"
    if canonical_key in route and route[canonical_key]:
        location["canonical_name"] = route[canonical_key]

    return location


def _match_route_points(
    point1: Dict,
    point2: Dict,
    max_distance_km: float
) -> bool:
    """Match two route points using coordinate matching with string fallback."""
    coord_match = match_location_by_coordinates(point1, point2, max_distance_km)
    if coord_match is not None:
        return coord_match

    canonical_match = _match_canonical_names(point1, point2)
    if canonical_match is not None:
        return canonical_match

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
    """
    # Normalize modes
    required_mode = required_mode.lower().strip() if required_mode else "near_me"
    candidate_mode = candidate_mode.lower().strip() if candidate_mode else "near_me"

    # Mode: global
    if required_mode == "global" or candidate_mode == "global":
        return True

    # Mode: route
    if required_mode == "route" or candidate_mode == "route":
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
            return False

    # Mode: target_only
    if required_mode == "target_only":
        if _is_location_in_exclusions(required_location, candidate_exclusions):
            return False
        return True

    # Mode: explicit or near_me
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
    """Extract location name from location object or string."""
    if not location:
        return ""

    if isinstance(location, str):
        return location.lower().strip()

    if isinstance(location, dict):
        name = location.get("name", "")
        return name.lower().strip() if name else ""

    return ""


def normalize_location_exclusions(exclusions: List[str]) -> List[str]:
    """Normalize location exclusions to lowercase, trimmed strings."""
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
    """
    if max_distance_km is None:
        max_distance_km = DEFAULT_MAX_DISTANCE_KM

    required_location = required_location_obj.get("location", "")
    required_mode = required_location_obj.get("locationmode", "near_me")
    required_exclusions = location_exclusions or required_location_obj.get("locationexclusions", [])

    candidate_location = candidate_other_obj.get("location", "")
    candidate_mode = candidate_other_obj.get("locationmode", "near_me")
    candidate_exclusions = other_location_exclusions or candidate_other_obj.get("locationexclusions", [])

    required_exclusions = normalize_location_exclusions(required_exclusions)
    candidate_exclusions = normalize_location_exclusions(candidate_exclusions)

    return match_location_v2(
        required_location,
        required_mode,
        required_exclusions,
        candidate_location,
        candidate_mode,
        candidate_exclusions,
        max_distance_km
    )
