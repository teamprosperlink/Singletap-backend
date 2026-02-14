"""
Datamuse API wrapper for synonym and semantic similarity lookups.

Datamuse is a free word-finding query engine:
- No API key required
- 100,000 requests/day limit
- Provides synonyms, related words, means-like queries
- API: https://api.datamuse.com/words

Used by the disambiguator as one of 5 candidate sources.
"""

import time
import requests
from typing import Dict, List, Optional
from threading import Lock


class DatamuseClient:
    """
    Client for querying the Datamuse API.

    Provides synonym and semantic similarity lookups with TTL caching.
    Thread-safe via Lock.
    """

    BASE_URL = "https://api.datamuse.com/words"
    DEFAULT_CACHE_TTL = 3600  # 1 hour

    def __init__(self, cache_ttl_seconds: int = DEFAULT_CACHE_TTL):
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = Lock()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "SingletapMatchingEngine/1.0"
        })

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

    def get_synonyms(self, term: str, topic: Optional[str] = None) -> List[Dict]:
        """
        Get synonyms for a term.

        Args:
            term: Word to find synonyms for.
            topic: Optional topic hint for relevance ranking.

        Returns:
            List of dicts: [{"word": "used", "score": 3000, "tags": ["syn"]}]
        """
        cache_key = f"syn:{term}:{topic}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {"rel_syn": term}
            if topic:
                params["topics"] = topic

            response = self._session.get(
                self.BASE_URL, params=params, timeout=5
            )
            response.raise_for_status()
            results = response.json()

            if not isinstance(results, list):
                results = []

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Datamuse synonym error for '{term}': {e}")
            return []

    def get_means_like(self, term: str, topic: Optional[str] = None) -> List[Dict]:
        """
        Get words that mean like the given term (broader semantic matches).

        Args:
            term: Word/phrase to find semantic matches for.
            topic: Optional topic hint.

        Returns:
            List of dicts: [{"word": "automobile", "score": 95000, "tags": ["syn","n"]}]
        """
        cache_key = f"ml:{term}:{topic}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {"ml": term}
            if topic:
                params["topics"] = topic

            response = self._session.get(
                self.BASE_URL, params=params, timeout=5
            )
            response.raise_for_status()
            results = response.json()

            if not isinstance(results, list):
                results = []

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Datamuse means-like error for '{term}': {e}")
            return []

    def get_definitions(self, term: str) -> List[Dict]:
        """
        Get definitions for a term (requires md=d flag).

        Returns:
            List of dicts with word and defs field.
        """
        cache_key = f"def:{term}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {"sp": term, "md": "d", "max": 1}
            response = self._session.get(
                self.BASE_URL, params=params, timeout=5
            )
            response.raise_for_status()
            results = response.json()

            if not isinstance(results, list):
                results = []

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Datamuse definitions error for '{term}': {e}")
            return []


# Global singleton
_datamuse_client: Optional[DatamuseClient] = None


def get_datamuse_client() -> DatamuseClient:
    """Get singleton Datamuse client instance."""
    global _datamuse_client
    if _datamuse_client is None:
        _datamuse_client = DatamuseClient()
    return _datamuse_client
