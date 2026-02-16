"""
Generic Categorical Attribute Resolver.

This resolver works for ANY categorical attribute (color, brand, condition, fuel, etc.)
without hardcoding specific logic. It uses a multi-tier API cascade to build
ontology trees dynamically.

Resolution Strategy:
1. ConceptNet: Get semantic relationships (IsA, RelatedTo)
2. Wikidata: Get canonical labels and hierarchies
3. BabelNet (optional): Fallback for unknown terms

Output Format (Ontology-Grounded):
{
    "concept_id": "navy blue",
    "concept_root": "color",
    "concept_path": ["color", "blue", "navy blue"],
    "match_scope": "exact"  # or "include_descendants"
}
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from src.services.external.conceptnet_wrapper import get_conceptnet_client
from src.services.external.wikidata_wrapper import get_wikidata_client
from src.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class OntologyNode:
    """
    Represents a concept in the ontology tree.

    Attributes:
        concept_id: Canonical concept identifier
        concept_root: Root category (e.g., "color", "food", "material")
        concept_path: Full path from root to this concept
        parents: Direct parent concepts
        children: Direct child concepts
        siblings: Related concepts at same level
        source: Where this came from (conceptnet, wikidata, etc.)
        confidence: Confidence score (0.0 to 1.0)
    """
    concept_id: str
    concept_root: str
    concept_path: List[str]
    parents: List[str]
    children: List[str]
    siblings: List[str]
    source: str
    confidence: float


class GenericCategoricalResolver:
    """
    Generic resolver for ANY categorical attribute.

    This resolver doesn't hardcode logic for specific attributes (color, food, etc.).
    Instead, it uses API-driven ontology building to work with any attribute type.

    Example usage:
        resolver = GenericCategoricalResolver()

        # Resolve a color
        result = resolver.resolve("navy blue")
        # → OntologyNode(concept_id="navy blue", concept_root="color",
        #                concept_path=["color", "blue", "navy blue"], ...)

        # Resolve a food
        result = resolver.resolve("chicken")
        # → OntologyNode(concept_id="chicken", concept_root="food",
        #                concept_path=["food", "meat", "poultry", "chicken"], ...)

        # Resolve a condition
        result = resolver.resolve("second hand")
        # → OntologyNode(concept_id="used", concept_root="condition",
        #                concept_path=["condition", "used"], ...)
    """

    def __init__(self):
        """Initialize the generic categorical resolver."""
        self.conceptnet = get_conceptnet_client()
        self.wikidata = get_wikidata_client()

    def resolve(
        self,
        value: str,
        context: Optional[str] = None,
        attribute_key: Optional[str] = None
    ) -> Optional[OntologyNode]:
        """
        Resolve a categorical value to ontology node.

        Args:
            value: Value to resolve (e.g., "navy blue", "chicken", "second hand")
            context: Optional context (e.g., item type like "car", "food")
            attribute_key: Optional attribute key hint (e.g., "color", "diet")

        Returns:
            OntologyNode with ontology information or None
        """
        # Try multi-tier resolution
        node = self._resolve_via_conceptnet(value)

        if not node:
            node = self._resolve_via_wikidata(value)

        if not node:
            # Fallback: return simple node without hierarchy
            return self._create_simple_node(value, attribute_key)

        return node

    def _resolve_via_conceptnet(self, value: str) -> Optional[OntologyNode]:
        """
        Resolve using ConceptNet API.

        Args:
            value: Term to resolve

        Returns:
            OntologyNode or None
        """
        try:
            hierarchy = self.conceptnet.get_hierarchy(value)

            if not hierarchy:
                return None

            # Get parents to find root
            parents = hierarchy.get("parents", [])
            children = hierarchy.get("children", [])
            related = hierarchy.get("related", [])

            # Try to find root by traversing parents
            paths = self.conceptnet.find_path_to_root(value, max_depth=5)

            if paths:
                # Use the shortest path as concept_path
                shortest_path = min(paths, key=len)
                concept_root = shortest_path[-1] if shortest_path else value

                return OntologyNode(
                    concept_id=value.lower(),
                    concept_root=concept_root.lower(),
                    concept_path=[p.lower() for p in reversed(shortest_path)],
                    parents=[p.lower() for p in parents],
                    children=[c.lower() for c in children],
                    siblings=[r.lower() for r in related],
                    source="conceptnet",
                    confidence=0.8
                )

            # If no path to root, still return what we have
            if parents:
                return OntologyNode(
                    concept_id=value.lower(),
                    concept_root=parents[0].lower() if parents else value.lower(),
                    concept_path=[parents[0].lower(), value.lower()] if parents else [value.lower()],
                    parents=[p.lower() for p in parents],
                    children=[c.lower() for c in children],
                    siblings=[r.lower() for r in related],
                    source="conceptnet",
                    confidence=0.7
                )

            return None

        except Exception as e:
            log.warning("ConceptNet resolution error", emoji="warning",
                        value=value, error=str(e))
            return None

    def _resolve_via_wikidata(self, value: str) -> Optional[OntologyNode]:
        """
        Resolve using Wikidata API.

        Args:
            value: Term to resolve

        Returns:
            OntologyNode or None
        """
        try:
            result = self.wikidata.get_related_concepts(value)

            canonical_label = result.get("canonical_label")
            if not canonical_label:
                return None

            paths = result.get("hierarchy_paths", [])

            if paths:
                # Use the shortest path
                shortest_path = min(paths, key=len)

                # Extract labels from path
                path_labels = [node["label"].lower() for node in shortest_path]

                # Find parents and siblings from path
                parents = []
                if len(shortest_path) > 1:
                    parents = [shortest_path[-2]["label"].lower()]

                return OntologyNode(
                    concept_id=canonical_label.lower(),
                    concept_root=path_labels[-1] if path_labels else canonical_label.lower(),
                    concept_path=list(reversed(path_labels)),
                    parents=parents,
                    children=[],  # Wikidata doesn't easily give children
                    siblings=[],  # Would need additional queries
                    source="wikidata",
                    confidence=0.9
                )

            # If canonical label but no path, still return it
            return OntologyNode(
                concept_id=canonical_label.lower(),
                concept_root=canonical_label.lower(),
                concept_path=[canonical_label.lower()],
                parents=[],
                children=[],
                siblings=[],
                source="wikidata",
                confidence=0.6
            )

        except Exception as e:
            log.warning("Wikidata resolution error", emoji="warning",
                        value=value, error=str(e))
            return None

    def _create_simple_node(
        self, value: str, attribute_key: Optional[str] = None
    ) -> OntologyNode:
        """
        Create a simple node when API resolution fails.

        Args:
            value: Value
            attribute_key: Optional attribute key as root hint

        Returns:
            OntologyNode with minimal information
        """
        concept_root = attribute_key if attribute_key else value

        return OntologyNode(
            concept_id=value.lower(),
            concept_root=concept_root.lower(),
            concept_path=[concept_root.lower(), value.lower()] if attribute_key else [value.lower()],
            parents=[],
            children=[],
            siblings=[],
            source="fallback",
            confidence=0.3
        )

    def to_schema_format(self, node: OntologyNode, match_scope: str = "exact") -> Dict:
        """
        Convert OntologyNode to schema format for storage.

        Args:
            node: OntologyNode to convert
            match_scope: "exact" or "include_descendants"

        Returns:
            Dict ready for schema storage
        """
        return {
            "concept_id": node.concept_id,
            "concept_root": node.concept_root,
            "concept_path": node.concept_path,
            "match_scope": match_scope,
            "metadata": {
                "parents": node.parents,
                "children": node.children,
                "siblings": node.siblings,
                "source": node.source,
                "confidence": node.confidence
            }
        }
