"""
Geocoding Service: Location Name to Coordinates.

Uses OpenStreetMap Nominatim API for free geocoding.
Includes caching to avoid repeated API calls.

Features:
- Nominatim geocoding (free, no API key)
- File-based caching (like ontology_cache.json)
- Rate limiting (1 request/second)
- Haversine distance calculation
- Alias resolution ("Bangalore" → coordinates for "Bengaluru")

Usage:
    from src.services.external.geocoding_service import get_geocoding_service

    service = get_geocoding_service()

    # Geocode a location
    coords = service.geocode("Bangalore")
    # → {"lat": 12.9716, "lng": 77.5946, "canonical_name": "Bengaluru"}

    # Calculate distance
    distance = service.distance("Bangalore", "Mumbai")
    # → 985.0 (km)

    # Check if within range
    is_near = service.is_within_distance("Bangalore", "Bengaluru", max_km=50)
    # → True

Author: Claude (Geocoding Service)
Date: 2026-02-05
"""

import json
import math
import os
import time
from typing import Dict, Optional, Tuple
from pathlib import Path


class GeocodingService:
    """
    Geocoding service using OpenStreetMap Nominatim.

    Provides:
    - Location name → coordinates conversion
    - Distance calculation between locations
    - File-based caching for efficiency
    - Rate limiting to respect Nominatim usage policy
    """

    # Nominatim API endpoint
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

    # Rate limit: 1 request per second (Nominatim policy)
    RATE_LIMIT_SECONDS = 1.1

    def __init__(
        self,
        cache_file: Optional[str] = None,
        user_agent: str = "VriddhiMatchingEngine/1.0 (vriddhi@example.com)"
    ):
        """
        Initialize geocoding service.

        Args:
            cache_file: Path to cache file. If None, uses default location.
            user_agent: User agent string for Nominatim API (required by their policy)
        """
        if cache_file is None:
            # Default: geocoding_cache.json in project root
            cache_file = "geocoding_cache.json"

        self.cache_file = cache_file
        self.user_agent = user_agent
        self.cache = self._load_cache()
        self._last_request_time = 0

    def _load_cache(self) -> Dict:
        """Load cache from JSON file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load geocoding cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save geocoding cache: {e}")

    def _rate_limit(self):
        """Enforce rate limit (1 request per second)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            time.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = time.time()

    def geocode(self, location_name: str) -> Optional[Dict]:
        """
        Convert location name to coordinates.

        Args:
            location_name: Location name (e.g., "Bangalore", "New York City")

        Returns:
            Dict with lat, lng, canonical_name, or None if not found
            Example: {"lat": 12.9716, "lng": 77.5946, "canonical_name": "Bengaluru"}
        """
        if not location_name:
            return None

        # Normalize for cache key
        cache_key = location_name.lower().strip()

        # Check cache
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Query Nominatim API
        try:
            import requests

            self._rate_limit()

            params = {
                "q": location_name,
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            }
            headers = {
                "User-Agent": self.user_agent
            }

            response = requests.get(
                self.NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.ok and response.json():
                result = response.json()[0]

                coords = {
                    "lat": float(result["lat"]),
                    "lng": float(result["lon"]),
                    "canonical_name": self._extract_canonical_name(result),
                    "display_name": result.get("display_name", ""),
                    "type": result.get("type", ""),
                    "class": result.get("class", "")
                }

                # Cache the result
                self.cache[cache_key] = coords
                self._save_cache()

                return coords

        except ImportError:
            print("Warning: requests library not available for geocoding")
        except Exception as e:
            print(f"Geocoding error for '{location_name}': {e}")

        # Cache negative result to avoid repeated failed lookups
        self.cache[cache_key] = None
        self._save_cache()

        return None

    def _extract_canonical_name(self, result: Dict) -> str:
        """
        Extract canonical name from Nominatim result.

        Args:
            result: Nominatim API result

        Returns:
            Canonical location name
        """
        # Try to get city/town name from address details
        address = result.get("address", {})

        # Priority: city > town > village > county > state
        for key in ["city", "town", "village", "municipality", "county", "state"]:
            if key in address:
                return address[key]

        # Fallback: first part of display_name
        display_name = result.get("display_name", "")
        if display_name:
            return display_name.split(",")[0].strip()

        return result.get("name", "")

    def distance(
        self,
        location1: str,
        location2: str
    ) -> Optional[float]:
        """
        Calculate distance between two locations in kilometers.

        Uses Haversine formula for great-circle distance.

        Args:
            location1: First location name
            location2: Second location name

        Returns:
            Distance in kilometers, or None if either location can't be geocoded
        """
        coords1 = self.geocode(location1)
        coords2 = self.geocode(location2)

        if not coords1 or not coords2:
            return None

        return self._haversine_distance(
            coords1["lat"], coords1["lng"],
            coords2["lat"], coords2["lng"]
        )

    def _haversine_distance(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float
    ) -> float:
        """
        Calculate Haversine distance between two coordinates.

        Args:
            lat1, lng1: First coordinate
            lat2, lng2: Second coordinate

        Returns:
            Distance in kilometers
        """
        # Earth's radius in kilometers
        R = 6371.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def is_within_distance(
        self,
        location1: str,
        location2: str,
        max_km: float = 50.0
    ) -> bool:
        """
        Check if two locations are within a given distance.

        Args:
            location1: First location name
            location2: Second location name
            max_km: Maximum distance in kilometers (default: 50km)

        Returns:
            True if within distance, False otherwise
        """
        dist = self.distance(location1, location2)

        if dist is None:
            return False

        return dist <= max_km

    def get_coordinates(self, location_name: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates as tuple for a location.

        Args:
            location_name: Location name

        Returns:
            Tuple of (lat, lng) or None
        """
        coords = self.geocode(location_name)
        if coords:
            return (coords["lat"], coords["lng"])
        return None

    def clear_cache(self):
        """Clear the geocoding cache."""
        self.cache = {}
        self._save_cache()

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total = len(self.cache)
        found = sum(1 for v in self.cache.values() if v is not None)
        not_found = total - found

        return {
            "total_entries": total,
            "found": found,
            "not_found": not_found
        }


# Singleton instance
_geocoding_service_instance: Optional[GeocodingService] = None


def get_geocoding_service() -> GeocodingService:
    """
    Get singleton GeocodingService instance.

    Uses settings from src.config.settings for configuration.

    Returns:
        Shared GeocodingService instance
    """
    global _geocoding_service_instance
    if _geocoding_service_instance is None:
        # Get settings from centralized config
        try:
            from src.config.settings import settings
            cache_file = getattr(settings, "geocoding_cache_file", "geocoding_cache.json")
            user_agent = getattr(settings, "geocoding_user_agent", "VriddhiMatchingEngine/1.0")
        except (ImportError, AttributeError):
            cache_file = "geocoding_cache.json"
            user_agent = "VriddhiMatchingEngine/1.0"

        _geocoding_service_instance = GeocodingService(
            cache_file=cache_file,
            user_agent=user_agent
        )
    return _geocoding_service_instance
