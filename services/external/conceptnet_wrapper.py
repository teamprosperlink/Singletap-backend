"""
ConceptNet API wrapper for semantic relationships and ontology resolution.

ConceptNet is a free semantic knowledge graph that provides relationships
between concepts (e.g., "blue" IsA "color", "navy blue" IsA "blue").
"""

import requests
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote


class ConceptNetClient:
    """
    Client for querying ConceptNet API.

    ConceptNet provides semantic relationships like:
    - IsA (category membership): "dog" IsA "animal"
    - PartOf (hierarchy): "wheel" PartOf "car"
    - RelatedTo (semantic similarity): "happy" RelatedTo "joyful"
    - HasProperty: "sky" HasProperty "blue"
    """

    def __init__(self, base_url: str = "http://api.conceptnet.io"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SingletapMatchingEngine/1.0"
        })

    def get_concept(self, term: str, language: str = "en") -> Optional[Dict]:
        """Get concept information from ConceptNet."""
        try:
            concept_uri = f"/c/{language}/{quote(term.lower().replace(' ', '_'))}"
            url = f"{self.base_url}{concept_uri}"

            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()
            return data

        except requests.exceptions.RequestException as e:
            print(f"ConceptNet API error for '{term}': {e}")
            return None

    def get_parents(self, term: str, language: str = "en") -> List[str]:
        """Get parent concepts (broader categories) using IsA relationships."""
        concept_data = self.get_concept(term, language)
        if not concept_data:
            return []

        parents = []
        edges = concept_data.get("edges", [])

        for edge in edges:
            if edge.get("rel", {}).get("label") == "IsA":
                start = edge.get("start", {}).get("label", "")
                end = edge.get("end", {}).get("label", "")

                if start.lower() == term.lower():
                    parents.append(end)

        return parents

    def get_children(self, term: str, language: str = "en") -> List[str]:
        """Get child concepts (narrower terms) using reverse IsA relationships."""
        concept_data = self.get_concept(term, language)
        if not concept_data:
            return []

        children = []
        edges = concept_data.get("edges", [])

        for edge in edges:
            if edge.get("rel", {}).get("label") == "IsA":
                start = edge.get("start", {}).get("label", "")
                end = edge.get("end", {}).get("label", "")

                if end.lower() == term.lower():
                    children.append(start)

        return children

    def get_related(self, term: str, language: str = "en") -> List[str]:
        """Get related concepts using RelatedTo and Synonym relationships."""
        concept_data = self.get_concept(term, language)
        if not concept_data:
            return []

        related = []
        edges = concept_data.get("edges", [])

        for edge in edges:
            rel_label = edge.get("rel", {}).get("label")

            if rel_label in ["RelatedTo", "Synonym", "SimilarTo"]:
                start = edge.get("start", {}).get("label", "")
                end = edge.get("end", {}).get("label", "")

                if start.lower() == term.lower():
                    related.append(end)
                elif end.lower() == term.lower():
                    related.append(start)

        return related

    def get_hierarchy(
        self, term: str, language: str = "en"
    ) -> Dict[str, List[str]]:
        """Get full hierarchy information for a term."""
        return {
            "term": term,
            "parents": self.get_parents(term, language),
            "children": self.get_children(term, language),
            "related": self.get_related(term, language),
        }

    def find_path_to_root(
        self, term: str, max_depth: int = 5, language: str = "en"
    ) -> List[List[str]]:
        """Find path(s) from term to root concept via IsA relationships."""
        paths = []
        visited = set()

        def traverse(current_term: str, current_path: List[str], depth: int):
            if depth > max_depth or current_term in visited:
                return

            visited.add(current_term)
            current_path = current_path + [current_term]

            parents = self.get_parents(current_term, language)

            if not parents:
                paths.append(current_path)
            else:
                for parent in parents:
                    traverse(parent, current_path, depth + 1)

        traverse(term, [], 0)
        return paths


# Global singleton instance
_conceptnet_client: Optional[ConceptNetClient] = None


def get_conceptnet_client() -> ConceptNetClient:
    """Get singleton ConceptNet client instance."""
    global _conceptnet_client

    if _conceptnet_client is None:
        _conceptnet_client = ConceptNetClient()

    return _conceptnet_client
