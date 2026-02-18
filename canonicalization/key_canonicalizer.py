"""
Key Canonicalizer for Attribute Key Normalization.

Hybrid approach combining linguistic (WordNet) and semantic embeddings
to canonicalize attribute keys like "style", "variety", "kind" to a
consistent canonical form.

Layers:
1. Cache - instant lookup for previously resolved keys
2. WordNet Synset - direct synonym match
3. WordNet Hypernym - shared ancestor within depth
4. Semantic Embedding - cosine similarity (fallback)
5. Fallback - key becomes its own canonical

Domain-scoped: Keys are canonicalized within domain context (e.g., "food & beverage").
Persistent: Mappings saved to JSON for consistency across runs.
Deterministic: Same input always produces same output.
"""

import json
import os
from typing import Dict, Tuple, Optional, List
from collections import defaultdict
from datetime import datetime

# Optional imports - graceful degradation if unavailable
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Graph-based clustering disabled.")

try:
    import torch
    from sentence_transformers import SentenceTransformer, util
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    print("Warning: sentence-transformers not installed. Embedding layer disabled.")

try:
    from nltk.corpus import wordnet as wn
    # Test if wordnet data is available
    wn.synsets('test')
    HAS_WORDNET = True
except Exception:
    HAS_WORDNET = False
    print("Warning: WordNet not available. Linguistic layers disabled.")


