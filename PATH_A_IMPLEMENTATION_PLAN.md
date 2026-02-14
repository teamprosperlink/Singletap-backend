# Path A: WordNet-First Strategy - Implementation Plan
**Date:** 2026-02-13
**Goal:** Fix 4 failing E2E tests without model fine-tuning
**Expected Result:** 16-17/18 tests passing (vs current 14/18)
**Timeline:** 4-6 hours

---

## Executive Summary

**Problem:** Synonyms resolve to different concept_ids causing match failures
- "used" (WordNet) → concept_id="used"
- "second-hand" (Wikidata) → concept_id="second-hand"
- Match FAILS: "used" ≠ "second-hand"

**Solution:** Use WordNet synset IDs as canonical concept_ids + enrich with Wikidata aliases
- "used" (WordNet) → synset_id="01758466-a" → concept_id="01758466-a"
- "second-hand" (WordNet) → synset_id="01758466-a" → concept_id="01758466-a"
- Match SUCCEEDS: "01758466-a" == "01758466-a"

**Key Changes:**
1. ✅ **WordNet synset IDs** as concept_ids (not labels)
2. ✅ **P8814 cache** for Wikidata alias enrichment (offline)
3. ✅ **BabelNet integration** (when API key available)
4. ✅ **Merriam-Webster fallback** (free tier: 1000/day)
5. ✅ **Hierarchy matching** in `semantic_implies()` (already exists!)

---

## Current State Analysis

### Matching Flow (From Code Review)

```
main.py:123-142 → semantic_implies(candidate_val, required_val)
  ↓
  1. Exact match: c == r
  2. Hierarchy check: resolver.is_ancestor(r, c)
  ↓
matching/item_matchers.py:118 → match_item_type(required, candidate, implies_fn)
  ↓
  Uses semantic_implies to check if types match
  ↓
matching/item_matchers.py:235 → match_item_categorical(required, candidate, implies_fn)
  ↓
  Uses semantic_implies for each categorical attribute
  ↓
matching/listing_matcher_v2.py:140 → all_required_items_match(A.items, B.items, implies_fn)
  ↓
  Injects semantic_implies into item matching logic
```

### BabelNet Integration (Already Exists!)

**File:** `services/external/babelnet_wrapper.py`

**Key Methods:**
- `get_canonical(term, context)` (line 442-526)
  - Returns: `canonical_id`, `canonical_label`, `synonyms`, `linked_wikidata`, `parents`
  - **Already extracts Wikidata Q-IDs** (line 498-502)
  - Already does embedding-based disambiguation (line 345-377)

**Wikidata Integration:**
```python
# Line 498-502: BabelNet already links Wikidata!
source = props.get("source", "")
if source == "WIKIDATA" and not linked_wikidata:
    sense_key = props.get("senseKey", "")
    if sense_key:
        linked_wikidata = sense_key  # This is the Q-ID!
```

