"""
WordsAPI wrapper via RapidAPI for definition and synonym lookups.

WordsAPI provides:
- Definitions grouped by sense (implicit disambiguation)
- Synonyms per definition
- type_of / has_types hierarchy
- 2,500 requests/day on free tier, $10/mo for 25K

Requires RAPIDAPI_KEY env var. Gracefully skips if not set.
"""

import os
import time
import requests
from typing import Dict, List, Optional
from threading import Lock


class WordsAPIClient:
    """
    Client for querying WordsAPI via RapidAPI.

    Key feature: returns synonyms grouped by definition, providing implicit
    sense disambiguation that other sources lack.

    Includes TTL cache and daily rate limiting.
    Thread-safe via Lock.
    """

    BASE_URL = "https://wordsapiv1.p.rapidapi.com/words"
    DEFAULT_CACHE_TTL = 3600  # 1 hour
    DAILY_LIMIT = 2400  # Leave buffer from 2500 free tier

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL
    ):
        self._api_key = api_key or os.getenv("RAPIDAPI_KEY", "")
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = Lock()
        self._daily_count = 0
        self._daily_reset_time = time.time()
        self._session = requests.Session()

        if self._api_key:
            self._session.headers.update({
                "X-RapidAPI-Key": self._api_key,
                "X-RapidAPI-Host": "wordsapiv1.p.rapidapi.com",
                "User-Agent": "SingletapMatchingEngine/1.0"
            })

    def is_available(self) -> bool:
        """Check if WordsAPI is available (key set + within rate limit)."""
        if not self._api_key:
            return False

        with self._lock:
            # Reset daily counter if 24h have passed
            if time.time() - self._daily_reset_time > 86400:
                self._daily_count = 0
                self._daily_reset_time = time.time()
            return self._daily_count < self.DAILY_LIMIT

    def _increment_counter(self):
        with self._lock:
            if time.time() - self._daily_reset_time > 86400:
                self._daily_count = 0
                self._daily_reset_time = time.time()
            self._daily_count += 1

    def _get_cached(self, key: str) -> Optional[any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry["fetched_at"]) < self._cache_ttl:
                return entry["value"]
            return None

    def _set_cached(self, key: str, value: any) -> None:
        with self._lock:
            self._cache[key] = {
                "value": value,
                "fetched_at": time.time()
            }

    def get_definitions_with_synonyms(self, term: str) -> List[Dict]:
        """
        Get definitions with associated synonyms for a term.

        Returns list of dicts:
        [
            {
                "definition": "a motor vehicle with four wheels...",
                "part_of_speech": "noun",
                "synonyms": ["automobile", "auto", "machine"],
                "type_of": ["motor vehicle"],
                "has_types": ["sedan", "coupe", "convertible"],
            },
            ...
        ]

        Key value: synonyms are grouped by definition (sense), enabling
        implicit disambiguation without embedding scoring.
        """
        if not self.is_available():
            return []

        cache_key = f"defs:{term}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = self._session.get(
                f"{self.BASE_URL}/{term}",
                timeout=5
            )
            self._increment_counter()
            response.raise_for_status()

            data = response.json()
            results_raw = data.get("results", [])

            results = []
            for entry in results_raw:
                results.append({
                    "definition": entry.get("definition", ""),
                    "part_of_speech": entry.get("partOfSpeech", ""),
                    "synonyms": entry.get("synonyms", []),
                    "type_of": entry.get("typeOf", []),
                    "has_types": entry.get("hasTypes", []),
                    "also": entry.get("also", []),
                    "similar_to": entry.get("similarTo", []),
                })

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"WordsAPI error for '{term}': {e}")
            return []

    def get_synonyms_flat(self, term: str) -> List[str]:
        """Get all synonyms across all definitions (deduplicated)."""
        defs = self.get_definitions_with_synonyms(term)
        synonyms = set()
        for d in defs:
            for s in d.get("synonyms", []):
                synonyms.add(s.lower())
        return sorted(synonyms)


# Global singleton
_wordsapi_client: Optional[WordsAPIClient] = None


def get_wordsapi_client() -> WordsAPIClient:
    """Get singleton WordsAPI client instance."""
    global _wordsapi_client
    if _wordsapi_client is None:
        _wordsapi_client = WordsAPIClient()
    return _wordsapi_client