class KeyCanonicalizer:
    """
    Hybrid key canonicalizer combining linguistic (WordNet) and semantic embeddings.

    Uses layered fallback: cache > WordNet synset > WordNet hypernym > embedding > fallback.
    Domain-scoped for context-awareness, key-only embeddings (no value contamination).
    Persistence via JSON for consistency.
    Deterministic: Stable mappings, order-independent clustering.
    """

    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        persistence_file: str = 'key_canonicals.json',
        similarity_threshold: float = 0.80,
        hypernym_depth: int = 3
    ):
        """
        Initialize the canonicalizer.

        Args:
            model_name: Pre-trained sentence-transformer model.
            persistence_file: File for persistence.
            similarity_threshold: High threshold for embedding connections to avoid false positives.
            hypernym_depth: Max depth for hypernym chain in WordNet.
        """
        self.threshold = similarity_threshold
        self.hypernym_depth = hypernym_depth
        self.persistence_file = persistence_file

        # Initialize embedding model if available
        self.model = None
        if HAS_EMBEDDINGS:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception as e:
                print(f"Warning: Could not load embedding model: {e}")

        # Domain-scoped mappings: (domain, key) -> canonical
        self.mappings: Dict[Tuple[str, str], str] = {}

        # Domain-scoped embeddings: (domain, key) -> torch.Tensor
        self.embeddings: Dict[Tuple[str, str], any] = {}

        # Domain-scoped graphs for clustering
        if HAS_NETWORKX:
            self.graphs: Dict[str, nx.Graph] = defaultdict(nx.Graph)
        else:
            self.graphs = defaultdict(dict)  # Fallback: simple dict

        # Review queue for borderline matches (manual verification)
        self.review_queue_file = persistence_file.replace('.json', '_review_queue.json')
        self.review_queue: List[Dict] = []
        self.borderline_threshold = 0.85  # Flag matches between threshold and this

        self._load_persistence()
        self._load_review_queue()

    def canonicalize(self, key: str, domain: str, value: Optional[str] = None) -> str:
        """
        Canonicalize a key using hybrid layered approach.

        Domain is required. Value is optional and NOT used in embedding (avoids contamination).

        Layers:
        1. Cache
        2. WordNet Synset
        3. WordNet Hypernym
        4. Embedding (if available)
        5. Fallback

        Args:
            key: The attribute key to canonicalize (e.g., "style")
            domain: Domain context (e.g., "food & beverage")
            value: Optional value (NOT used in canonicalization, for future extensions)

        Returns:
            The canonical key.
        """
        key = key.lower().strip()
        domain = domain.lower().strip() if domain else "general"
        cache_key = (domain, key)

        # Layer 1: Cache Lookup
        if cache_key in self.mappings:
            return self.mappings[cache_key]

        # Generate embedding once (for later if needed)
        emb = self._embed_key(key, domain)
        self.embeddings[cache_key] = emb

        if HAS_NETWORKX:
            graph = self.graphs[domain]
            graph.add_node(key)

        # Layer 2: WordNet Direct Synset Match
        if HAS_WORDNET:
            canonical = self._wordnet_synset_match(key, domain)
            if canonical:
                self._update_mapping(cache_key, canonical)
                return canonical

            # Layer 3: WordNet Hypernym Match
            canonical = self._wordnet_hypernym_match(key, domain)
            if canonical:
                self._update_mapping(cache_key, canonical)
                return canonical

        # Layer 4: Semantic Embedding Match (if available)
        if HAS_EMBEDDINGS and self.model is not None and emb is not None:
            canonical = self._embedding_match(key, domain, emb)
            if canonical:
                self._update_mapping(cache_key, canonical)
                return canonical

        # Layer 5: Fallback - key is its own canonical
        canonical = key
        self._update_mapping(cache_key, canonical)
        return canonical

    def _embed_key(self, key: str, domain: str) -> Optional[any]:
        """Embed key with domain context, without value."""
        if not HAS_EMBEDDINGS or self.model is None:
            return None

        try:
            phrase = f"In {domain} products, the attribute '{key}' describes"
            return self.model.encode(phrase)
        except Exception as e:
            print(f"Warning: Embedding failed for '{key}': {e}")
            return None

    def _wordnet_synset_match(self, key: str, domain: str) -> Optional[str]:
        """Layer 2: Check for direct synset shared with existing keys."""
        if not HAS_WORDNET:
            return None

        try:
            synsets = wn.synsets(key, pos=wn.NOUN)
            if not synsets:
                return None

            for (d, existing_key), _ in list(self.embeddings.items()):
                if d != domain or existing_key == key:
                    continue

                existing_synsets = wn.synsets(existing_key, pos=wn.NOUN)
                if set(synsets) & set(existing_synsets):
                    # Add edge for clustering
                    if HAS_NETWORKX:
                        self.graphs[domain].add_edge(key, existing_key)

                    # Return existing canonical
                    return self.mappings.get((domain, existing_key), existing_key)
        except Exception as e:
            print(f"Warning: WordNet synset match failed: {e}")

        return None

    def _wordnet_hypernym_match(self, key: str, domain: str) -> Optional[str]:
        """Layer 3: Check for shared hypernym within depth."""
        if not HAS_WORDNET:
            return None

        try:
            h1 = self._get_hypernyms(key)
            if not h1:
                return None

            for (d, existing_key), _ in list(self.embeddings.items()):
                if d != domain or existing_key == key:
                    continue

                h2 = self._get_hypernyms(existing_key)
                shared = h1 & h2

                if shared and not self._is_too_generic(shared):
                    # Add edge for clustering
                    if HAS_NETWORKX:
                        self.graphs[domain].add_edge(key, existing_key)

                    return self.mappings.get((domain, existing_key), existing_key)
        except Exception as e:
            print(f"Warning: WordNet hypernym match failed: {e}")

        return None

    def _get_hypernyms(self, word: str) -> set:
        """Get hypernyms up to specified depth."""
        if not HAS_WORDNET:
            return set()

        hypernyms = set()
        try:
            for syn in wn.synsets(word, pos=wn.NOUN):
                for path in syn.hypernym_paths():
                    hypernyms.update(path[:self.hypernym_depth])
        except Exception:
            pass

        return hypernyms

    def _is_too_generic(self, hypernyms: set) -> bool:
        """Filter out overly generic hypernyms like 'entity', 'abstraction'."""
        generics = {
            # Top-level abstractions
            'entity.n.01', 'abstraction.n.06', 'object.n.01', 'whole.n.02',
            'physical_entity.n.01', 'thing.n.12', 'psychological_feature.n.01',
            # Mid-level generics that cause false positives
            'attribute.n.02',       # connects condition/quality to unrelated terms
            'communication.n.02',   # connects brand to condition
            'group.n.01',           # connects manufacturer to state
            'relation.n.01',        # too broad
            'process.n.06',         # too broad
            'causal_agent.n.01',    # too broad
            'matter.n.03',          # too broad
        }
        try:
            return all(h.name() in generics for h in hypernyms if hasattr(h, 'name'))
        except Exception:
            return False

    def _embedding_match(self, key: str, domain: str, emb: any) -> Optional[str]:
        """Layer 4: Embedding similarity, domain-scoped, high threshold."""
        if not HAS_EMBEDDINGS or emb is None:
            return None

        try:
            for (d, existing_key), existing_emb in list(self.embeddings.items()):
                if d != domain or existing_key == key or existing_emb is None:
                    continue

                sim = util.cos_sim(emb, existing_emb).item()

                if sim > self.threshold:
                    # Flag borderline matches for review (between threshold and borderline_threshold)
                    if sim < self.borderline_threshold:
                        self._flag_for_review(
                            key1=key,
                            key2=existing_key,
                            domain=domain,
                            match_type="embedding",
                            score=sim,
                            reason=f"Borderline similarity {sim:.3f} (threshold={self.threshold}, borderline={self.borderline_threshold})"
                        )

                    # Add edge for clustering
                    if HAS_NETWORKX:
                        self.graphs[domain].add_edge(key, existing_key)

                    # Use EXISTING canonical for consistency
                    return self.mappings.get((domain, existing_key), existing_key)
        except Exception as e:
            print(f"Warning: Embedding match failed: {e}")

        return None

    def _update_mapping(self, cache_key: Tuple[str, str], canonical: str):
        """Update mappings for stability - only set if not exists."""
        domain, key = cache_key

        if HAS_NETWORKX and domain in self.graphs:
            graph = self.graphs[domain]
            if key in graph:
                try:
                    component = nx.node_connected_component(graph, key)
                    for k in component:
                        comp_key = (domain, k)
                        if comp_key not in self.mappings:
                            self.mappings[comp_key] = canonical
                except Exception:
                    # Fallback: just set this key
                    if cache_key not in self.mappings:
                        self.mappings[cache_key] = canonical
            else:
                if cache_key not in self.mappings:
                    self.mappings[cache_key] = canonical
        else:
            if cache_key not in self.mappings:
                self.mappings[cache_key] = canonical

        self._save_persistence()

    def _save_persistence(self):
        """Save state to JSON for persistence."""
        try:
            data = {
                'mappings': {f"{k[0]}|{k[1]}": v for k, v in self.mappings.items()},
                'graphs': {}
            }

            # Save graph edges if available
            if HAS_NETWORKX:
                for d, g in self.graphs.items():
                    if isinstance(g, nx.Graph):
                        data['graphs'][d] = list(g.edges())

            # Note: We don't save embeddings (they're recomputed as needed)

            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save persistence: {e}")

    def _load_persistence(self):
        """Load state from JSON if exists."""
        if not os.path.exists(self.persistence_file):
            return

        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)

            # Load mappings
            self.mappings = {
                (k.split('|')[0], k.split('|')[1]): v
                for k, v in data.get('mappings', {}).items()
            }

            # Load graph edges if available
            if HAS_NETWORKX:
                for d, edges in data.get('graphs', {}).items():
                    # Convert lists to tuples if needed (JSON loads as lists)
                    edge_tuples = [tuple(e) for e in edges]
                    self.graphs[d].add_edges_from(edge_tuples)
                    # Add all nodes from edges
                    for edge in edge_tuples:
                        for node in edge:
                            self.graphs[d].add_node(node)

            print(f"Loaded {len(self.mappings)} key mappings from persistence.")
        except Exception as e:
            print(f"Warning: Could not load persistence: {e}")

    def get_cluster(self, key: str, domain: str) -> set:
        """Return all keys in the same cluster (for debugging)."""
        key = key.lower().strip()
        domain = domain.lower().strip()

        if HAS_NETWORKX and domain in self.graphs:
            graph = self.graphs[domain]
            if key in graph:
                try:
                    return nx.node_connected_component(graph, key)
                except Exception:
                    pass

        return {key}

    def explain(self, key: str, domain: str) -> dict:
        """Explain why a key maps to its canonical (for debugging)."""
        canonical = self.canonicalize(key, domain)
        cluster = self.get_cluster(key, domain)

        return {
            "key": key,
            "domain": domain,
            "canonical": canonical,
            "cluster": list(cluster),
            "cluster_size": len(cluster)
        }

    # ==================== REVIEW QUEUE METHODS ====================

    def _flag_for_review(
        self,
        key1: str,
        key2: str,
        domain: str,
        match_type: str,
        score: float,
        reason: str
    ):
        """Flag a match for manual review."""
        # Check if already flagged (avoid duplicates)
        for entry in self.review_queue:
            if (entry["key1"] == key1 and entry["key2"] == key2 and
                entry["domain"] == domain and entry["status"] == "pending"):
                return  # Already flagged

        entry = {
            "id": f"{domain}|{key1}|{key2}|{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "key1": key1,
            "key2": key2,
            "domain": domain,
            "match_type": match_type,
            "score": round(score, 4),
            "reason": reason,
            "status": "pending"  # pending, approved, rejected
        }
        self.review_queue.append(entry)
        self._save_review_queue()
        print(f"[REVIEW] Flagged for review: '{key1}' <-> '{key2}' in {domain} (score={score:.3f})")

    def _save_review_queue(self):
        """Save review queue to JSON file."""
        try:
            with open(self.review_queue_file, 'w') as f:
                json.dump(self.review_queue, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save review queue: {e}")

    def _load_review_queue(self):
        """Load review queue from JSON file."""
        if not os.path.exists(self.review_queue_file):
            self.review_queue = []
            return

        try:
            with open(self.review_queue_file, 'r') as f:
                self.review_queue = json.load(f)
            pending_count = sum(1 for e in self.review_queue if e.get("status") == "pending")
            if pending_count > 0:
                print(f"Loaded {pending_count} pending review items.")
        except Exception as e:
            print(f"Warning: Could not load review queue: {e}")
            self.review_queue = []

    def get_pending_reviews(self) -> List[Dict]:
        """Get all pending review items."""
        return [e for e in self.review_queue if e.get("status") == "pending"]

    def get_all_reviews(self, status: Optional[str] = None) -> List[Dict]:
        """Get all review items, optionally filtered by status."""
        if status:
            return [e for e in self.review_queue if e.get("status") == status]
        return self.review_queue

    def approve_match(self, key1: str, key2: str, domain: str) -> bool:
        """
        Approve a flagged match. The match stays in cache.

        Returns True if found and approved, False otherwise.
        """
        for entry in self.review_queue:
            if (entry["key1"] == key1 and entry["key2"] == key2 and
                entry["domain"] == domain and entry["status"] == "pending"):
                entry["status"] = "approved"
                entry["reviewed_at"] = datetime.now().isoformat()
                self._save_review_queue()
                print(f"[REVIEW] Approved: '{key1}' <-> '{key2}' in {domain}")
                return True
        return False

    def reject_match(
        self,
        key1: str,
        key2: str,
        domain: str,
        block_hypernym: Optional[str] = None
    ) -> bool:
        """
        Reject a flagged match. Removes from cache and optionally blocks a hypernym.

        Args:
            key1: First key in the match
            key2: Second key in the match
            domain: Domain of the match
            block_hypernym: Optional hypernym to add to generics filter (e.g., 'property.n.02')

        Returns True if found and rejected, False otherwise.
        """
        for entry in self.review_queue:
            if (entry["key1"] == key1 and entry["key2"] == key2 and
                entry["domain"] == domain and entry["status"] == "pending"):
                entry["status"] = "rejected"
                entry["reviewed_at"] = datetime.now().isoformat()
                if block_hypernym:
                    entry["blocked_hypernym"] = block_hypernym

                # Remove the mapping for key1 (it should become its own canonical)
                cache_key1 = (domain, key1)
                if cache_key1 in self.mappings:
                    del self.mappings[cache_key1]

                # Remove edge from graph
                if HAS_NETWORKX and domain in self.graphs:
                    graph = self.graphs[domain]
                    if graph.has_edge(key1, key2):
                        graph.remove_edge(key1, key2)

                # Set key1 as its own canonical
                self.mappings[cache_key1] = key1

                self._save_persistence()
                self._save_review_queue()
                print(f"[REVIEW] Rejected: '{key1}' <-> '{key2}' in {domain}")
                if block_hypernym:
                    print(f"[REVIEW] Note: Add '{block_hypernym}' to generics filter manually.")
                return True
        return False

    def review_summary(self) -> Dict:
        """Get a summary of the review queue."""
        pending = sum(1 for e in self.review_queue if e.get("status") == "pending")
        approved = sum(1 for e in self.review_queue if e.get("status") == "approved")
        rejected = sum(1 for e in self.review_queue if e.get("status") == "rejected")

        return {
            "total": len(self.review_queue),
            "pending": pending,
            "approved": approved,
            "rejected": rejected
        }


# Convenience function for use in orchestrator
def canonicalize_key(key: str, domain: str) -> str:
    """
    Convenience function to canonicalize a key.

    Uses a module-level singleton to avoid repeated initialization.
    """
    global _key_canonicalizer_instance

    if '_key_canonicalizer_instance' not in globals():
        _key_canonicalizer_instance = KeyCanonicalizer()

    return _key_canonicalizer_instance.canonicalize(key, domain)
