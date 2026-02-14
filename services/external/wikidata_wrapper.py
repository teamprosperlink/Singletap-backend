"""
Wikidata API wrapper for canonical item types and hierarchical relationships.

Wikidata is a structured knowledge base that provides:
- Canonical labels for entities (laptop -> "laptop computer")
- Hierarchical relationships (instance of, subclass of)
- Aliases / alternative labels (synonym data for matching)
- Multilingual support
"""

import time
import requests
import numpy as np
from typing import Dict, List, Optional, Tuple
from threading import Lock
from urllib.parse import quote


class WikidataClient:
    """
    Client for querying Wikidata via SPARQL and REST API.

    Wikidata provides:
    - Canonical labels for items
    - "Instance of" (P31) relationships
    - "Subclass of" (P279) relationships
    - Hierarchical category trees
    - Aliases (alternative labels) for synonym resolution
    """

    DEFAULT_CACHE_TTL = 3600  # 1 hour

    def __init__(
        self,
        sparql_endpoint: str = "https://query.wikidata.org/sparql",
        api_endpoint: str = "https://www.wikidata.org/w/api.php",
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL
    ):
        self.sparql_endpoint = sparql_endpoint
        self.api_endpoint = api_endpoint
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = Lock()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SingletapMatchingEngine/1.0"
        })

    # ── Cache helpers (follows currency_service.py pattern) ──

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

    # ── Entity search ──

    def search_entity(self, term: str, language: str = "en", limit: int = 5) -> List[Dict]:
        """
        Search for Wikidata entities by term.

        Returns list of dicts with: id, label, description, url, aliases, match_type
        """
        cache_key = f"search:{term}:{language}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "action": "wbsearchentities",
                "format": "json",
                "language": language,
                "type": "item",
                "limit": limit,
                "search": term
            }

            response = self.session.get(self.api_endpoint, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get("search", []):
                results.append({
                    "id": item.get("id"),
                    "label": item.get("label"),
                    "description": item.get("description", ""),
                    "url": item.get("concepturi", ""),
                    "aliases": item.get("aliases", []),
                    "match_type": item.get("match", {}).get("type", "")
                })

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Wikidata search error for '{term}': {e}")
            return []

    # ── Entity details (wbgetentities) ──

    def get_entity_details(self, entity_id: str, language: str = "en") -> Optional[Dict]:
        """
        Get full entity details including aliases using wbgetentities API.

        Returns: {id, label, aliases: List[str], description}
        """
        cache_key = f"entity:{entity_id}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            params = {
                "action": "wbgetentities",
                "format": "json",
                "ids": entity_id,
                "props": "labels|aliases|descriptions",
                "languages": language
            }

            response = self.session.get(self.api_endpoint, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            entity = data.get("entities", {}).get(entity_id)
            if not entity:
                return None

            label = entity.get("labels", {}).get(language, {}).get("value", "")
            description = entity.get("descriptions", {}).get(language, {}).get("value", "")

            aliases = []
            for alias_entry in entity.get("aliases", {}).get(language, []):
                alias_val = alias_entry.get("value", "")
                if alias_val:
                    aliases.append(alias_val)

            result = {
                "id": entity_id,
                "label": label,
                "aliases": aliases,
                "description": description
            }

            self._set_cached(cache_key, result)
            return result

        except requests.exceptions.RequestException as e:
            print(f"Wikidata entity details error for '{entity_id}': {e}")
            return None

    # ── Aliases ──

    def get_aliases(self, term: str, language: str = "en", limit: int = 3) -> List[str]:
        """
        Get all aliases for a term by searching Wikidata and collecting aliases
        from the top matching entities.

        Returns deduplicated list of alias strings (includes the canonical labels).
        """
        cache_key = f"aliases:{term}:{language}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        search_results = self.search_entity(term, language, limit=limit)
        if not search_results:
            return []

        all_aliases = set()
        for result in search_results:
            entity_id = result.get("id")
            if not entity_id:
                continue

            details = self.get_entity_details(entity_id, language)
            if details:
                if details.get("label"):
                    all_aliases.add(details["label"].lower())
                for alias in details.get("aliases", []):
                    all_aliases.add(alias.lower())

        alias_list = sorted(all_aliases)
        self._set_cached(cache_key, alias_list)
        return alias_list

    # ── Canonical label ──

    def get_canonical_label(self, term: str, language: str = "en") -> Optional[str]:
        """Get canonical label for a term from Wikidata."""
        results = self.search_entity(term, language, limit=1)

        if results:
            return results[0]["label"]

        return None

    # ── Embedding-based disambiguation ──

    def _get_embedding_model(self):
        """Get shared embedding model for disambiguation scoring."""
        from embedding.model_provider import get_embedding_model
        return get_embedding_model()

    def _score_description(self, description: str, context: str) -> float:
        """
        Score an entity description against context using embedding cosine similarity.

        Args:
            description: Entity description string from Wikidata
            context: The attribute_key or context string (e.g., "condition")

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        if not description or not context:
            return 0.0

        try:
            model = self._get_embedding_model()
            context_emb = model.encode(context)
            desc_emb = model.encode(description)
            sim = float(
                np.dot(context_emb, desc_emb)
                / (np.linalg.norm(context_emb) * np.linalg.norm(desc_emb))
            )
            return max(sim, 0.0)
        except Exception as e:
            print(f"Wikidata description scoring error: {e}")
            return 0.0

    def search_disambiguated_entity(
        self, term: str, context: Optional[str] = None, language: str = "en"
    ) -> Optional[Dict]:
        """
        Search for the best Wikidata entity, disambiguated by context.

        Fetches multiple candidates, scores each by comparing its description
        to the context using embedding similarity. Returns the entity dict
        with the highest score.

        Args:
            term: The word/phrase to look up
            context: Attribute key for disambiguation (e.g., "condition", "color")
            language: Language code

        Returns:
            Best entity dict {id, label, description, aliases}, or None
        """
        # Search with more candidates for disambiguation
        search_results = self.search_entity(term, language, limit=10)
        if not search_results:
            return None

        # If no context, return first result (original behavior)
        if not context:
            return search_results[0]

        # Score each result: description similarity + label/alias match quality
        best_result = search_results[0]
        best_score = -1.0
        term_lower = term.lower().strip()

        for i, result in enumerate(search_results):
            description = result.get("description", "")
            label = result.get("label", "").lower().strip()
            aliases = [a.lower().strip() for a in result.get("aliases", [])]

            # Base score: description vs context embedding similarity
            desc_score = self._score_description(description, context)

            # Label/alias match scoring:
            # Check if search term matches label OR any alias
            label_bonus = 0.0
            if label == term_lower:
                label_bonus = 0.5
            elif term_lower in aliases:
                # Alias match: term is a known alias of this entity
                # Give a bonus, but weight it by description relevance too
                label_bonus = 0.4
            elif term_lower in label:
                extra_words = len(label.split()) - len(term_lower.split())
                label_bonus = max(0.1 - extra_words * 0.05, 0.0)
            elif label in term_lower:
                label_bonus = 0.1

            # Wikidata relevance bonus: first result gets a small boost
            rank_bonus = 0.1 if i == 0 else 0.0

            score = desc_score + label_bonus + rank_bonus

            if score > best_score:
                best_score = score
                best_result = result

        return best_result

    def get_canonical(
        self, term: str, context: Optional[str] = None, language: str = "en"
    ) -> Optional[Dict]:
        """
        Get canonical form for a term with disambiguation.

        Returns dict with:
        - entity_id: Wikidata Q-ID
        - canonical_label: The canonical English label
        - aliases: All alternative labels
        - linked_babelnet: BabelNet synset ID if available (via P2581)

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

        # Step 1: Get disambiguated entity
        entity = self.search_disambiguated_entity(term, context, language)
        if not entity:
            return None

        entity_id = entity.get("id")
        if not entity_id:
            return None

        # Step 2: Get full entity details (label + aliases)
        details = self.get_entity_details(entity_id, language)
        if not details:
            return None

        canonical_label = details.get("label", "")
        if not canonical_label:
            return None

        aliases = details.get("aliases", [])

        # Step 3: Get BabelNet link via P2581 property
        linked_babelnet = self._get_babelnet_link(entity_id)

        result = {
            "entity_id": entity_id,
            "canonical_label": canonical_label.lower(),
            "aliases": [a.lower() for a in aliases],
            "linked_babelnet": linked_babelnet
        }

        self._set_cached(cache_key, result)
        return result

    def _get_babelnet_link(self, entity_id: str) -> Optional[str]:
        """
        Get BabelNet synset ID linked to a Wikidata entity via P2581 property.

        Uses SPARQL to check for the P2581 (BabelNet ID) claim.
        """
        cache_key = f"babelnet_link:{entity_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = f"""
        SELECT ?babelnetId WHERE {{
          wd:{entity_id} wdt:P2581 ?babelnetId.
        }}
        LIMIT 1
        """

        try:
            params = {
                "query": query,
                "format": "json"
            }

            response = self.session.get(self.sparql_endpoint, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])

            if bindings:
                babelnet_id = bindings[0].get("babelnetId", {}).get("value", "")
                if babelnet_id:
                    self._set_cached(cache_key, babelnet_id)
                    return babelnet_id

            self._set_cached(cache_key, None)
            return None

        except requests.exceptions.RequestException as e:
            print(f"Wikidata BabelNet link lookup error for '{entity_id}': {e}")
            return None

    # ── Hierarchy (SPARQL) ──

    def get_superclasses(self, entity_id: str, language: str = "en") -> List[Tuple[str, str]]:
        """Get superclasses (parent classes) for an entity using SPARQL."""
        cache_key = f"superclasses:{entity_id}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = f"""
        SELECT ?superclass ?superclassLabel WHERE {{
          wd:{entity_id} wdt:P279 ?superclass.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{language}". }}
        }}
        LIMIT 10
        """

        try:
            params = {
                "query": query,
                "format": "json"
            }

            response = self.session.get(self.sparql_endpoint, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            for binding in data.get("results", {}).get("bindings", []):
                superclass_uri = binding.get("superclass", {}).get("value", "")
                superclass_label = binding.get("superclassLabel", {}).get("value", "")

                if "/entity/" in superclass_uri:
                    eid = superclass_uri.split("/entity/")[-1]
                    results.append((eid, superclass_label))

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Wikidata SPARQL error for entity {entity_id}: {e}")
            return []

    def get_hierarchy_path(
        self, term: str, max_depth: int = 5, language: str = "en"
    ) -> List[List[Dict]]:
        """Get hierarchical path(s) from term to root concepts."""
        results = self.search_entity(term, language, limit=1)
        if not results:
            return []

        entity_id = results[0]["id"]
        entity_label = results[0]["label"]

        paths = []
        visited = set()

        def traverse(current_id: str, current_label: str, current_path: List[Dict], depth: int):
            if depth > max_depth or current_id in visited:
                return

            visited.add(current_id)
            current_path = current_path + [{"id": current_id, "label": current_label}]

            superclasses = self.get_superclasses(current_id, language)

            if not superclasses:
                paths.append(current_path)
            else:
                for super_id, super_label in superclasses:
                    traverse(super_id, super_label, current_path, depth + 1)

        traverse(entity_id, entity_label, [], 0)
        return paths

    # ── Hierarchy checking (is A a type of B?) ──

    def is_subclass_of(self, child_term: str, parent_term: str, max_depth: int = 3, language: str = "en") -> bool:
        """
        Check if child_term is a subclass/instance of parent_term using Wikidata hierarchy.

        Uses P31 (instance of) and P279 (subclass of) to traverse the hierarchy.

        Examples:
            is_subclass_of("dentist", "doctor") -> True (dentist is a type of doctor)
            is_subclass_of("iphone", "smartphone") -> True (iPhone is a smartphone)
            is_subclass_of("puppy", "dog") -> True (puppy is a young dog)

        Args:
            child_term: The more specific term (e.g., "dentist")
            parent_term: The broader term (e.g., "doctor")
            max_depth: Maximum hierarchy depth to search
            language: Language code

        Returns:
            True if child is a subclass/instance of parent
        """
        cache_key = f"is_subclass:{child_term}:{parent_term}:{max_depth}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Get entity IDs for both terms
        child_results = self.search_entity(child_term, language, limit=3)
        parent_results = self.search_entity(parent_term, language, limit=3)

        if not child_results or not parent_results:
            self._set_cached(cache_key, False)
            return False

        # Collect parent entity IDs and labels to match against
        parent_ids = {r["id"] for r in parent_results}
        parent_labels = {r["label"].lower() for r in parent_results if r.get("label")}

        # BFS through child's hierarchy
        visited = set()
        queue = [(r["id"], 0) for r in child_results[:2]]  # Start with top 2 matches

        while queue:
            current_id, depth = queue.pop(0)

            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)

            # Check P31 (instance of) and P279 (subclass of)
            parents = self._get_parent_classes(current_id, language)

            for parent_id, parent_label in parents:
                # Check if we found the target parent
                if parent_id in parent_ids:
                    self._set_cached(cache_key, True)
                    return True
                if parent_label.lower() in parent_labels:
                    self._set_cached(cache_key, True)
                    return True

                # Add to queue for further traversal
                if parent_id not in visited and depth + 1 <= max_depth:
                    queue.append((parent_id, depth + 1))

        self._set_cached(cache_key, False)
        return False

    def _get_parent_classes(self, entity_id: str, language: str = "en") -> List[Tuple[str, str]]:
        """
        Get both P31 (instance of) and P279 (subclass of) parents for an entity.

        Returns list of (entity_id, label) tuples.
        """
        cache_key = f"parents:{entity_id}:{language}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Query both P31 and P279
        query = f"""
        SELECT DISTINCT ?parent ?parentLabel WHERE {{
          {{
            wd:{entity_id} wdt:P31 ?parent.
          }} UNION {{
            wd:{entity_id} wdt:P279 ?parent.
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{language},en". }}
        }}
        LIMIT 20
        """

        try:
            params = {
                "query": query,
                "format": "json"
            }

            response = self.session.get(self.sparql_endpoint, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            for binding in data.get("results", {}).get("bindings", []):
                parent_uri = binding.get("parent", {}).get("value", "")
                parent_label = binding.get("parentLabel", {}).get("value", "")

                if "/entity/" in parent_uri:
                    eid = parent_uri.split("/entity/")[-1]
                    results.append((eid, parent_label))

            self._set_cached(cache_key, results)
            return results

        except requests.exceptions.RequestException as e:
            print(f"Wikidata parent classes error for '{entity_id}': {e}")
            return []

    # ── Related concepts (enhanced with aliases) ──

    def get_related_concepts(self, term: str, language: str = "en") -> Dict:
        """Get comprehensive hierarchy information for a term, including aliases."""
        search_results = self.search_entity(term, language, limit=1)

        canonical = None
        aliases = []
        entity_id = None

        if search_results:
            canonical = search_results[0]["label"]
            entity_id = search_results[0]["id"]

            details = self.get_entity_details(entity_id, language)
            if details:
                aliases = details.get("aliases", [])

        paths = self.get_hierarchy_path(term, max_depth=5, language=language)

        return {
            "term": term,
            "canonical_label": canonical,
            "entity_id": entity_id,
            "aliases": aliases,
            "hierarchy_paths": paths
        }


# Global singleton instance
_wikidata_client: Optional[WikidataClient] = None


def get_wikidata_client() -> WikidataClient:
    """Get singleton Wikidata client instance."""
    global _wikidata_client

    if _wikidata_client is None:
        _wikidata_client = WikidataClient()

    return _wikidata_client