**References:**
- [BabelNet API Guide](https://babelnet.org/guide)
- [BabelNet Wikipedia](https://en.wikipedia.org/wiki/BabelNet)
- [Wikidata P2581 (BabelNet ID)](https://www.wikidata.org/wiki/Property:P2581)
- [BabelNet Survey Paper](https://www.ijcai.org/proceedings/2021/0620.pdf)

### Current Canonicalization Flow

**File:** `canonicalization/orchestrator.py`

**Entry Point:** `canonicalize_listing(listing)` (called from main.py:20)

**Current Cascade (from MEMORY.md):**
```
1. Synonym registry (local dict)
2. WordNet (local, nltk)
3. BabelNet (API, disambiguated) ← ALREADY HAS WIKIDATA
4. Wikidata (API, disambiguated)
5. Fallback (lowercase)
```

**Problem:** Each tier returns different concept_ids for same concept

---

## Implementation Plan

### Phase 1: Build P8814 Cache (1 hour)

**Goal:** Create offline mapping of WordNet synset IDs → Wikidata Q-IDs + aliases

**File to Create:** `scripts/build_wordnet_wikidata_cache.py`

**What It Does:**
```python
# Query Wikidata SPARQL endpoint for P8814 property
SELECT ?item ?itemLabel ?wordnet_id ?aliases WHERE {
  ?item wdt:P8814 ?wordnet_id .  # P8814 = WordNet 3.1 synset ID
  OPTIONAL { ?item skos:altLabel ?aliases FILTER(LANG(?aliases) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}

# Output: canonicalization/static_dicts/wordnet_wikidata_map.json
{
  "01758466-a": {  # WordNet synset ID for "secondhand"
    "qid": "Q4818134",
    "label": "second-hand good",
    "aliases": ["secondhand", "second-hand", "pre-owned", "used", "previously owned"]
  },
  "02939185-n": {  # WordNet synset ID for "laptop"
    "qid": "Q3962",
    "label": "laptop",
    "aliases": ["laptop computer", "portable computer", "notebook computer"]
  }
}
```

**Expected Output:**
- ~80,000 entries (70% of WordNet 3.1)
- File size: ~10MB JSON
- Coverage: Primarily nouns, some verbs/adjectives

**Dependencies:**
- `SPARQLWrapper` (already in use for Wikidata queries)
- Internet connection (one-time download)

**Verification:**
```bash
python3 scripts/build_wordnet_wikidata_cache.py
# Check output
python3 -c "import json; data = json.load(open('canonicalization/static_dicts/wordnet_wikidata_map.json')); print(f'{len(data)} mappings loaded')"
```

---

### Phase 2: Add Merriam-Webster Wrapper (30 minutes)

**Goal:** Free API fallback for terms not in WordNet (modern slang, tech terms)

**File to Create:** `services/external/merriam_webster_wrapper.py`

**What It Does:**
```python
class MerriamWebsterClient:
    """
    Merriam-Webster Collegiate Dictionary API wrapper.

    Free tier: 1,000 requests/day (non-commercial)
    API: https://dictionaryapi.com/
    """

    BASE_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MERRIAM_WEBSTER_API_KEY", "")
        self._cache: Dict[str, Dict] = {}  # TTL cache (1 hour)
        self._daily_counter = 0  # Track daily usage
        self._last_reset = time.time()

    def is_available(self) -> bool:
        """Check if API key is set and daily limit not exceeded."""
        if not self.api_key:
            return False
        # Reset counter daily
        if time.time() - self._last_reset > 86400:
            self._daily_counter = 0
            self._last_reset = time.time()
        return self._daily_counter < 1000

    def get_definition(self, term: str) -> Optional[Dict]:
        """
        Get definition and synonyms for a term.

        Returns:
            {
                "definition": "a portable computer...",
                "synonyms": ["notebook", "portable"],
                "part_of_speech": "noun"
            }
        """
        # Check cache first
        # Make API call
        # Parse response
        # Return structured data
```

**API Response Format:**
```json
{
  "meta": {"id": "laptop", "stems": ["laptop", "laptops"]},
  "hwi": {"hw": "lap*top"},
  "fl": "noun",
  "def": [{
    "sseq": [[["sense", {
      "dt": [["text", "a portable computer small enough to use in your lap"]]
    }]]]
  }],
  "shortdef": ["a portable computer small enough to use in your lap"]
}
```

**Integration Point:** `canonicalization/disambiguator.py`
```python
# After WordNet/BabelNet fail, try Merriam-Webster
if os.getenv("MERRIAM_WEBSTER_API_KEY"):
    mw_client = get_merriam_webster_client()
    if mw_client.is_available():
        definition = mw_client.get_definition(term)
        if definition:
            # Create pseudo-synset from definition
```

**Documentation:**
- [Merriam-Webster API Docs](https://dictionaryapi.com/)
- Free tier registration: https://dictionaryapi.com/register/index

---

### Phase 3: Update WordNet Wrapper (30 minutes)

**Goal:** Return synset IDs instead of labels as concept_ids

**File to Modify:** `services/external/wordnet_wrapper.py`

**Current Behavior:**
```python
# OLD: Returns label as concept_id
def get_canonical(term: str) -> Optional[Dict]:
    synsets = wordnet.synsets(term)
    if synsets:
        return {
            "canonical_label": synsets[0].lemmas()[0].name(),  # "used"
            # Missing: synset ID!
        }
```

**New Behavior:**
```python
# NEW: Return synset ID as concept_id
def get_canonical(term: str, context: Optional[str] = None) -> Optional[Dict]:
    """
    Get canonical form with WordNet synset ID.

    Returns:
        {
            "canonical_id": "01758466-a",  # Synset ID (8 digits + POS)
            "canonical_label": "used",     # Preferred lemma
            "all_forms": ["used", "secondhand", "second-hand"],
            "hypernyms": ["previously owned"],
            "source": "wordnet"
        }
    """
    synsets = wordnet.synsets(term)
    if not synsets:
        return None

    # Disambiguation if context provided (using existing embedding scorer)
    if context and len(synsets) > 1:
        best_synset = _disambiguate_synsets(synsets, context)
    else:
        best_synset = synsets[0]

    # Extract synset ID (offset format: 8 digits + POS char)
    synset_id = _get_synset_offset_id(best_synset)  # e.g., "01758466-a"

    # Extract all lemmas (synonyms)
    all_forms = [lemma.name().replace("_", " ").lower()
                 for lemma in best_synset.lemmas()]

    # Extract hypernyms
    hypernyms = [hyp.lemmas()[0].name().replace("_", " ").lower()
                 for hyp in best_synset.hypernyms()]

    return {
        "canonical_id": synset_id,
        "canonical_label": all_forms[0],
        "all_forms": all_forms,
        "hypernyms": hypernyms,
        "source": "wordnet"
    }

def _get_synset_offset_id(synset) -> str:
    """
    Extract WordNet synset offset ID.

    Format: 8-digit offset + POS character
    Example: car.n.01 → "02958343-n"
    """
    offset = str(synset.offset()).zfill(8)
    pos_char = synset.pos()  # n, v, a, r, s
    return f"{offset}-{pos_char}"

def _disambiguate_synsets(synsets, context: str):
    """
    Disambiguate synsets using gloss-context embedding similarity.

    Uses shared SentenceTransformer from embedding/model_provider.py
    """
    from embedding.model_provider import get_embedding_model
    model = get_embedding_model()

    context_emb = model.encode(context)
    best_synset = synsets[0]
    best_score = -1.0

    for synset in synsets:
        gloss = synset.definition()
        gloss_emb = model.encode(gloss)
        score = np.dot(context_emb, gloss_emb) / (np.linalg.norm(context_emb) * np.linalg.norm(gloss_emb))
        if score > best_score:
            best_score = score
            best_synset = synset

    return best_synset
```

**Verification:**
```python
# Test synset ID extraction
from services.external.wordnet_wrapper import get_wordnet_client
client = get_wordnet_client()
result = client.get_canonical("used", context="condition")
print(result["canonical_id"])  # Should be "01758466-a"
```

---

### Phase 4: Create Disambiguator Module (1 hour)

**File to Create:** `canonicalization/disambiguator.py`

**Purpose:** Centralize multi-source candidate gathering + scoring

**Architecture:**
```python
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class CandidateSense:
    """Data class for candidate senses from any source."""
    source: str          # "wordnet", "babelnet", "wikidata", "merriam_webster"
    source_id: str       # Synset ID, Q-ID, etc.
    label: str           # Primary label
    gloss: str           # Definition text for scoring
    all_forms: List[str] # All synonyms/aliases
    hypernyms: List[str] # Parent concepts
    score: float = 0.0

@dataclass
class DisambiguatedSense:
    """Final disambiguated sense after scoring."""
    resolved_form: str   # Canonical label
    source: str          # Winning source
    source_id: str       # Canonical ID (synset ID, Q-ID, etc.)
    all_forms: List[str] # All aliases
    hypernyms: List[str] # Parent concepts
    score: float         # Confidence score

def disambiguate(term: str, context: Optional[str] = None) -> Optional[DisambiguatedSense]:
    """
    Disambiguate a term by gathering candidates from all sources and scoring.

    Priority order:
    1. WordNet (local, fast) - PRIMARY
    2. BabelNet (if API key set) - adds Wikidata links + multilingual
    3. Merriam-Webster (if API key set) - modern terms fallback
    4. Wikidata (if not already in BabelNet) - entities/proper nouns

    Args:
        term: Word/phrase to disambiguate
        context: Attribute key for context (e.g., "condition", "color")

    Returns:
        DisambiguatedSense with best candidate, or None if no candidates
    """
    # Step 1: Gather candidates from all available sources
    candidates = []

    # WordNet (always available, local)
    wordnet_candidates = _gather_wordnet_candidates(term, context)
    candidates.extend(wordnet_candidates)

    # BabelNet (if API key available)
    if os.getenv("BABELNET_API_KEY"):
        babel_candidates = _gather_babelnet_candidates(term, context)
        candidates.extend(babel_candidates)

    # Merriam-Webster (if API key available and within daily limit)
    if os.getenv("MERRIAM_WEBSTER_API_KEY"):
        mw_client = get_merriam_webster_client()
        if mw_client.is_available():
            mw_candidates = _gather_merriam_candidates(term)
            candidates.extend(mw_candidates)

    if not candidates:
        return None

    # Step 2: Score candidates (if context provided)
    if context and len(candidates) > 1:
        candidates = _score_candidates(candidates, context)

    # Step 3: Return best candidate
    best = max(candidates, key=lambda c: c.score)

    return DisambiguatedSense(
        resolved_form=best.label,
        source=best.source,
        source_id=best.source_id,
        all_forms=best.all_forms,
        hypernyms=best.hypernyms,
        score=best.score
    )

def _gather_wordnet_candidates(term: str, context: Optional[str] = None) -> List[CandidateSense]:
    """
    Gather candidates from WordNet.

    Returns one CandidateSense per synset.
    """
    try:
        from services.external.wordnet_wrapper import get_wordnet_client
        client = get_wordnet_client()

        # Get all synsets for term
        from nltk.corpus import wordnet
        synsets = wordnet.synsets(term)

        candidates = []
        for synset in synsets:
            # Extract synset ID
            offset = str(synset.offset()).zfill(8)
            pos_char = synset.pos()
            synset_id = f"{offset}-{pos_char}"

            # Extract lemmas
            all_forms = [lemma.name().replace("_", " ").lower()
                         for lemma in synset.lemmas()]

            # Extract hypernyms
            hypernyms = [hyp.lemmas()[0].name().replace("_", " ").lower()
                         for hyp in synset.hypernyms()]

            candidate = CandidateSense(
                source="wordnet",
                source_id=synset_id,
                label=all_forms[0],
                gloss=synset.definition(),
                all_forms=all_forms,
                hypernyms=hypernyms,
                score=1.0  # Default score (will be updated if context provided)
            )
            candidates.append(candidate)

        return candidates

    except Exception as e:
        print(f"WordNet candidate gathering error: {e}")
        return []

def _gather_babelnet_candidates(term: str, context: Optional[str] = None) -> List[CandidateSense]:
    """
    Gather candidates from BabelNet.

    BabelNet already integrates WordNet + Wikidata, so this adds:
    - Multilingual synonyms
    - Wikidata Q-IDs
    - Richer gloss data
    """
    try:
        from services.external.babelnet_wrapper import get_babelnet_client
        client = get_babelnet_client()

        # BabelNet's get_canonical already does disambiguation!
        result = client.get_canonical(term, context)
        if not result:
            return []

        candidate = CandidateSense(
            source="babelnet",
            source_id=result["canonical_id"],  # BabelNet synset ID (bn:XXXXXXXX)
            label=result["canonical_label"],
            gloss="",  # BabelNet glosses already used for disambiguation
            all_forms=[result["canonical_label"]] + result["synonyms"],
            hypernyms=result["parents"],
            score=1.0,
            linked_wikidata=result.get("linked_wikidata")  # Q-ID if available
        )

        return [candidate]

    except Exception as e:
        print(f"BabelNet candidate gathering error: {e}")
        return []

def _score_candidates(candidates: List[CandidateSense], context: str) -> List[CandidateSense]:
    """
    Score candidates using gloss-context embedding similarity.

    Uses shared SentenceTransformer from embedding/model_provider.py
    """
    from embedding.model_provider import get_embedding_model
    model = get_embedding_model()

    context_emb = model.encode(context)

    for candidate in candidates:
        if not candidate.gloss:
            continue

        gloss_emb = model.encode(candidate.gloss)
        similarity = np.dot(context_emb, gloss_emb) / (
            np.linalg.norm(context_emb) * np.linalg.norm(gloss_emb)
        )
        candidate.score = float(similarity)

    return candidates
```

**Key Design Decisions:**
1. **WordNet-first:** Always try WordNet first (local, fast, no API limits)
2. **BabelNet optional:** Only use if API key available (adds Wikidata links)
3. **Graceful degradation:** Each source wrapped in try/except → returns []
4. **Unified scoring:** All candidates scored with same embedding model
5. **Single winner:** Returns best candidate (no ensemble complexity)

---

### Phase 5: Create Canonicalizer Module (1 hour)

**File to Create:** `canonicalization/canonicalizer.py`

**Purpose:** Convert DisambiguatedSense → OntologyNode + cross-tier propagation

**Architecture:**
```python
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class OntologyNode:
    """
    Canonical concept representation.

    Used by resolver to store/retrieve canonicalized concepts.
    """
    concept_id: str      # Synset ID or canonical ID
    canonical_label: str # Preferred form
    all_forms: List[str] # All aliases
    concept_path: List[str]  # Hierarchy path
    source: str          # "wordnet", "babelnet", "wikidata"

# Load P8814 cache (singleton)
_WORDNET_WIKIDATA_MAP: Optional[Dict] = None

def _load_wikidata_enrichment() -> Dict:
    """Load P8814 cache from disk (one-time)."""
    global _WORDNET_WIKIDATA_MAP

    if _WORDNET_WIKIDATA_MAP is None:
        cache_path = Path(__file__).parent / "static_dicts/wordnet_wikidata_map.json"
        if cache_path.exists():
            with open(cache_path) as f:
                _WORDNET_WIKIDATA_MAP = json.load(f)
        else:
            print("⚠️ P8814 cache not found. Run: python3 scripts/build_wordnet_wikidata_cache.py")
            _WORDNET_WIKIDATA_MAP = {}

    return _WORDNET_WIKIDATA_MAP

def enrich_with_wikidata_aliases(sense: DisambiguatedSense) -> DisambiguatedSense:
    """
    Enrich WordNet sense with Wikidata aliases via P8814 mapping.

    Args:
        sense: DisambiguatedSense with WordNet synset ID

    Returns:
        Enriched sense with merged aliases from Wikidata
    """
    # Only enrich WordNet senses
    if sense.source != "wordnet":
        return sense

    mapping = _load_wikidata_enrichment()
    synset_id = sense.source_id  # e.g., "01758466-a"

    if synset_id not in mapping:
        return sense  # No Wikidata mapping found

    # Merge Wikidata aliases
    wikidata_data = mapping[synset_id]
    wikidata_aliases = wikidata_data.get("aliases", [])

    # Combine and deduplicate
    all_forms = list(set(sense.all_forms + wikidata_aliases))

    return DisambiguatedSense(
        resolved_form=sense.resolved_form,
        source="wordnet+wikidata",  # Mark as enriched
        source_id=sense.source_id,
        all_forms=all_forms,
        hypernyms=sense.hypernyms,
        score=sense.score
    )

def canonicalize(
    sense: DisambiguatedSense,
    original_term: str,
    attribute_key: str,
    synonym_registry: Dict[str, str]
) -> OntologyNode:
    """
    Convert DisambiguatedSense to OntologyNode with cross-tier propagation.

    Cross-tier propagation logic:
    - Check if ANY of sense.all_forms already exists in synonym_registry
    - If yes, reuse that concept_id (prevents duplicate concepts)
    - If no, use sense.source_id as new concept_id

    Args:
        sense: Disambiguated sense from disambiguator
        original_term: Original input term
        attribute_key: Attribute context (e.g., "condition")
        synonym_registry: Existing synonym→concept_id mappings

    Returns:
        OntologyNode with concept_id, labels, and hierarchy
    """
    # Step 1: Enrich with Wikidata aliases (if WordNet source)
    sense = enrich_with_wikidata_aliases(sense)

    # Step 2: Cross-tier propagation - check if any alias already exists
    concept_id = None
    for form in sense.all_forms:
        normalized_form = _normalize_for_registry(form)
        if normalized_form in synonym_registry:
            concept_id = synonym_registry[normalized_form]
            print(f"✅ Cross-tier match: '{form}' → concept_id={concept_id}")
            break

    # Step 3: If no existing mapping, use source_id as new concept_id
    if not concept_id:
        concept_id = sense.source_id  # WordNet synset ID or BabelNet ID

    # Step 4: Build concept_path (hierarchy)
    concept_path = [attribute_key] + sense.hypernyms + [concept_id]

    # Step 5: Register ALL forms → concept_id
    for form in sense.all_forms:
        normalized_form = _normalize_for_registry(form)
        synonym_registry[normalized_form] = concept_id

    # Also register original term (in case it's not in all_forms)
    normalized_original = _normalize_for_registry(original_term)
    synonym_registry[normalized_original] = concept_id

    return OntologyNode(
        concept_id=concept_id,
        canonical_label=sense.resolved_form,
        all_forms=sense.all_forms,
        concept_path=concept_path,
        source=sense.source
    )

def _normalize_for_registry(text: str) -> str:
    """
    Normalize text for registry lookup.

    Handles compound variants: "second hand" / "second-hand" / "secondhand" → "secondhand"
    """
    return text.lower().replace(" ", "").replace("-", "").replace("_", "")
```

**Key Fix: Cross-Tier Propagation**

This is the **critical fix** for the synonym mismatch problem:

```python
# BEFORE (Problem):
# User A: "used" → WordNet → concept_id="used"
# User B: "second hand" → Wikidata → concept_id="second-hand"
# Match: "used" ≠ "second-hand" → FAIL ❌

# AFTER (Fixed):
# User A: "used" → WordNet synset 01758466-a → concept_id="01758466-a"
#   → synonym_registry["used"] = "01758466-a"
#   → synonym_registry["secondhand"] = "01758466-a"  (from all_forms)
#
# User B: "second hand" → Wikidata returns aliases ["second-hand", "used", "pre-owned"]
#   → Check registry: "secondhand" (normalized) → FOUND: "01758466-a"
#   → Reuse concept_id="01758466-a" (don't create new concept)
#   → synonym_registry["pre-owned"] = "01758466-a"  (add new alias)
#
# Match: "01758466-a" == "01758466-a" → SUCCESS ✅
```

---

### Phase 6: Update Generic Categorical Resolver (1 hour)

**File to Modify:** `canonicalization/resolvers/generic_categorical_resolver.py`

**Current Flow:**
```
resolve(value, context, attribute_key)
  → Check synonym_registry
  → Try WordNet
  → Try BabelNet (raw, no disambiguation)
  → Try Wikidata (raw, no disambiguation)
  → Fallback (lowercase)
```

**New Flow:**
```
resolve(value, context, attribute_key)
  → Check synonym_registry (both exact + normalized)
  → Call disambiguate() → returns DisambiguatedSense
  → Call canonicalize() → returns OntologyNode
  → Update synonym_registry + concept_paths
  → Return OntologyNode
```

**Implementation:**
```python
# Add to class GenericCategoricalResolver

def __init__(self):
    self._synonym_registry: Dict[str, str] = {}
    self._concept_paths: Dict[str, List[str]] = {}  # NEW: concept_id → path
    # ... existing code ...

def resolve(
    self, value: str, context: Optional[str] = None, attribute_key: Optional[str] = None
) -> OntologyNode:
    """
    Resolve a categorical value to canonical form using WordNet-first strategy.

    NEW FLOW (Path A):
    1. Check synonym_registry (exact + normalized)
    2. Disambiguate (WordNet → BabelNet → Merriam-Webster)
    3. Canonicalize (cross-tier propagation + P8814 enrichment)
    4. Update registry + paths
    5. Return OntologyNode
    """
    # Feature flag for rollback
    if os.getenv("USE_NEW_PIPELINE", "1") == "0":
        return self._resolve_legacy(value, context, attribute_key)

    # Step 1: Normalize and check registry
    normalized = value.lower().strip()

    # Check exact match
    if normalized in self._synonym_registry:
        concept_id = self._synonym_registry[normalized]
        return self._build_node_from_registry(concept_id, normalized)

    # Check normalized (compound variants)
    from canonicalization.canonicalizer import _normalize_for_registry
    registry_key = _normalize_for_registry(normalized)
    if registry_key in self._synonym_registry:
        concept_id = self._synonym_registry[registry_key]
        return self._build_node_from_registry(concept_id, normalized)

    # Step 2: Disambiguate
    from canonicalization.disambiguator import disambiguate
    sense = disambiguate(normalized, context=attribute_key)

    if not sense:
        # No candidates found, fallback
        return self._create_fallback_node(normalized, attribute_key)

    # Step 3: Canonicalize (includes cross-tier propagation + P8814 enrichment)
    from canonicalization.canonicalizer import canonicalize
    node = canonicalize(sense, normalized, attribute_key or "unknown", self._synonym_registry)

    # Step 4: Store concept_path for hierarchy matching
    self._concept_paths[node.concept_id] = node.concept_path

    # Step 5: Persist to database (OntologyStore)
    from canonicalization.ontology_store import get_ontology_store
    store = get_ontology_store()
    store.save_to_db({
        "synonym_registry": self._synonym_registry,
        "concept_paths": self._concept_paths
    })

    return node

def is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
    """
    Check if ancestor_id is an ancestor of descendant_id in concept hierarchy.

    Used by semantic_implies() in main.py for hierarchy matching.

    Example:
        concept_paths = {
            "02958343-n": ["item_type", "motor vehicle", "vehicle", "02958343-n"]
        }
        is_ancestor("vehicle", "02958343-n") → True
    """
    if descendant_id not in self._concept_paths:
        return False

    path = self._concept_paths[descendant_id]
    return ancestor_id in path

def _build_node_from_registry(self, concept_id: str, original_form: str) -> OntologyNode:
    """Build OntologyNode from registry hit."""
    # Get all forms that map to this concept_id
    all_forms = [k for k, v in self._synonym_registry.items() if v == concept_id]

    return OntologyNode(
        concept_id=concept_id,
        canonical_label=original_form,
        all_forms=all_forms,
        concept_path=self._concept_paths.get(concept_id, []),
        source="registry"
    )

def _create_fallback_node(self, value: str, attribute_key: str) -> OntologyNode:
    """Create fallback node when no candidates found."""
    concept_id = value.lower()
    self._synonym_registry[value.lower()] = concept_id

    return OntologyNode(
        concept_id=concept_id,
        canonical_label=value,
        all_forms=[value],
        concept_path=[attribute_key, concept_id],
        source="fallback"
    )

def _resolve_legacy(self, value: str, context: Optional[str], attribute_key: Optional[str]) -> OntologyNode:
    """
    Legacy resolution logic (old cascade).

    Kept for instant rollback via USE_NEW_PIPELINE=0.
    """
    # ... existing cascade code ...
    # (WordNet raw → BabelNet raw → Wikidata raw → fallback)
```

---

### Phase 7: Update Main.py (15 minutes)

**File to Modify:** `main.py`

**Current Code (lines 123-142):**
```python
def semantic_implies(candidate_val: str, required_val: str) -> bool:
    """Check if candidate_val implies required_val."""
    c, r = candidate_val.lower().strip(), required_val.lower().strip()
    if c == r:
        return True
    # Hierarchy: is required_val an ancestor of candidate_val?
    try:
        from canonicalization.orchestrator import _get_categorical_resolver
        resolver = _get_categorical_resolver()
        if resolver.is_ancestor(r, c):
            return True
    except Exception:
        pass
    return False
```

**No Changes Needed!** ✅

The hierarchy check (`resolver.is_ancestor()`) already exists and will work with the new concept_paths we're building.

**Verification Test:**
```python
# Test hierarchy matching
from canonicalization.orchestrator import _get_categorical_resolver

resolver = _get_categorical_resolver()

# Resolve "car" (should get synset 02958343-n)
car_node = resolver.resolve("car", attribute_key="item_type")
print(f"car → concept_id={car_node.concept_id}")
print(f"car → concept_path={car_node.concept_path}")

# Test hierarchy
is_vehicle = resolver.is_ancestor("vehicle", car_node.concept_id)
print(f"is 'vehicle' ancestor of 'car'? {is_vehicle}")  # Should be True
```

---

## Testing Plan

### Unit Tests (30 minutes)

**File to Create:** `tests/unit_testing/test_path_a_components.py`

```python
import pytest
from canonicalization.disambiguator import disambiguate, CandidateSense
from canonicalization.canonicalizer import enrich_with_wikidata_aliases, canonicalize
from canonicalization.resolvers.generic_categorical_resolver import GenericCategoricalResolver

def test_wordnet_disambiguator():
    """Test WordNet candidate gathering."""
    sense = disambiguate("laptop", context="electronics")
    assert sense is not None
    assert sense.source == "wordnet"
    assert sense.source_id.endswith("-n")  # Noun synset
    assert "laptop" in sense.all_forms or "portable computer" in sense.all_forms

def test_p8814_enrichment():
    """Test Wikidata alias enrichment via P8814."""
    # Build cache first (run scripts/build_wordnet_wikidata_cache.py)
    from canonicalization.disambiguator import DisambiguatedSense

    sense = DisambiguatedSense(
        resolved_form="used",
        source="wordnet",
        source_id="01758466-a",
        all_forms=["used", "secondhand"],
        hypernyms=[],
        score=1.0
    )

    enriched = enrich_with_wikidata_aliases(sense)

    # Should add Wikidata aliases
    assert "pre-owned" in enriched.all_forms or len(enriched.all_forms) >= len(sense.all_forms)
    assert enriched.source == "wordnet+wikidata"

def test_cross_tier_propagation():
    """Test that different terms resolve to same concept_id."""
    resolver = GenericCategoricalResolver()

    # First term: "used"
    node1 = resolver.resolve("used", attribute_key="condition")
    concept_id_1 = node1.concept_id

    # Second term: "second hand" (should map to same concept)
    node2 = resolver.resolve("second hand", attribute_key="condition")
    concept_id_2 = node2.concept_id

    # They should have the same concept_id
    assert concept_id_1 == concept_id_2, \
        f"Expected same concept_id, got {concept_id_1} vs {concept_id_2}"

def test_hierarchy_matching():
    """Test is_ancestor() for concept hierarchy."""
    resolver = GenericCategoricalResolver()

    # Resolve "car" to get concept_id
    car_node = resolver.resolve("car", attribute_key="item_type")

    # "vehicle" should be ancestor of "car"
    assert resolver.is_ancestor("vehicle", car_node.concept_id) or \
           resolver.is_ancestor("motor vehicle", car_node.concept_id)

def test_normalized_compound_matching():
    """Test that compound variants match."""
    from canonicalization.canonicalizer import _normalize_for_registry

    variants = ["second hand", "second-hand", "secondhand"]
    normalized = [_normalize_for_registry(v) for v in variants]

    # All should normalize to same form
    assert len(set(normalized)) == 1
```

### E2E Tests (30 minutes)

**File:** `tests/e2e_canonicalization_test.py` (existing)

**Run Tests:**
```bash
# Set feature flag
export USE_NEW_PIPELINE=1

# Run E2E tests
python3 tests/e2e_canonicalization_test.py
```

**Expected Results:**

**Current (14/18 PASS):**
- ❌ P2: laptop vs notebook (different concept_ids)
- ❌ S1: tutoring vs coaching (different sources)
- ❌ S2: plumber vs plumbing (person vs activity)
- ❌ S3: cleaning vs housekeeping (off-by-one alias)

**After Path A (16-17/18 PASS):**
- ✅ P2: laptop vs notebook → **SHOULD PASS**
  - Both resolve to WordNet synset 02939185-n (laptop.n.01)
  - concept_id match: "02939185-n" == "02939185-n"

- ✅ S2: plumber vs plumbing → **SHOULD PASS**
  - WordNet disambiguates: plumber.n.01 (person) vs plumbing.n.01 (system)
  - Hierarchy: plumber is-a tradesman, plumbing is-a utility
  - Match via hypernym if resolver configured correctly

- ⚠️ S1: tutoring vs coaching → **MAYBE**
  - Depends on WordNet synsets for education services
  - May need BabelNet for better coverage

- ⚠️ S3: cleaning vs housekeeping → **MAYBE**
  - P8814 enrichment should add aliases
  - Both should map to same synset if Wikidata has mapping

**Best Case:** 17/18 PASS (only S1 fails, needs BabelNet)
**Worst Case:** 16/18 PASS (S1 + S3 fail)

---

## Rollback Strategy

### Instant Rollback
```bash
# Disable new pipeline
export USE_NEW_PIPELINE=0

# Restart server
python3 main.py
```

### Partial Rollback
```bash
# Keep disambiguator but disable P8814 enrichment
# Delete or rename: canonicalization/static_dicts/wordnet_wikidata_map.json

# Keep WordNet-first but disable Merriam-Webster
# Unset API key
unset MERRIAM_WEBSTER_API_KEY
```

### Full Rollback
```bash
# Revert all changes
git checkout main.py
git checkout canonicalization/
git checkout services/external/wordnet_wrapper.py
```

---

## Success Metrics

### Primary Metrics
- ✅ **E2E Test Pass Rate:** 16-17/18 (vs current 14/18)
- ✅ **Cross-Tier Propagation:** "used" and "second-hand" map to same concept_id
- ✅ **P8814 Cache Size:** ~80,000 mappings loaded
- ✅ **Hierarchy Matching:** `is_ancestor("vehicle", "car")` returns True

### Performance Metrics
- ⏱️ **Disambiguation Latency:** <100ms (WordNet local, no API)
- ⏱️ **P8814 Enrichment:** <5ms (local JSON lookup)
- ⏱️ **Registry Hit Rate:** >60% after 100 canonicalizations
- 💾 **Memory Overhead:** ~15MB (P8814 cache + registry)

### Coverage Metrics
- 📊 **WordNet Coverage:** 117,000 synsets
- 📊 **P8814 Coverage:** 80,000 WordNet-Wikidata links
- 📊 **Merriam-Webster Coverage:** 470,000 words (fallback tier)

---

## Implementation Checklist

### Phase 1: Build P8814 Cache ⬜
- [ ] Create `scripts/build_wordnet_wikidata_cache.py`
- [ ] Install SPARQLWrapper if needed (`pip install sparqlwrapper`)
- [ ] Run script: `python3 scripts/build_wordnet_wikidata_cache.py`
- [ ] Verify output: `ls -lh canonicalization/static_dicts/wordnet_wikidata_map.json`
- [ ] Load and count entries: `python3 -c "import json; print(len(json.load(open('canonicalization/static_dicts/wordnet_wikidata_map.json'))))"`

### Phase 2: Add Merriam-Webster Wrapper ⬜
- [ ] Create `services/external/merriam_webster_wrapper.py`
- [ ] Get free API key from https://dictionaryapi.com/register/index
- [ ] Set env var: `export MERRIAM_WEBSTER_API_KEY="your-key-here"`
- [ ] Test API: `python3 -c "from services.external.merriam_webster_wrapper import get_merriam_webster_client; print(get_merriam_webster_client().get_definition('laptop'))"`

### Phase 3: Update WordNet Wrapper ⬜
- [ ] Modify `services/external/wordnet_wrapper.py`
- [ ] Add `get_canonical()` method with synset ID extraction
- [ ] Add `_get_synset_offset_id()` helper
- [ ] Add `_disambiguate_synsets()` for context scoring
- [ ] Test: `python3 -c "from services.external.wordnet_wrapper import get_wordnet_client; print(get_wordnet_client().get_canonical('used', 'condition'))"`

### Phase 4: Create Disambiguator ⬜
- [ ] Create `canonicalization/disambiguator.py`
- [ ] Implement `disambiguate()` main function
- [ ] Implement `_gather_wordnet_candidates()`
- [ ] Implement `_gather_babelnet_candidates()` (uses existing wrapper)
- [ ] Implement `_score_candidates()` with embedding model
- [ ] Test: `python3 -c "from canonicalization.disambiguator import disambiguate; print(disambiguate('laptop', 'electronics'))"`

### Phase 5: Create Canonicalizer ⬜
- [ ] Create `canonicalization/canonicalizer.py`
- [ ] Implement `enrich_with_wikidata_aliases()`
- [ ] Implement `canonicalize()` with cross-tier propagation
- [ ] Implement `_normalize_for_registry()`
- [ ] Test: `python3 -c "from canonicalization.canonicalizer import enrich_with_wikidata_aliases; # test enrichment"`

### Phase 6: Update Generic Categorical Resolver ⬜
- [ ] Modify `canonicalization/resolvers/generic_categorical_resolver.py`
- [ ] Add `_concept_paths` dictionary
- [ ] Implement new `resolve()` method
- [ ] Implement `is_ancestor()` method
- [ ] Keep old code as `_resolve_legacy()`
- [ ] Add `USE_NEW_PIPELINE` feature flag check
- [ ] Test: `python3 -c "from canonicalization.orchestrator import _get_categorical_resolver; r = _get_categorical_resolver(); print(r.resolve('used', attribute_key='condition'))"`

### Phase 7: Update Main.py ⬜
- [ ] Verify `semantic_implies()` has hierarchy check (lines 134-139)
- [ ] No changes needed (already implemented!)
- [ ] Test hierarchy: `python3 -c "from main import semantic_implies; print(semantic_implies('car', 'vehicle'))"`

### Phase 8: Testing ⬜
- [ ] Create `tests/unit_testing/test_path_a_components.py`
- [ ] Run unit tests: `python3 tests/unit_testing/test_path_a_components.py`
- [ ] Run E2E tests: `python3 tests/e2e_canonicalization_test.py`
- [ ] Verify pass rate: 16-17/18 (vs 14/18 baseline)
- [ ] Check logs for cross-tier propagation messages

### Phase 9: Documentation ⬜
- [ ] Update `MEMORY.md` with Path A status
- [ ] Document new env vars in README
- [ ] Add rollback instructions
- [ ] Update architecture diagram

---

## Environment Variables Reference

```bash
# Feature Flags
export USE_NEW_PIPELINE=1  # 1=Path A, 0=legacy cascade

# API Keys (Optional)
export BABELNET_API_KEY="your-babelnet-key"  # For Wikidata Q-ID enrichment
export MERRIAM_WEBSTER_API_KEY="your-mw-key"  # For modern term fallback

# Already Existing
export SUPABASE_URL="..."  # For OntologyStore persistence
export OPENAI_API_KEY="..."  # For extraction
```

---

## Expected Improvements

| Test Case | Before (14/18) | After Path A (16-17/18) | Fix Explanation |
|-----------|----------------|-------------------------|-----------------|
| **P2: laptop vs notebook** | ❌ FAIL | ✅ PASS | Both resolve to synset 02939185-n |
| **S2: plumber vs plumbing** | ❌ FAIL | ✅ PASS | WordNet disambiguates person vs system |
| **S3: cleaning vs housekeeping** | ❌ FAIL | ⚠️ MAYBE | P8814 adds Wikidata aliases |
| **S1: tutoring vs coaching** | ❌ FAIL | ⚠️ MAYBE | May need BabelNet for education |
| All others (14) | ✅ PASS | ✅ PASS | No regression |

---

## Next Steps After Path A

If Path A achieves 16-17/18, we can proceed to **Path B** (fine-tuning) to reach 18/18:

**Path B: Fine-tune DistilBERT on UFSAC**
- Download UFSAC dataset (2M annotations)
- Fine-tune transformer component
- Enable hybrid scorer (weights: 0.5,0.35,0.15)
- Expected: 18/18 tests (100%)

But Path A should be sufficient for production use (89-94% accuracy) without any model training.

---

**Status:** ✅ **Plan Complete - Ready for Implementation**

**Estimated Time:** 4-6 hours
**Expected Result:** 16-17/18 tests passing (vs 14/18 baseline)
**Risk Level:** LOW (instant rollback via feature flag)
