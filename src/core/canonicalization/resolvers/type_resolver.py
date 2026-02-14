"""
Type Resolver: Hierarchical Type Canonicalization.

Resolves item types to ontology-format structures for hierarchical matching.
Uses a static JSON hierarchy file for deterministic, fast resolution.

Resolution Logic:
- Specific type (leaf node) → match_scope="exact"
- Broad type (has children) → match_scope="include_descendants"
- Alias normalization ("mobile" → "smartphone")

Output Format (same as categorical ontology):
{
    "concept_id": "iphone 15 pro",
    "concept_root": "smartphone",
    "concept_path": ["smartphone", "apple", "iphone", "iphone 15", "iphone 15 pro"],
    "match_scope": "exact",
    "metadata": {
        "children": [],
        "aliases": [],
        "source": "type_hierarchy"
    }
}

Author: Claude (Type Resolution Engine)
Date: 2026-02-05
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TypeNode:
    """
    Represents a type in the hierarchy.

    Attributes:
        concept_id: Canonical type identifier (lowercase)
        concept_root: Root category (e.g., "smartphone", "laptop")
        concept_path: Full path from root to this type
        children: Direct child types
        aliases: Alternative names for this type
        is_leaf: Whether this is a leaf node (no children)
        source: Always "type_hierarchy"
    """
    concept_id: str
    concept_root: str
    concept_path: List[str]
    children: List[str]
    aliases: List[str]
    is_leaf: bool
    source: str = "type_hierarchy"


class TypeResolver:
    """
    Hierarchical type resolver using static JSON hierarchy.

    This resolver provides fast, deterministic type resolution without
    external API calls. The hierarchy is loaded once from JSON and
    cached in memory.

    Example usage:
        resolver = TypeResolver()

        # Resolve a specific type (leaf)
        result = resolver.resolve("iPhone 15 Pro")
        # → match_scope="exact" (no descendants)

        # Resolve a broad type (has children)
        result = resolver.resolve("iPhone")
        # → match_scope="include_descendants" (matches iPhone 15, iPhone 15 Pro, etc.)

        # Resolve with alias
        result = resolver.resolve("mobile")
        # → concept_id="smartphone", match_scope="include_descendants"
    """

    def __init__(self, hierarchy_file: Optional[str] = None):
        """
        Initialize the type resolver.

        Args:
            hierarchy_file: Path to type_hierarchy.json. If None, uses default location.
        """
        if hierarchy_file is None:
            # Default: src/data/type_hierarchy.json
            base_path = Path(__file__).parent.parent.parent.parent
            hierarchy_file = base_path / "data" / "type_hierarchy.json"

        self.hierarchy = self._load_hierarchy(str(hierarchy_file))
        self.alias_map = self._build_alias_map()

    def _load_hierarchy(self, filepath: str) -> Dict[str, Any]:
        """Load hierarchy from JSON file."""
        if not os.path.exists(filepath):
            print(f"Warning: Type hierarchy file not found: {filepath}")
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Remove metadata key if present
                data.pop("_metadata", None)
                return data
        except Exception as e:
            print(f"Warning: Failed to load type hierarchy: {e}")
            return {}

    def _build_alias_map(self) -> Dict[str, str]:
        """
        Build reverse alias map for fast lookup.

        Returns:
            Dict mapping alias → canonical type
        """
        alias_map = {}
        for type_id, type_data in self.hierarchy.items():
            aliases = type_data.get("aliases", [])
            for alias in aliases:
                alias_map[alias.lower()] = type_id.lower()
        return alias_map

    def resolve(self, type_value: str) -> Optional[TypeNode]:
        """
        Resolve a type value to TypeNode.

        Args:
            type_value: Type string (e.g., "iPhone 15 Pro", "mobile", "laptop")

        Returns:
            TypeNode with hierarchy information, or None if not found
        """
        if not type_value:
            return None

        # Normalize input
        normalized = type_value.lower().strip()

        # Check alias map first
        if normalized in self.alias_map:
            normalized = self.alias_map[normalized]

        # Check if type exists in hierarchy
        if normalized in self.hierarchy:
            return self._build_type_node(normalized)

        # Try fuzzy matching for partial matches
        matched_type = self._fuzzy_match(normalized)
        if matched_type:
            return self._build_type_node(matched_type)

        # Not found in hierarchy - return as simple leaf
        return self._create_unknown_node(type_value)

    def _build_type_node(self, type_id: str) -> TypeNode:
        """
        Build TypeNode for a known type.

        Args:
            type_id: Canonical type ID (lowercase)

        Returns:
            TypeNode with full hierarchy information
        """
        type_data = self.hierarchy.get(type_id, {})

        # Build concept_path by traversing parents
        concept_path = self._build_path(type_id)

        # Get children
        children = [c.lower() for c in type_data.get("children", [])]

        # Get aliases
        aliases = [a.lower() for a in type_data.get("aliases", [])]

        # Determine root (last element of path)
        concept_root = concept_path[0] if concept_path else type_id

        # Leaf = no children
        is_leaf = len(children) == 0

        return TypeNode(
            concept_id=type_id,
            concept_root=concept_root,
            concept_path=concept_path,
            children=children,
            aliases=aliases,
            is_leaf=is_leaf,
            source="type_hierarchy"
        )

    def _build_path(self, type_id: str) -> List[str]:
        """
        Build path from root to type by traversing parents.

        Args:
            type_id: Type ID to build path for

        Returns:
            List from root to type_id (e.g., ["smartphone", "apple", "iphone"])
        """
        path = []
        current = type_id

        # Safety limit to prevent infinite loops
        max_depth = 20
        visited = set()

        while current and max_depth > 0:
            if current in visited:
                break
            visited.add(current)

            path.append(current)

            # Get parent
            type_data = self.hierarchy.get(current, {})
            parent = type_data.get("parent")

            if not parent:
                break

            current = parent.lower()
            max_depth -= 1

        # Reverse to get root → leaf order
        return list(reversed(path))

    def _fuzzy_match(self, query: str) -> Optional[str]:
        """
        Try to match query to a type using fuzzy matching.

        Handles cases like "iPhone 15 Pro 256GB" → "iphone 15 pro"

        Args:
            query: Normalized query string

        Returns:
            Matched type ID or None
        """
        # First try: exact match in aliases
        for type_id, type_data in self.hierarchy.items():
            aliases = [a.lower() for a in type_data.get("aliases", [])]
            if query in aliases:
                return type_id

        # Second try: check if query starts with any type
        # Sort by length (longest first) to match most specific
        sorted_types = sorted(self.hierarchy.keys(), key=len, reverse=True)
        for type_id in sorted_types:
            if query.startswith(type_id) or type_id in query:
                return type_id

        # Third try: check aliases for partial match
        for type_id, type_data in self.hierarchy.items():
            aliases = [a.lower() for a in type_data.get("aliases", [])]
            for alias in aliases:
                if query.startswith(alias) or alias in query:
                    return type_id

        return None

    def _create_unknown_node(self, type_value: str) -> TypeNode:
        """
        Create node for unknown type (not in hierarchy).

        Unknown types are treated as specific/exact (no descendants).

        Args:
            type_value: Original type value

        Returns:
            TypeNode with minimal information
        """
        normalized = type_value.lower().strip()
        return TypeNode(
            concept_id=normalized,
            concept_root=normalized,
            concept_path=[normalized],
            children=[],
            aliases=[],
            is_leaf=True,  # Unknown = treat as specific
            source="unknown"
        )

    def to_schema_format(self, node: TypeNode) -> Dict:
        """
        Convert TypeNode to schema format for storage.

        match_scope is determined by whether the type has children:
        - Leaf (no children) → "exact"
        - Non-leaf (has children) → "include_descendants"

        Args:
            node: TypeNode to convert

        Returns:
            Dict ready for schema storage (same format as categorical ontology)
        """
        # Determine match_scope based on whether it's a leaf
        match_scope = "exact" if node.is_leaf else "include_descendants"

        return {
            "concept_id": node.concept_id,
            "concept_root": node.concept_root,
            "concept_path": node.concept_path,
            "match_scope": match_scope,
            "metadata": {
                "children": node.children,
                "aliases": node.aliases,
                "source": node.source,
                "is_leaf": node.is_leaf
            }
        }

    def get_descendants(self, type_id: str) -> List[str]:
        """
        Get all descendants of a type (for debugging/testing).

        Args:
            type_id: Type ID to get descendants for

        Returns:
            List of all descendant type IDs
        """
        descendants = []
        type_id = type_id.lower()

        type_data = self.hierarchy.get(type_id, {})
        children = type_data.get("children", [])

        for child in children:
            child_lower = child.lower()
            descendants.append(child_lower)
            # Recursively get descendants of child
            descendants.extend(self.get_descendants(child_lower))

        return descendants

    def is_descendant_of(self, candidate_type: str, required_type: str) -> bool:
        """
        Check if candidate_type is a descendant of required_type.

        Args:
            candidate_type: Potential descendant type
            required_type: Required/parent type

        Returns:
            True if candidate is descendant of required
        """
        candidate_type = candidate_type.lower()
        required_type = required_type.lower()

        # Same type
        if candidate_type == required_type:
            return True

        # Check if candidate's path contains required
        candidate_node = self.resolve(candidate_type)
        if not candidate_node:
            return False

        return required_type in candidate_node.concept_path


# Singleton instance
_type_resolver_instance: Optional[TypeResolver] = None


def get_type_resolver() -> TypeResolver:
    """
    Get singleton TypeResolver instance.

    Uses settings from src.config.settings for configuration.

    Returns:
        Shared TypeResolver instance
    """
    global _type_resolver_instance
    if _type_resolver_instance is None:
        # Get hierarchy file from settings
        try:
            from src.config.settings import settings
            hierarchy_file = getattr(settings, "type_hierarchy_file", None)
        except (ImportError, AttributeError):
            hierarchy_file = None

        _type_resolver_instance = TypeResolver(hierarchy_file=hierarchy_file)
    return _type_resolver_instance
