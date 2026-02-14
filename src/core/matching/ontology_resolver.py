"""
ONTOLOGY RESOLVER: Multi-Source Relationship Detection

Implements hybrid ontology resolution with deterministic, domain-agnostic
relationship detection for semantic matching and exclusion checking.

Resolution order:
1. File Cache (JSON)
2. ConceptNet (free public API)
3. Wikidata (free SPARQL endpoint)
4. BabelNet (paid API, requires key)
5. LLM (fallback with gpt-4o-mini)

Key Capabilities:
- Hierarchical implication detection (chicken → non-veg)
- Antonym detection (veg vs non-veg)
- Exclusion violation checking with hierarchy awareness
- Persistent file-based caching

Author: Claude (Ontology Resolver Implementation)
Date: 2026-01-21
"""

import json
import os
import requests
from typing import Dict, Tuple, Optional, Any
from pathlib import Path


# ============================================================================
# RELATIONSHIP TYPES
# ============================================================================

class RelationType:
    """Relationship types between terms"""
    IMPLIES = "implies"           # Term1 implies term2 (chicken → non-veg)
    COMPATIBLE = "compatible"     # Terms can coexist
    INCOMPATIBLE = "incompatible" # Mutually exclusive (veg vs non-veg)
    UNRELATED = "unrelated"       # No known relationship


# ============================================================================
# ONTOLOGY RESOLVER CLASS
# ============================================================================

