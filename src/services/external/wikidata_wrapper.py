"""
Wikidata API wrapper for canonical item types and hierarchical relationships.

Wikidata is a structured knowledge base that provides:
- Canonical labels for entities (laptop → "laptop computer")
- Hierarchical relationships (instance of, subclass of)
- Multilingual support
"""

import requests
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote


class WikidataClient:
    """
    Client for querying Wikidata via SPARQL and REST API.

    Wikidata provides:
    - Canonical labels for items
    - "Instance of" (P31) relationships
    - "Subclass of" (P279) relationships
    - Hierarchical category trees
    """

    def __init__(
        self,
        sparql_endpoint: str = "https://query.wikidata.org/sparql",
        api_endpoint: str = "https://www.wikidata.org/w/api.php"
    ):
        """
        Initialize Wikidata client.

        Args:
            sparql_endpoint: Wikidata SPARQL query service URL
            api_endpoint: Wikidata REST API URL
        """
        self.sparql_endpoint = sparql_endpoint
        self.api_endpoint = api_endpoint
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Vriddhi-MatchingEngine/1.0"
        })

    def search_entity(self, term: str, language: str = "en", limit: int = 5) -> List[Dict]:
        """
        Search for Wikidata entities by term.

        Args:
            term: Search term (e.g., "laptop", "dog")
            language: Language code
            limit: Maximum results

        Returns:
            List of dicts with entity information
        """
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
                    "url": item.get("concepturi", "")
                })

            return results

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Wikidata search error for '{term}': {e}")
            return []

    def get_canonical_label(self, term: str, language: str = "en") -> Optional[str]:
        """
        Get canonical label for a term from Wikidata.

        Args:
            term: Term to look up
            language: Language code

        Returns:
            Canonical label or None
        """
        results = self.search_entity(term, language, limit=1)

        if results:
            return results[0]["label"]

        return None

    def get_superclasses(self, entity_id: str, language: str = "en") -> List[Tuple[str, str]]:
        """
        Get superclasses (parent classes) for an entity using SPARQL.

        Uses "subclass of" (P279) property.

        Args:
            entity_id: Wikidata entity ID (e.g., "Q68")
            language: Language code

        Returns:
            List of (entity_id, label) tuples
        """
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

                # Extract entity ID from URI
                if "/entity/" in superclass_uri:
                    entity_id = superclass_uri.split("/entity/")[-1]
                    results.append((entity_id, superclass_label))

            return results

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Wikidata SPARQL error for entity {entity_id}: {e}")
            return []

    def get_hierarchy_path(
        self, term: str, max_depth: int = 5, language: str = "en"
    ) -> List[List[Dict]]:
        """
        Get hierarchical path(s) from term to root concepts.

        Args:
            term: Term to look up
            max_depth: Maximum depth to traverse
            language: Language code

        Returns:
            List of paths, each path is a list of dicts with id and label
        """
        # First, search for the entity
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
                # Reached a root
                paths.append(current_path)
            else:
                for super_id, super_label in superclasses:
                    traverse(super_id, super_label, current_path, depth + 1)

        traverse(entity_id, entity_label, [], 0)
        return paths

    def get_related_concepts(self, term: str, language: str = "en") -> Dict:
        """
        Get comprehensive hierarchy information for a term.

        Args:
            term: Term to look up
            language: Language code

        Returns:
            Dict with canonical label and hierarchy paths
        """
        canonical = self.get_canonical_label(term, language)
        paths = self.get_hierarchy_path(term, max_depth=5, language=language)

        return {
            "term": term,
            "canonical_label": canonical,
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
