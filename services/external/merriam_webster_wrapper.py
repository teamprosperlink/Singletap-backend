"""
Merriam-Webster Collegiate Dictionary API Wrapper

Provides definition and synonym lookup for terms not in WordNet.
Useful for modern slang, tech terms, and recent additions to English.

API: https://dictionaryapi.com/
Free tier: 1,000 requests/day (non-commercial)
Get API key: https://dictionaryapi.com/register/index

Usage:
    from services.external.merriam_webster_wrapper import get_merriam_webster_client

    client = get_merriam_webster_client()
    if client.is_available():
        result = client.get_definition("laptop")
        print(result["definition"])
        print(result["synonyms"])
"""

import os
import time
import requests
from typing import Dict, List, Optional
from threading import Lock


class MerriamWebsterClient:
    """
    Client for Merriam-Webster Collegiate Dictionary API.

    Features:
    - Definition lookup
    - Synonym extraction
    - Part of speech tagging
    - TTL cache (1 hour)
    - Daily rate limiting (1000/day)
    """

    BASE_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json"
    DEFAULT_CACHE_TTL = 3600  # 1 hour
    DAILY_LIMIT = 1000

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL
    ):
        self.api_key = api_key or os.getenv("MERRIAM_WEBSTER_API_KEY", "")

        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = Lock()
        self._daily_counter = 0
        self._last_reset = time.time()

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "SingletapMatchingEngine/1.0",
            "Accept": "application/json"
        })

    def is_available(self) -> bool:
        """
        Check if API is available (key set and within daily limit).

        Returns:
            True if can make API calls, False otherwise
        """
        if not self.api_key:
            return False

        # Reset counter daily
        if time.time() - self._last_reset > 86400:  # 24 hours
            self._daily_counter = 0
            self._last_reset = time.time()

        return self._daily_counter < self.DAILY_LIMIT

    def _get_cached(self, key: str) -> Optional[Dict]:
        """Get value from cache if within TTL."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry["fetched_at"]) < self._cache_ttl:
                return entry["value"]
            return None

    def _set_cached(self, key: str, value: Dict) -> None:
        """Store value in cache with current timestamp."""
        with self._lock:
            self._cache[key] = {
                "value": value,
                "fetched_at": time.time()
            }

    def get_definition(self, term: str) -> Optional[Dict]:
        """
        Get definition and synonyms for a term.

        Args:
            term: Word/phrase to look up

        Returns:
            {
                "term": "laptop",
                "definition": "a portable computer small enough to use in your lap",
                "synonyms": ["notebook", "portable computer"],
                "part_of_speech": "noun"
            }

            Returns None if:
            - API key not set
            - Daily limit exceeded
            - Term not found
            - API error
        """
        if not self.is_available():
            return None

        # Check cache
        cache_key = f"def:{term.lower()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Make API request
            params = {"key": self.api_key}
            url = f"{self.BASE_URL}/{term}"

            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()

            # Increment counter
            with self._lock:
                self._daily_counter += 1

            data = response.json()

            if not isinstance(data, list) or len(data) == 0:
                return None

            # Check if response is suggestions (list of strings) rather than definitions
            if isinstance(data[0], str):
                # These are suggested spellings, not definitions
                return None

            # Parse first entry
            entry = data[0]

            # Extract definition
            definition = None
            if "shortdef" in entry and entry["shortdef"]:
                definition = entry["shortdef"][0]

            # Extract part of speech
            part_of_speech = entry.get("fl", "")

            # Extract synonyms (if available)
            synonyms = []
            if "meta" in entry and "stems" in entry["meta"]:
                synonyms = [s for s in entry["meta"]["stems"] if s != term.lower()]

            result = {
                "term": term,
                "definition": definition or "",
                "synonyms": synonyms,
                "part_of_speech": part_of_speech
            }

            # Cache result
            self._set_cached(cache_key, result)

            return result

        except requests.exceptions.RequestException as e:
            print(f"Merriam-Webster API error for '{term}': {e}")
            return None

        except (KeyError, IndexError, ValueError) as e:
            print(f"Merriam-Webster parse error for '{term}': {e}")
            return None

    def get_all_senses(self, term: str) -> List[Dict]:
        """
        Get all definitions for a term (all senses).

        Returns list of definition dicts, one per sense.
        """
        if not self.is_available():
            return []

        try:
            params = {"key": self.api_key}
            url = f"{self.BASE_URL}/{term}"

            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()

            with self._lock:
                self._daily_counter += 1

            data = response.json()

            if not isinstance(data, list):
                return []

            # Filter out suggestion lists
            if data and isinstance(data[0], str):
                return []

            senses = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue

                # Extract all definitions for this entry
                shortdefs = entry.get("shortdef", [])
                part_of_speech = entry.get("fl", "")

                for idx, definition in enumerate(shortdefs):
                    senses.append({
                        "term": term,
                        "definition": definition,
                        "part_of_speech": part_of_speech,
                        "sense_number": idx + 1
                    })

            return senses

        except Exception as e:
            print(f"Merriam-Webster multi-sense error for '{term}': {e}")
            return []


# Global singleton instance
_merriam_webster_client: Optional[MerriamWebsterClient] = None


def get_merriam_webster_client() -> MerriamWebsterClient:
    """Get singleton Merriam-Webster client instance."""
    global _merriam_webster_client

    if _merriam_webster_client is None:
        _merriam_webster_client = MerriamWebsterClient()

    return _merriam_webster_client
