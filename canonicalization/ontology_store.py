"""
OntologyStore: Persistent storage for concept ontology.

Manages the concept_ontology table in Supabase, providing:
- Bulk load on startup (populates in-memory synonym_registry + concept_paths)
- Buffered upserts during ingestion (write-behind pattern)
- Flush to DB after canonicalization completes
- Graceful degradation if DB is unavailable

Singleton pattern — one store shared across the app.
"""

import time
from typing import Dict, List, Optional, Set
from threading import Lock


class OntologyStore:
    """
    Persistent ontology store backed by Supabase concept_ontology table.

    Lifecycle:
        1. initialize(supabase_client) — connect to DB
        2. load_from_db() — bulk load all concepts into memory
        3. buffer_concept(...) — buffer new concepts during ingestion
        4. flush_to_db() — write buffered concepts to DB
    """

    TABLE_NAME = "concept_ontology"

    def __init__(self):
        self._supabase = None
        self._initialized = False
        self._lock = Lock()

        # Buffered concepts waiting to be flushed to DB
        # Key: concept_id, Value: {concept_path, synonyms, source, confidence}
        self._pending: Dict[str, Dict] = {}

        # Track which concept_ids are already in DB (avoid redundant upserts)
        self._known_ids: Set[str] = set()

        # Stats
        self._load_count = 0
        self._flush_count = 0

    def initialize(self, supabase_client) -> None:
        """
        Connect to Supabase and mark as initialized.

        Args:
            supabase_client: Initialized Supabase client from IngestionClients.
        """
        self._supabase = supabase_client
        self._initialized = True
        print("OntologyStore: initialized with Supabase client")

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self._supabase is not None

    def load_from_db(self) -> Dict:
        """
        Bulk load all concepts from concept_ontology table into memory.

        Returns:
            Dict with 'synonym_registry' and 'concept_paths' ready to inject
            into GenericCategoricalResolver.

        Returns empty dicts if DB unavailable or table doesn't exist.
        """
        synonym_registry: Dict[str, str] = {}
        concept_paths: Dict[str, List[str]] = {}

        if not self.is_initialized:
            print("OntologyStore: not initialized, returning empty state")
            return {"synonym_registry": synonym_registry, "concept_paths": concept_paths}

        try:
            # Fetch all rows (paginated for large tables)
            all_rows = []
            page_size = 1000
            offset = 0

            while True:
                response = (
                    self._supabase.table(self.TABLE_NAME)
                    .select("concept_id, concept_path, synonyms")
                    .range(offset, offset + page_size - 1)
                    .execute()
                )

                if not response.data:
                    break

                all_rows.extend(response.data)
                if len(response.data) < page_size:
                    break
                offset += page_size

            # Build in-memory structures
            for row in all_rows:
                concept_id = row["concept_id"]
                path = row.get("concept_path", [])
                synonyms = row.get("synonyms", [])

                # Register concept_path
                if path:
                    concept_paths[concept_id] = path

                # Register all synonyms -> concept_id
                for syn in synonyms:
                    syn_lower = syn.lower().strip()
                    if syn_lower:
                        synonym_registry[syn_lower] = concept_id

                # Also map concept_id -> itself
                synonym_registry[concept_id] = concept_id

                # Track known IDs
                self._known_ids.add(concept_id)

            self._load_count = len(all_rows)
            print(f"OntologyStore: loaded {self._load_count} concepts "
                  f"({len(synonym_registry)} synonym mappings, "
                  f"{len(concept_paths)} paths)")

        except Exception as e:
            print(f"OntologyStore: load_from_db error (table may not exist yet): {e}")

        return {"synonym_registry": synonym_registry, "concept_paths": concept_paths}

    def buffer_concept(
        self,
        concept_id: str,
        concept_path: List[str],
        synonyms: List[str],
        source: str = "unknown",
        confidence: float = 0.0,
    ) -> None:
        """
        Buffer a concept for later flush to DB.

        Called during canonicalization when a new concept is resolved.
        Merges synonyms if concept already buffered.

        Args:
            concept_id: Canonical concept identifier.
            concept_path: Full hierarchy path.
            synonyms: All known synonyms/aliases.
            source: Resolution source (wordnet, wikidata, etc.).
            confidence: Disambiguation confidence score.
        """
        if not concept_id:
            return

        with self._lock:
            if concept_id in self._pending:
                # Merge synonyms (union)
                existing = set(self._pending[concept_id].get("synonyms", []))
                existing.update(s.lower().strip() for s in synonyms if s)
                self._pending[concept_id]["synonyms"] = sorted(existing)
                # Update path if new one is longer (more detailed)
                if len(concept_path) > len(self._pending[concept_id].get("concept_path", [])):
                    self._pending[concept_id]["concept_path"] = concept_path
            else:
                self._pending[concept_id] = {
                    "concept_path": concept_path,
                    "synonyms": sorted(set(s.lower().strip() for s in synonyms if s)),
                    "source": source,
                    "confidence": confidence,
                }

    def flush_to_db(self) -> int:
        """
        Write all buffered concepts to DB via upsert.

        Returns:
            Number of concepts flushed.
        """
        if not self.is_initialized:
            return 0

        with self._lock:
            if not self._pending:
                return 0
            # Snapshot and clear buffer
            to_flush = dict(self._pending)
            self._pending.clear()

        flushed = 0
        for concept_id, data in to_flush.items():
            try:
                row = {
                    "concept_id": concept_id,
                    "concept_path": data["concept_path"],
                    "synonyms": data["synonyms"],
                    "source": data.get("source", "unknown"),
                    "confidence": data.get("confidence", 0.0),
                }

                if concept_id in self._known_ids:
                    # Concept already in DB — merge synonyms
                    existing = self._get_existing(concept_id)
                    if existing:
                        merged_synonyms = sorted(set(
                            existing.get("synonyms", []) + data["synonyms"]
                        ))
                        row["synonyms"] = merged_synonyms
                        # Keep longer path
                        if len(existing.get("concept_path", [])) > len(data["concept_path"]):
                            row["concept_path"] = existing["concept_path"]

                self._supabase.table(self.TABLE_NAME).upsert(
                    row, on_conflict="concept_id"
                ).execute()

                self._known_ids.add(concept_id)
                flushed += 1

            except Exception as e:
                print(f"OntologyStore: flush error for '{concept_id}': {e}")
                # Re-buffer failed concept for next flush
                with self._lock:
                    if concept_id not in self._pending:
                        self._pending[concept_id] = data

        if flushed > 0:
            self._flush_count += flushed
            print(f"OntologyStore: flushed {flushed} concepts to DB "
                  f"(total flushed: {self._flush_count})")

        return flushed

    def _get_existing(self, concept_id: str) -> Optional[Dict]:
        """Fetch a single concept from DB for merge."""
        try:
            response = (
                self._supabase.table(self.TABLE_NAME)
                .select("concept_path, synonyms")
                .eq("concept_id", concept_id)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]
        except Exception:
            pass
        return None

    def get_stats(self) -> Dict:
        """Get store statistics."""
        return {
            "initialized": self.is_initialized,
            "loaded_concepts": self._load_count,
            "total_flushed": self._flush_count,
            "pending_buffer": len(self._pending),
            "known_ids": len(self._known_ids),
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_ontology_store: Optional[OntologyStore] = None


def get_ontology_store() -> OntologyStore:
    """Get singleton OntologyStore instance."""
    global _ontology_store
    if _ontology_store is None:
        _ontology_store = OntologyStore()
    return _ontology_store
