"""
Generic Categorical Attribute Resolver.

This resolver works for ANY categorical attribute (color, brand, condition, fuel, etc.)
without hardcoding specific logic. It uses a multi-tier API cascade to build
ontology trees dynamically.

New Pipeline (USE_NEW_PIPELINE=1, default):
  Phase 0: Preprocess (static dicts, local, instant)
  Phase 1: Disambiguate (gather candidates from ALL 5 sources, score, pick best)
  Phase 2: Canonicalize (cross-tier propagation, registry, label extraction)

Legacy Pipeline (USE_NEW_PIPELINE=0):
  1. Synonym registry -> 2. WordNet -> 3. BabelNet -> 4. Wikidata -> 5. Fallback

Output Format (Ontology-Grounded):
{
    "concept_id": "navy blue",
    "concept_root": "color",
    "concept_path": ["color", "blue", "navy blue"],
    "match_scope": "exact"  # or "include_descendants"
}
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from services.external.wordnet_wrapper import get_wordnet_client
from services.external.babelnet_wrapper import get_babelnet_client
from services.external.wikidata_wrapper import get_wikidata_client


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
        source: Where this came from (wordnet, babelnet, wikidata, etc.)
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

    Uses API-driven ontology building to work with any attribute type.
    Maintains a synonym registry so that aliases of the same entity
    resolve to the same concept_id within the same session.

    Pipeline selection via USE_NEW_PIPELINE env var (defaults to "1"):
    - "1": New 3-phase pipeline (preprocess -> disambiguate -> canonicalize)
    - "0": Legacy cascade (synonym_registry -> WordNet -> BabelNet -> Wikidata -> fallback)
    """

    def __init__(self):
        self.wordnet = get_wordnet_client()
        self.babelnet = get_babelnet_client()
        self.wikidata = get_wikidata_client()
        # Maps alias.lower() -> canonical concept_id
        self._synonym_registry: Dict[str, str] = {}
        # Maps concept_id -> concept_path for hierarchy matching
        self._concept_paths: Dict[str, List[str]] = {}
        # Load persisted ontology from DB (if OntologyStore is initialized)
        self._load_persisted_ontology()

    def _load_persisted_ontology(self) -> None:
        """Load synonym_registry and concept_paths from OntologyStore if available."""
        try:
            from canonicalization.ontology_store import get_ontology_store
            store = get_ontology_store()
            if store.is_initialized:
                data = store.load_from_db()
                self._synonym_registry.update(data.get("synonym_registry", {}))
                self._concept_paths.update(data.get("concept_paths", {}))
        except Exception as e:
            print(f"Resolver: could not load persisted ontology: {e}")

    def reload_from_db(self) -> None:
        """Explicitly reload ontology from DB (e.g., after table creation)."""
        self._load_persisted_ontology()

    def _register_synonyms(self, concept_id: str, aliases: List[str]) -> None:
        """Register all aliases as mapping to the same concept_id."""
        for alias in aliases:
            key = alias.lower().strip()
            if key:
                self._synonym_registry[key] = concept_id

    def _register_concept_path(self, concept_id: str, concept_path: List[str]) -> None:
        """Register a concept_path for hierarchy matching."""
        if concept_id and concept_path:
            self._concept_paths[concept_id] = concept_path

    def _buffer_to_store(self, node: "OntologyNode", sense) -> None:
        """Buffer a newly resolved concept to OntologyStore for DB persistence."""
        try:
            from canonicalization.ontology_store import get_ontology_store
            store = get_ontology_store()
            if not store.is_initialized:
                return
            synonyms = list(set(
                [node.concept_id] +
                node.siblings +
                [s.lower() for s in getattr(sense, 'all_forms', [])]
            ))
            store.buffer_concept(
                concept_id=node.concept_id,
                concept_path=node.concept_path,
                synonyms=synonyms,
                source=node.source,
                confidence=node.confidence,
            )
        except Exception as e:
            print(f"Resolver: buffer_to_store error: {e}")

    def is_ancestor(self, ancestor: str, concept_id: str, max_depth: int = 5) -> bool:
        """
        Check if ancestor is an ancestor of concept_id.

        Uses multiple strategies:
        1. Check stored concept_paths
        2. Check WordNet hypernym paths (dynamic, works for any terms)

        Used for hierarchy matching: "chromatic color" is_ancestor of "red"
        because red IS-A chromatic color in WordNet.
        """
        ancestor_lower = ancestor.lower().strip()
        concept_lower = concept_id.lower().strip()

        # Strategy 1: Check stored concept_paths
        path = self._concept_paths.get(concept_lower)
        if path:
            try:
                ancestor_idx = -1
                concept_idx = -1
                for i, p in enumerate(path):
                    if p == ancestor_lower:
                        ancestor_idx = i
                    if p == concept_lower:
                        concept_idx = i
                if ancestor_idx >= 0 and concept_idx >= 0 and ancestor_idx < concept_idx:
                    return True
            except Exception:
                pass

        # Strategy 2: Use WordNet hypernym paths (dynamic)
        try:
            from nltk.corpus import wordnet as wn

            # Get synsets for both terms (prefer nouns)
            concept_synsets = wn.synsets(concept_lower.replace(" ", "_"), pos='n')
            if not concept_synsets:
                concept_synsets = wn.synsets(concept_lower.replace(" ", "_"))

            ancestor_synsets = wn.synsets(ancestor_lower.replace(" ", "_"), pos='n')
            if not ancestor_synsets:
                ancestor_synsets = wn.synsets(ancestor_lower.replace(" ", "_"))

            if not concept_synsets or not ancestor_synsets:
                return False

            ancestor_synset_set = set(ancestor_synsets)

            # Check if any ancestor synset appears in concept's hypernym path
            for concept_syn in concept_synsets:
                for hypernym_path in concept_syn.hypernym_paths():
                    # Depth should be measured from concept (end of path), not root
                    # hypernym_path goes: [entity...ancestor...concept]
                    # Reverse to check from concept upward
                    path_len = len(hypernym_path)
                    for depth_from_concept, hyp in enumerate(reversed(hypernym_path)):
                        if depth_from_concept > max_depth:
                            break
                        if hyp in ancestor_synset_set:
                            return True
        except Exception:
            pass

        return False

    def resolve(
        self,
        value: str,
        context: Optional[str] = None,
        attribute_key: Optional[str] = None
    ) -> Optional[OntologyNode]:
        """
        Resolve a categorical value to ontology node.

        Routes to new pipeline or legacy based on USE_NEW_PIPELINE env var.
        """
        if os.getenv("USE_NEW_PIPELINE", "1") == "1":
            return self._resolve_new_pipeline(value, context, attribute_key)
        return self._resolve_legacy(value, context, attribute_key)

    # ═══════════════════════════════════════════════════════════════════
    # NEW PIPELINE (Phase 0 -> Phase 1 -> Phase 2)
    # ═══════════════════════════════════════════════════════════════════

    def _resolve_new_pipeline(
        self,
        value: str,
        context: Optional[str] = None,
        attribute_key: Optional[str] = None
    ) -> Optional[OntologyNode]:
        """
        New 3-phase pipeline: Preprocess -> Disambiguate -> Canonicalize.
        """
        from canonicalization.preprocessor import preprocess, normalize_for_registry_lookup
        from canonicalization.disambiguator import disambiguate
        from canonicalization.canonicalizer import canonicalize, enrich_hypernyms

        # Phase 0: Preprocess
        preprocessed = preprocess(value, attribute_key)

        # Registry check (both raw and compound-normalized forms)
        for key in [preprocessed, normalize_for_registry_lookup(preprocessed)]:
            if key and key in self._synonym_registry:
                concept_id = self._synonym_registry[key]
                path = self._concept_paths.get(concept_id, [])
                if not path:
                    path = [attribute_key.lower(), concept_id] if attribute_key else [concept_id]
                return OntologyNode(
                    concept_id=concept_id,
                    concept_root=attribute_key.lower() if attribute_key else concept_id,
                    concept_path=path,
                    parents=[],
                    children=[],
                    siblings=[],
                    source="synonym_registry",
                    confidence=0.85,
                )

        # Phase 1: Disambiguate
        sense = disambiguate(preprocessed, context=attribute_key)
        if not sense:
            return self._create_simple_node(preprocessed, attribute_key)

        # Enrich hypernyms if missing
        sense = enrich_hypernyms(sense)

        # Phase 2: Canonicalize
        node = canonicalize(sense, value, attribute_key, self._synonym_registry)

        # Register concept_path for hierarchy matching
        self._register_concept_path(node.concept_id, node.concept_path)

        # Buffer to OntologyStore for DB persistence
        self._buffer_to_store(node, sense)

        return node

    # ═══════════════════════════════════════════════════════════════════
    # LEGACY PIPELINE (old cascade, preserved for rollback)
    # ═══════════════════════════════════════════════════════════════════

    def _resolve_legacy(
        self,
        value: str,
        context: Optional[str] = None,
        attribute_key: Optional[str] = None
    ) -> Optional[OntologyNode]:
        """
        Legacy resolution cascade: synonym_registry -> WordNet -> BabelNet -> Wikidata -> fallback.

        Preserved for instant rollback via USE_NEW_PIPELINE=0.
        """
        # Check synonym registry first (instant, no API call)
        cached_concept_id = self._synonym_registry.get(value.lower().strip())
        if cached_concept_id:
            return OntologyNode(
                concept_id=cached_concept_id,
                concept_root=attribute_key.lower() if attribute_key else cached_concept_id,
                concept_path=[attribute_key.lower(), cached_concept_id] if attribute_key else [cached_concept_id],
                parents=[],
                children=[],
                siblings=[],
                source="synonym_registry",
                confidence=0.85
            )

        # Tier 1: WordNet (local, fast)
        node = self._resolve_via_wordnet(value)

        # Tier 2: BabelNet (API, disambiguated with attribute_key)
        if not node:
            node = self._resolve_via_babelnet(value, attribute_key)

        # Tier 3: Wikidata (API, disambiguated with attribute_key)
        if not node:
            node = self._resolve_via_wikidata(value, attribute_key)

        # Tier 4: Fallback
        if not node:
            return self._create_simple_node(value, attribute_key)

        return node

    def _resolve_via_wordnet(self, value: str) -> Optional[OntologyNode]:
        """Resolve using local WordNet via NLTK."""
        try:
            hierarchy = self.wordnet.get_hierarchy(value)

            if not hierarchy:
                return None

            parents = hierarchy.get("parents", [])
            children = hierarchy.get("children", [])
            related = hierarchy.get("related", [])

            # Register synonyms from WordNet
            if related:
                concept_id = value.lower()
                self._register_synonyms(concept_id, related + [value])

            paths = self.wordnet.find_path_to_root(value, max_depth=5)

            if paths:
                shortest_path = min(paths, key=len)
                concept_root = shortest_path[-1] if shortest_path else value

                return OntologyNode(
                    concept_id=value.lower(),
                    concept_root=concept_root.lower(),
                    concept_path=[p.lower() for p in reversed(shortest_path)],
                    parents=[p.lower() for p in parents],
                    children=[c.lower() for c in children],
                    siblings=[r.lower() for r in related],
                    source="wordnet",
                    confidence=0.8
                )

            if parents:
                return OntologyNode(
                    concept_id=value.lower(),
                    concept_root=parents[0].lower() if parents else value.lower(),
                    concept_path=[parents[0].lower(), value.lower()] if parents else [value.lower()],
                    parents=[p.lower() for p in parents],
                    children=[c.lower() for c in children],
                    siblings=[r.lower() for r in related],
                    source="wordnet",
                    confidence=0.7
                )

            return None

        except Exception as e:
            print(f"WordNet resolution error for '{value}': {e}")
            return None

    def _resolve_via_babelnet(self, value: str, attribute_key: Optional[str] = None) -> Optional[OntologyNode]:
        """
        Resolve using BabelNet API with embedding-based disambiguation.

        Passes attribute_key as context so BabelNet picks the correct synset
        (e.g., "second hand" + "condition" -> used goods, not card game).
        """
        try:
            canonical = self.babelnet.get_canonical(value, context=attribute_key)

            if not canonical:
                return None

            concept_id = canonical["canonical_label"]
            synonyms = canonical.get("synonyms", [])
            linked_wikidata = canonical.get("linked_wikidata")

            # Register all synonyms -> canonical label
            self._register_synonyms(concept_id, synonyms + [value])

            # Get hierarchy for concept path
            parents = canonical.get("parents", [])

            return OntologyNode(
                concept_id=concept_id,
                concept_root=attribute_key.lower() if attribute_key else concept_id,
                concept_path=[attribute_key.lower(), concept_id] if attribute_key else [concept_id],
                parents=[p.lower() for p in parents],
                children=[],
                siblings=[s.lower() for s in synonyms],
                source="babelnet",
                confidence=0.85
            )

        except Exception as e:
            print(f"BabelNet resolution error for '{value}': {e}")
            return None

    def _resolve_via_wikidata(self, value: str, attribute_key: Optional[str] = None) -> Optional[OntologyNode]:
        """
        Resolve using Wikidata API with embedding-based disambiguation.

        Passes attribute_key as context so Wikidata picks the correct entity
        (e.g., "second hand" + "condition" -> used goods entity, not clock hand).
        """
        try:
            canonical = self.wikidata.get_canonical(value, context=attribute_key)

            if not canonical:
                return None

            concept_id = canonical["canonical_label"]
            aliases = canonical.get("aliases", [])

            # Register all aliases -> canonical label
            self._register_synonyms(concept_id, aliases + [value])

            # Get hierarchy path
            entity_id = canonical.get("entity_id")
            paths = []
            if entity_id:
                paths = self.wikidata.get_hierarchy_path(value, max_depth=3)

            if paths:
                shortest_path = min(paths, key=len)
                path_labels = [node["label"].lower() for node in shortest_path]

                parents = []
                if len(shortest_path) > 1:
                    parents = [shortest_path[-2]["label"].lower()]

                return OntologyNode(
                    concept_id=concept_id,
                    concept_root=path_labels[-1] if path_labels else concept_id,
                    concept_path=list(reversed(path_labels)),
                    parents=parents,
                    children=[],
                    siblings=[a.lower() for a in aliases],
                    source="wikidata",
                    confidence=0.9
                )

            return OntologyNode(
                concept_id=concept_id,
                concept_root=attribute_key.lower() if attribute_key else concept_id,
                concept_path=[attribute_key.lower(), concept_id] if attribute_key else [concept_id],
                parents=[],
                children=[],
                siblings=[a.lower() for a in aliases],
                source="wikidata",
                confidence=0.6
            )

        except Exception as e:
            print(f"Wikidata resolution error for '{value}': {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # SHARED HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _create_simple_node(
        self, value: str, attribute_key: Optional[str] = None
    ) -> OntologyNode:
        """Create a simple node when API resolution fails."""
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
        """Convert OntologyNode to schema format for storage."""
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