class OntologyResolver:
    """
    Multi-source ontology resolver for relationship detection.

    Queries multiple knowledge bases in order:
    1. File cache (instant)
    2. ConceptNet (free, no auth)
    3. Wikidata (free, no auth)
    4. BabelNet (paid, requires API key)
    5. LLM fallback (OpenAI gpt-4o-mini)

    Features:
    - Persistent file-based cache
    - Automatic cache updates
    - Source tracking for transparency
    - Statistics tracking
    """

    def __init__(self, openai_client=None, babelnet_key: Optional[str] = None, cache_file: str = "ontology_cache.json"):
        """
        Initialize ontology resolver.

        Args:
            openai_client: OpenAI client for LLM fallback
            babelnet_key: BabelNet API key (optional)
            cache_file: Path to JSON cache file
        """
        self.openai_client = openai_client
        self.babelnet_key = babelnet_key
        self.cache_file = cache_file

        # Load cache from file
        self.cache = self._load_cache()

        # Statistics tracking
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "conceptnet_hits": 0,
            "wikidata_hits": 0,
            "babelnet_hits": 0,
            "llm_hits": 0
        }

    def _load_cache(self) -> Dict:
        """Load cache from JSON file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load cache from {self.cache_file}: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save cache to JSON file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache to {self.cache_file}: {e}")

    def _make_cache_key(self, term1: str, term2: str, context: Optional[str] = None) -> str:
        """
        Create cache key for term pair.

        Format: rel:term1|term2|context
        """
        term1 = term1.lower().strip()
        term2 = term2.lower().strip()
        context_str = context.lower().strip() if context else ""
        return f"rel:{term1}|{term2}|{context_str}"

    def get_relationship(self, term1: str, term2: str, context: Optional[str] = None) -> Tuple[str, str]:
        """
        Get relationship between two terms.

        Resolution order:
        1. Check cache
        2. Query ConceptNet
        3. Query Wikidata
        4. Query BabelNet
        5. Fallback to LLM

        Args:
            term1: First term
            term2: Second term
            context: Optional context (e.g., "food", "diet")

        Returns:
            Tuple of (relationship_type, source)
            relationship_type: "implies" | "compatible" | "incompatible" | "unrelated"
            source: "cache" | "conceptnet" | "wikidata" | "babelnet" | "llm"

        Example:
            >>> get_relationship("chicken", "non-veg", "food")
            ("implies", "conceptnet")
        """
        self.stats["total_queries"] += 1

        # Normalize terms
        term1 = term1.lower().strip()
        term2 = term2.lower().strip()

        # Exact match
        if term1 == term2:
            return (RelationType.COMPATIBLE, "exact_match")

        # Check cache
        cache_key = self._make_cache_key(term1, term2, context)
        if cache_key in self.cache:
            self.stats["cache_hits"] += 1
            cached = self.cache[cache_key]
            return (cached["relationship"], "cache")

        # Try ConceptNet
        rel, source = self._query_conceptnet(term1, term2)
        if rel != RelationType.UNRELATED:
            self._update_cache(cache_key, rel, source)
            self.stats["conceptnet_hits"] += 1
            return (rel, source)

        # Try Wikidata
        rel, source = self._query_wikidata(term1, term2)
        if rel != RelationType.UNRELATED:
            self._update_cache(cache_key, rel, source)
            self.stats["wikidata_hits"] += 1
            return (rel, source)

        # Try BabelNet (if API key available)
        if self.babelnet_key:
            rel, source = self._query_babelnet(term1, term2)
            if rel != RelationType.UNRELATED:
                self._update_cache(cache_key, rel, source)
                self.stats["babelnet_hits"] += 1
                return (rel, source)

        # Fallback to LLM
        if self.openai_client:
            rel, source = self._query_llm(term1, term2, context)
            self._update_cache(cache_key, rel, source)
            self.stats["llm_hits"] += 1
            return (rel, source)

        # No relationship found
        self._update_cache(cache_key, RelationType.UNRELATED, "unknown")
        return (RelationType.UNRELATED, "unknown")

    def _update_cache(self, cache_key: str, relationship: str, source: str):
        """Update cache with new relationship"""
        self.cache[cache_key] = {
            "relationship": relationship,
            "source": source
        }
        self._save_cache()

    def _query_conceptnet(self, term1: str, term2: str) -> Tuple[str, str]:
        """
        Query ConceptNet API for relationship.

        ConceptNet relationships:
        - /r/IsA → implies (chicken IsA meat)
        - /r/Antonym → incompatible (veg Antonym non-veg)
        - /r/RelatedTo → compatible
        - /r/PartOf → implies

        Returns:
            (relationship_type, "conceptnet")
        """
        try:
            # Query edges from term1 to term2
            url = f"http://api.conceptnet.io/query"
            params = {
                "start": f"/c/en/{term1.replace(' ', '_')}",
                "end": f"/c/en/{term2.replace(' ', '_')}",
                "limit": 10
            }
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                edges = data.get("edges", [])

                for edge in edges:
                    rel = edge.get("rel", {}).get("@id", "")

                    # Map ConceptNet relations to our types
                    if "/r/IsA" in rel or "/r/PartOf" in rel:
                        return (RelationType.IMPLIES, "conceptnet")
                    elif "/r/Antonym" in rel:
                        return (RelationType.INCOMPATIBLE, "conceptnet")
                    elif "/r/RelatedTo" in rel or "/r/SimilarTo" in rel:
                        return (RelationType.COMPATIBLE, "conceptnet")

            # Also try reverse direction (term2 → term1) to check for inverse relationships
            params_reverse = {
                "start": f"/c/en/{term2.replace(' ', '_')}",
                "end": f"/c/en/{term1.replace(' ', '_')}",
                "limit": 10
            }
            response_reverse = requests.get(url, params=params_reverse, timeout=5)

            if response_reverse.status_code == 200:
                data = response_reverse.json()
                edges = data.get("edges", [])

                for edge in edges:
                    rel = edge.get("rel", {}).get("@id", "")

                    # If term2 IsA term1, then term1 does NOT imply term2
                    # But they are related (compatible)
                    if "/r/IsA" in rel or "/r/PartOf" in rel:
                        return (RelationType.COMPATIBLE, "conceptnet")
                    elif "/r/Antonym" in rel:
                        return (RelationType.INCOMPATIBLE, "conceptnet")

        except Exception as e:
            print(f"ConceptNet query failed: {e}")

        return (RelationType.UNRELATED, "conceptnet")

    def _query_wikidata(self, term1: str, term2: str) -> Tuple[str, str]:
        """
        Query Wikidata SPARQL endpoint for relationship.

        Wikidata properties:
        - P279 (subclass of) → implies
        - P31 (instance of) → implies
        - P461 (opposite of) → incompatible

        Returns:
            (relationship_type, "wikidata")
        """
        try:
            from SPARQLWrapper import SPARQLWrapper, JSON

            sparql = SPARQLWrapper("https://query.wikidata.org/sparql")

            # SPARQL query to find relationships
            query = f"""
            SELECT ?rel WHERE {{
              ?term1 rdfs:label "{term1}"@en .
              ?term2 rdfs:label "{term2}"@en .
              ?term1 ?rel ?term2 .
            }}
            LIMIT 10
            """

            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)

            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])

            for binding in bindings:
                rel_uri = binding.get("rel", {}).get("value", "")

                # Map Wikidata properties to our types
                if "P279" in rel_uri or "P31" in rel_uri:  # subclass of, instance of
                    return (RelationType.IMPLIES, "wikidata")
                elif "P461" in rel_uri:  # opposite of
                    return (RelationType.INCOMPATIBLE, "wikidata")

        except ImportError:
            # SPARQLWrapper not installed, skip Wikidata
            pass
        except Exception as e:
            print(f"Wikidata query failed: {e}")

        return (RelationType.UNRELATED, "wikidata")

    def _query_babelnet(self, term1: str, term2: str) -> Tuple[str, str]:
        """
        Query BabelNet API for relationship.

        BabelNet relationships:
        - Hypernym → implies (chicken hypernym-of meat)
        - Antonym → incompatible

        Returns:
            (relationship_type, "babelnet")
        """
        if not self.babelnet_key:
            return (RelationType.UNRELATED, "babelnet")

        try:
            # Get synset IDs for both terms
            synset1_id = self._get_babelnet_synset(term1)
            synset2_id = self._get_babelnet_synset(term2)

            if not synset1_id or not synset2_id:
                return (RelationType.UNRELATED, "babelnet")

            # Query edges between synsets
            url = f"https://babelnet.io/v9/getOutgoingEdges"
            params = {
                "id": synset1_id,
                "key": self.babelnet_key
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                edges = response.json()

                for edge in edges:
                    target = edge.get("target", "")
                    pointer = edge.get("pointer", {}).get("name", "")

                    if target == synset2_id:
                        # Map BabelNet pointers to our types
                        if "HYPERNYM" in pointer.upper():
                            return (RelationType.IMPLIES, "babelnet")
                        elif "ANTONYM" in pointer.upper():
                            return (RelationType.INCOMPATIBLE, "babelnet")
                        elif "SIMILAR" in pointer.upper():
                            return (RelationType.COMPATIBLE, "babelnet")

        except Exception as e:
            print(f"BabelNet query failed: {e}")

        return (RelationType.UNRELATED, "babelnet")

    def _get_babelnet_synset(self, term: str) -> Optional[str]:
        """Get BabelNet synset ID for a term"""
        try:
            url = "https://babelnet.io/v9/getSynsetIds"
            params = {
                "lemma": term,
                "searchLang": "EN",
                "key": self.babelnet_key
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0].get("id")

        except Exception as e:
            print(f"BabelNet synset lookup failed: {e}")

        return None

    def _query_llm(self, term1: str, term2: str, context: Optional[str] = None) -> Tuple[str, str]:
        """
        Query LLM (gpt-4o-mini) for relationship as fallback.

        Args:
            term1: First term
            term2: Second term
            context: Optional context for disambiguation

        Returns:
            (relationship_type, "llm")
        """
        if not self.openai_client:
            return (RelationType.UNRELATED, "llm")

        try:
            context_str = f" in the context of {context}" if context else ""
            prompt = f"""What is the semantic relationship between "{term1}" and "{term2}"{context_str}?

