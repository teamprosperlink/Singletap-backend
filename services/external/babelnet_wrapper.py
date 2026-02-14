"""
BabelNet API wrapper for multilingual synonym and concept resolution.

BabelNet is a multilingual encyclopedic dictionary and semantic network that provides:
- Synsets with rich synonym data across 500+ languages
- Hypernym/hyponym relations
- Integration of WordNet, Wikipedia, Wikidata, and other sources

API: https://babelnet.io/v9/
Free tier: 1000 requests/day
"""

import os
import time
import requests
import numpy as np
from typing import Dict, List, Optional, Tuple
from threading import Lock


class BabelNetClient:
    """
    Client for querying BabelNet REST API v9.

    Provides synonym lookup, concept search, and hypernym resolution.
    Includes in-memory TTL cache to minimize API calls (1000/day free tier).
    """

    BASE_URL = "https://babelnet.io/v9"
    DEFAULT_CACHE_TTL = 3600  # 1 hour

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL
    ):
        self.api_key = api_key or os.getenv("BABELNET_API_KEY", "")
        if not self.api_key:
            print("WARNING: BABELNET_API_KEY not set. BabelNet lookups will fail.")

        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = Lock()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "SingletapMatchingEngine/1.0",
            "Accept-Encoding": "gzip"
        })

    # ── Cache helpers ──

    def _get_cached(self, key: str) -> Optional[any]:
        """Get value from cache if within TTL."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry["fetched_at"]) < self._cache_ttl:
                return entry["value"]
            return None

    def _set_cached(self, key: str, value: any) -> None:
        """Store value in cache with current timestamp."""
        with self._lock:
            self._cache[key] = {
                "value": value,
                "fetched_at": time.time()
            }

    # ── Synset ID search ──

    def get_synset_ids(
        self, term: str, language: str = "EN", pos: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for BabelNet synset IDs matching a term.

        Args:
            term: The word/phrase to search
            language: Language code (EN, ES, FR, etc.)
            pos: Optional POS filter (NOUN, VERB, ADJ, ADV)

        Returns list of {id, pos, source} dicts.
        """
        cache_key = f"synset_ids:{term}:{language}:{pos}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "lemma": term,
                "searchLang": language,
                "key": self.api_key
            }
            if pos:
                params["pos"] = pos

            response = self._session.get(
                f"{self.BASE_URL}/getSynsetIds",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            results = response.json()
            if not isinstance(results, list):
                results = []

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"BabelNet synset ID search error for '{term}': {e}")
            return []

    # ── Synset details (synonyms) ──

    def get_synset(self, synset_id: str, language: str = "EN") -> Optional[Dict]:
        """
        Get full synset details including all senses (synonyms).

        Returns dict with: id, senses (list), glosses (list).
        """
        cache_key = f"synset:{synset_id}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "id": synset_id,
                "targetLang": language,
                "key": self.api_key
            }

            response = self._session.get(
                f"{self.BASE_URL}/getSynset",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            self._set_cached(cache_key, data)
            return data

        except requests.exceptions.RequestException as e:
            print(f"BabelNet synset details error for '{synset_id}': {e}")
            return None

    # ── Direct senses lookup ──

    def get_senses(self, term: str, language: str = "EN") -> List[Dict]:
        """
        Get all senses for a term using the getSenses endpoint.

        This returns senses across ALL synsets the term belongs to,
        which is more comprehensive than getSynsetIds + getSynset.
        Each sense includes its synsetID, so we can group by synset.
        """
        cache_key = f"senses:{term}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "lemma": term,
                "searchLang": language,
                "key": self.api_key
            }

            response = self._session.get(
                f"{self.BASE_URL}/getSenses",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                data = []

            self._set_cached(cache_key, data)
            return data

        except requests.exceptions.RequestException as e:
            print(f"BabelNet getSenses error for '{term}': {e}")
            return []

    # ── Synonym extraction ──

    def get_synonyms(self, term: str, language: str = "EN") -> List[str]:
        """
        Get all synonyms for a term from BabelNet.

        Uses getSenses to discover which synsets contain this term,
        then fetches those synsets to collect all co-occurring lemmas.
        Returns deduplicated list of synonym strings.
        """
        cache_key = f"synonyms:{term}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Use getSenses to find all synsets this term belongs to
        senses = self.get_senses(term, language)
        if not senses:
            return []

        # Collect unique synset IDs from senses
        synset_ids = []
        seen_ids = set()
        for sense in senses:
            props = sense.get("properties", sense)
            sid = props.get("synsetID", {}).get("id", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                synset_ids.append(sid)

        all_synonyms = set()

        # Check top 3 synsets to balance coverage vs API calls
        for sid in synset_ids[:3]:
            synset = self.get_synset(sid, language)
            if not synset:
                continue

            for sense in synset.get("senses", []):
                props = sense.get("properties", sense)
                sense_lang = props.get("language", "")
                if sense_lang == language:
                    lemma = props.get("simpleLemma") or props.get("fullLemma", "")
                    if lemma:
                        clean = lemma.replace("_", " ").lower()
                        all_synonyms.add(clean)

        synonym_list = sorted(all_synonyms)
        self._set_cached(cache_key, synonym_list)
        return synonym_list

    # ── Hypernyms (parent concepts) ──

    def get_hypernyms(self, term: str, language: str = "EN") -> List[str]:
        """
        Get hypernyms (parent concepts) for a term.

        Finds the top synset, then queries outgoing edges for HYPERNYM relations.
        """
        cache_key = f"hypernyms:{term}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        synset_ids = self.get_synset_ids(term, language)
        if not synset_ids:
            return []

        top_id = synset_ids[0].get("id")
        if not top_id:
            return []

        hypernyms = self._get_hypernyms_for_synset(top_id, language)
        self._set_cached(cache_key, hypernyms)
        return hypernyms

    def _get_hypernyms_for_synset(self, synset_id: str, language: str = "EN") -> List[str]:
        """Get hypernym labels for a specific synset ID."""
        try:
            params = {
                "id": synset_id,
                "key": self.api_key
            }

            response = self._session.get(
                f"{self.BASE_URL}/getOutgoingEdges",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            edges = response.json()
            if not isinstance(edges, list):
                return []

            hypernym_ids = []
            for edge in edges:
                pointer = edge.get("pointer", {})
                relation_group = pointer.get("relationGroup", "")
                if relation_group == "HYPERNYM":
                    target_id = edge.get("target")
                    if target_id:
                        hypernym_ids.append(target_id)

            # Resolve hypernym IDs to labels
            labels = []
            for hid in hypernym_ids[:5]:  # Limit to 5 to conserve API calls
                synset = self.get_synset(hid)
                if synset:
                    for sense in synset.get("senses", []):
                        props = sense.get("properties", sense)
                        if props.get("language") == language:
                            lemma = props.get("simpleLemma") or props.get("fullLemma", "")
                            if lemma:
                                labels.append(lemma.replace("_", " ").lower())
                                break

            return labels

        except requests.exceptions.RequestException as e:
            print(f"BabelNet hypernym lookup error for '{synset_id}': {e}")
            return []

    # ── High-level: hierarchy (ConceptNet-compatible interface) ──

    def get_hierarchy(self, term: str, language: str = "EN") -> Optional[Dict]:
        """
        Get hierarchy information for a term.

        Returns dict with parents, children (empty), related (synonyms).
        Compatible with the interface the resolver expects.
        """
        synonyms = self.get_synonyms(term, language)
        if not synonyms:
            return None

        parents = self.get_hypernyms(term, language)

        # Remove the original term from synonyms list
        related = [s for s in synonyms if s != term.lower()]

        return {
            "term": term,
            "parents": parents,
            "children": [],  # Not fetching hyponyms to conserve API calls
            "related": related,
        }

    # ── Embedding-based disambiguation ──

    def _get_embedding_model(self):
        """Get shared embedding model for disambiguation scoring."""
        from embedding.model_provider import get_embedding_model
        return get_embedding_model()

    def _score_glosses(self, glosses: List[str], context: str) -> float:
        """
        Score a list of glosses against context using embedding cosine similarity.

        Args:
            glosses: List of gloss/definition strings from a synset
            context: The attribute_key or context string (e.g., "condition")

        Returns:
            Best cosine similarity score (0.0 to 1.0)
        """
        if not glosses or not context:
            return 0.0

        try:
            model = self._get_embedding_model()
            context_emb = model.encode(context)

            best_score = 0.0
            for gloss in glosses:
                if not gloss:
                    continue
                gloss_emb = model.encode(gloss)
                sim = float(
                    np.dot(context_emb, gloss_emb)
                    / (np.linalg.norm(context_emb) * np.linalg.norm(gloss_emb))
                )
                if sim > best_score:
                    best_score = sim
            return best_score
        except Exception as e:
            print(f"BabelNet gloss scoring error: {e}")
            return 0.0

    def get_disambiguated_synset(
        self, term: str, context: Optional[str] = None, language: str = "EN"
    ) -> Optional[str]:
        """
        Get the best synset ID for a term, disambiguated by context.

        Fetches multiple synsets, scores each by comparing its glosses
        to the context using embedding similarity. Returns the synset ID
        with the highest score.

        Args:
            term: The word/phrase to look up
            context: Attribute key for disambiguation (e.g., "condition", "color")
            language: Language code

        Returns:
            Best synset ID string, or None if no synsets found
        """
        senses = self.get_senses(term, language)
        if not senses:
            return None

        # Collect unique synset IDs
        synset_ids = []
        seen_ids = set()
        for sense in senses:
            props = sense.get("properties", sense)
            sid = props.get("synsetID", {}).get("id", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                synset_ids.append(sid)

        if not synset_ids:
            return None

        # If no context, return first synset (original behavior)
        if not context:
            return synset_ids[0]

        # Score each synset's glosses against context
        best_id = synset_ids[0]
        best_score = -1.0

        for sid in synset_ids[:5]:  # Check top 5 synsets to balance API calls vs accuracy
            synset = self.get_synset(sid, language)
            if not synset:
                continue

            # Extract English glosses
            glosses = []
            for gloss_entry in synset.get("glosses", []):
                if gloss_entry.get("language") == language:
                    gloss_text = gloss_entry.get("gloss", "")
                    if gloss_text:
                        glosses.append(gloss_text)

            score = self._score_glosses(glosses, context)
            if score > best_score:
                best_score = score
                best_id = sid

        return best_id

    def get_canonical(
        self, term: str, context: Optional[str] = None, language: str = "EN"
    ) -> Optional[Dict]:
        """
        Get canonical form for a term with disambiguation.

        Returns dict with:
        - canonical_label: The key sense label (canonical form)
        - canonical_id: BabelNet synset ID
        - synonyms: All synonyms from the disambiguated synset
        - linked_wikidata: Wikidata Q-ID if available (via WIKIDATA source senses)
        - parents: Hypernym labels from the disambiguated synset

        Args:
            term: The word/phrase to canonicalize
            context: Attribute key for disambiguation (e.g., "condition")
            language: Language code

        Returns:
            Dict with canonical info, or None if not found
        """
        cache_key = f"canonical:{term}:{context}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Step 1: Get disambiguated synset
        synset_id = self.get_disambiguated_synset(term, context, language)
        if not synset_id:
            return None

        # Step 2: Fetch full synset details
        synset = self.get_synset(synset_id, language)
        if not synset:
            return None

        # Step 3: Extract canonical label, synonyms, and Wikidata link
        canonical_label = None
        synonyms = []
        linked_wikidata = None

        for sense in synset.get("senses", []):
            props = sense.get("properties", sense)
            sense_lang = props.get("language", "")

            if sense_lang == language:
                lemma = props.get("simpleLemma") or props.get("fullLemma", "")
                if lemma:
                    clean = lemma.replace("_", " ").lower()
                    synonyms.append(clean)

                    # Key sense = canonical label
                    if props.get("keySense", False) and not canonical_label:
                        canonical_label = clean

            # Check for Wikidata link
            source = props.get("source", "")
            if source == "WIKIDATA" and not linked_wikidata:
                sense_key = props.get("senseKey", "")
                if sense_key:
                    linked_wikidata = sense_key

        # Fallback: use first synonym as canonical label
        if not canonical_label and synonyms:
            canonical_label = synonyms[0]

        if not canonical_label:
            return None

        # Step 4: Get hypernyms from the disambiguated synset
        parents = self._get_hypernyms_for_synset(synset_id, language)

        # Remove canonical label from synonyms list
        synonyms = [s for s in synonyms if s != canonical_label]

        result = {
            "canonical_id": synset_id,
            "canonical_label": canonical_label,
            "synonyms": synonyms,
            "linked_wikidata": linked_wikidata,
            "parents": parents
        }

        self._set_cached(cache_key, result)
        return result

    # ── Path to root ──

    def find_path_to_root(
        self, term: str, max_depth: int = 3, language: str = "EN"
    ) -> List[List[str]]:
        """
        Find path from term to root concept via hypernym chains.

        Limited depth to conserve API calls (each level = 1+ API calls).
        """
        synset_ids = self.get_synset_ids(term, language)
        if not synset_ids:
            return []

        top_id = synset_ids[0].get("id")
        if not top_id:
            return []

        paths = []
        visited = set()

        def traverse(current_id: str, current_label: str, path: List[str], depth: int):
            if depth >= max_depth or current_id in visited:
                paths.append(path)
                return

            visited.add(current_id)

            try:
                params = {
                    "id": current_id,
                    "key": self.api_key
                }
                response = self._session.get(
                    f"{self.BASE_URL}/getOutgoingEdges",
                    params=params,
                    timeout=10
                )
                response.raise_for_status()
                edges = response.json()

                hypernym_ids = []
                for edge in edges if isinstance(edges, list) else []:
                    pointer = edge.get("pointer", {})
                    if pointer.get("relationGroup") == "HYPERNYM":
                        target = edge.get("target")
                        if target:
                            hypernym_ids.append(target)

                if not hypernym_ids:
                    paths.append(path)
                    return

                for hid in hypernym_ids[:2]:  # Limit branching
                    synset = self.get_synset(hid)
                    if synset:
                        label = ""
                        for sense in synset.get("senses", []):
                            props = sense.get("properties", sense)
                            if props.get("language") == language:
                                label = (props.get("simpleLemma") or
                                         props.get("fullLemma", "")).replace("_", " ").lower()
                                break
                        if label:
                            traverse(hid, label, path + [label], depth + 1)

            except Exception:
                paths.append(path)

        traverse(top_id, term.lower(), [term.lower()], 0)
        return paths


# Global singleton instance
_babelnet_client: Optional[BabelNetClient] = None


def get_babelnet_client() -> BabelNetClient:
    """Get singleton BabelNet client instance."""
    global _babelnet_client

    if _babelnet_client is None:
        _babelnet_client = BabelNetClient()

    return _babelnet_client