Respond with EXACTLY ONE of these relationships:
- "implies" if {term1} implies {term2} (e.g., "chicken" implies "non-veg", "excellent" implies "good")
- "incompatible" if they are mutually exclusive or antonyms (e.g., "veg" and "non-veg")
- "compatible" if they can coexist but no implication
- "unrelated" if there's no semantic relationship

Only respond with the single word: implies, incompatible, compatible, or unrelated."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a semantic relationship classifier. Respond with only one word."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.0
            )

            result = response.choices[0].message.content.strip().lower()

            # Validate result
            if result in [RelationType.IMPLIES, RelationType.INCOMPATIBLE, RelationType.COMPATIBLE, RelationType.UNRELATED]:
                return (result, "llm")

        except Exception as e:
            print(f"LLM query failed: {e}")

        return (RelationType.UNRELATED, "llm")

    def check_value_satisfies_requirement(self, candidate_val, required_val, attr_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if candidate value satisfies requirement using ontology.

        Args:
            candidate_val: Value from candidate (str or dict with concept_id)
            required_val: Required value (str or dict with concept_id)
            attr_type: Optional attribute type for context

        Returns:
            (satisfied: bool, reason: str)

        Example:
            >>> check_value_satisfies_requirement("chicken", "non-veg", "diet")
            (True, "chicken implies non-veg (via conceptnet)")
        """
        # Extract string from ontology dicts if needed
        if isinstance(candidate_val, dict):
            candidate_val = candidate_val.get("concept_id", str(candidate_val))
        if isinstance(required_val, dict):
            required_val = required_val.get("concept_id", str(required_val))
        # Ensure strings
        candidate_val = str(candidate_val)
        required_val = str(required_val)

        # Exact match
        if candidate_val.lower() == required_val.lower():
            return (True, "exact match")

        # Check relationship
        rel, source = self.get_relationship(candidate_val, required_val, attr_type)

        if rel == RelationType.IMPLIES:
            return (True, f"{candidate_val} implies {required_val} (via {source})")
        elif rel == RelationType.COMPATIBLE:
            return (True, f"{candidate_val} compatible with {required_val} (via {source})")
        elif rel == RelationType.INCOMPATIBLE:
            return (False, f"{candidate_val} incompatible with {required_val} (via {source})")
        else:
            return (False, f"{candidate_val} unrelated to {required_val} (no ontology match)")

    def check_exclusion_violation(self, exclusion, candidate_val, attr_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if candidate value violates exclusion using ontology.

        Exclusion is violated if:
        1. Exact match (candidate_val == exclusion)
        2. Candidate implies exclusion (chicken implies non-veg, so excluding non-veg catches chicken)

        Args:
            exclusion: Excluded value (str or dict with concept_id)
            candidate_val: Candidate value to check (str or dict with concept_id)
            attr_type: Optional attribute type for context

        Returns:
            (violated: bool, reason: str)

        Example:
            >>> check_exclusion_violation("non-veg", "chicken", "diet")
            (True, "chicken implies non-veg (via conceptnet) - exclusion violated")
        """
        # Extract string from ontology dicts if needed
        if isinstance(exclusion, dict):
            exclusion = exclusion.get("concept_id", str(exclusion))
        if isinstance(candidate_val, dict):
            candidate_val = candidate_val.get("concept_id", str(candidate_val))
        # Ensure strings
        exclusion = str(exclusion)
        candidate_val = str(candidate_val)

        # Exact match
        if exclusion.lower() == candidate_val.lower():
            return (True, "exact match - exclusion violated")

        # Check if candidate implies excluded term
        # If chicken → non-veg, then excluding "non-veg" should catch "chicken"
        rel, source = self.get_relationship(candidate_val, exclusion, attr_type)

        if rel == RelationType.IMPLIES:
            return (True, f"{candidate_val} implies {exclusion} (via {source}) - exclusion violated")
        elif rel == RelationType.INCOMPATIBLE:
            # Incompatible terms don't violate exclusion
            # Excluding "veg" doesn't exclude "non-veg" (they're opposites, not hierarchical)
            return (False, f"{candidate_val} incompatible with {exclusion} (via {source}) - no violation")
        else:
            return (False, f"{candidate_val} unrelated to {exclusion} - no violation")

    def print_stats(self):
        """Print resolver statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            print("No queries processed yet.")
            return

        print("=" * 60)
        print("ONTOLOGY RESOLVER STATISTICS")
        print("=" * 60)
        print(f"Total queries:     {total}")
        print(f"Cache hits:        {self.stats['cache_hits']} ({100 * self.stats['cache_hits'] / total:.1f}%)")
        print(f"ConceptNet hits:   {self.stats['conceptnet_hits']} ({100 * self.stats['conceptnet_hits'] / total:.1f}%)")
        print(f"Wikidata hits:     {self.stats['wikidata_hits']} ({100 * self.stats['wikidata_hits'] / total:.1f}%)")
        print(f"BabelNet hits:     {self.stats['babelnet_hits']} ({100 * self.stats['babelnet_hits'] / total:.1f}%)")
        print(f"LLM fallback:      {self.stats['llm_hits']} ({100 * self.stats['llm_hits'] / total:.1f}%)")
        print("=" * 60)
