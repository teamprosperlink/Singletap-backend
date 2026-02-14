# Singletap Backend - Developer Documentation

## Overview

**Singletap** is a semantic matching engine that connects buyers with sellers, service seekers with providers, and mutual interest parties. It uses NLP, knowledge graphs, and vector embeddings to match listings based on semantic understanding rather than exact keyword matching.

---

## Technology Stack

### Core Framework
| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | Latest | REST API framework (async support) |
| **Uvicorn** | Latest | ASGI server |
| **Pydantic** | Latest | Data validation and settings management |
| **Python** | 3.10+ | Runtime |

### AI/ML Libraries
| Library | Purpose |
|---------|---------|
| **OpenAI API** | GPT-4o for natural language extraction |
| **sentence-transformers** | Semantic embeddings (all-MiniLM-L6-v2) |
| **transformers** | Hugging Face transformers |
| **torch** | PyTorch (CPU version) |
| **scikit-learn** | ML utilities |
| **numpy** | Numerical computing |

### NLP & Knowledge Graphs
| Library/API | Purpose |
|-------------|---------|
| **NLTK** | WordNet access, lemmatization, derivational forms |
| **BabelNet API** | Multilingual synonyms, hypernyms (1000 req/day free) |
| **Wikidata API** | Entity disambiguation, hierarchy paths |
| **Datamuse API** | Synonym lookup (100K/day free, no key) |
| **WordsAPI** | Definitions with grouped synonyms (2500/day free) |

### Quantitative Processing
| Library | Purpose |
|---------|---------|
| **Quantulum3** | Parse quantities from text ("5 kg", "100 miles") |
| **Pint** | Unit normalization and conversion |

### Database & Vector Storage
| Service | Purpose |
|---------|---------|
| **Supabase (PostgreSQL)** | Primary database for listings, matches |
| **Qdrant Cloud** | Vector database for semantic search |

### External Services
| Service | Purpose |
|---------|---------|
| **Nominatim (OpenStreetMap)** | Geocoding for location canonicalization |
| **Currency Exchange API** | Currency code validation |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
│                    "need a plumber who speaks kannada"                       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: GPT EXTRACTION                               │
│                                                                              │
│  OpenAI GPT-4o + GLOBAL_REFERENCE_CONTEXT.md prompt                         │
│  Output: NEW Schema (14 fields, axis-based structure)                       │
│                                                                              │
│  {                                                                           │
│    "intent": "service",                                                      │
│    "subintent": "seek",                                                      │
│    "domain": ["construction & trades"],                                      │
│    "items": [{"type": "plumbing", "categorical": {...}}],                    │
│    "other_party_preferences": {"categorical": {"language": "kannada"}}       │
│  }                                                                           │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 2: CANONICALIZATION                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ Phase 0: PREPROCESS (static dicts, instant)                  │           │
│  │   lowercase → lemmatize → expand abbreviations →             │           │
│  │   reduce MWEs → normalize spelling → normalize demonyms      │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                                 │                                            │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ Phase 1: DISAMBIGUATE (multi-source, embedding scoring)      │           │
│  │                                                               │           │
│  │   Gather candidates from ALL 5 sources simultaneously:       │           │
│  │   ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────┐│           │
│  │   │ WordNet │ │ WordsAPI │ │ Datamuse │ │ Wikidata │ │BNet ││           │
│  │   │ (local) │ │  (API)   │ │  (API)   │ │  (API)   │ │(opt)││           │
│  │   └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬──┘│           │
│  │        │           │            │            │          │    │           │
│  │        └───────────┴────────────┴────────────┴──────────┘    │           │
│  │                              │                                │           │
│  │                              ▼                                │           │
│  │        Score ALL glosses via SentenceTransformer cosine      │           │
│  │        Pick best candidate above threshold (0.15)            │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                                 │                                            │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ Phase 2: CANONICALIZE (registry + label extraction)          │           │
│  │                                                               │           │
│  │   Cross-tier propagation: check all_forms against registry   │           │
│  │   Extract canonical label → build concept_path               │           │
│  │   Register ALL forms → concept_id in synonym_registry        │           │
│  │                                                               │           │
│  │   Output: OntologyNode with concept_id, concept_path, etc.   │           │
│  └──────────────────────────────────────────────────────────────┘           │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 3: SCHEMA NORMALIZATION                           │
│                                                                              │
│  Transform NEW schema (14 fields) → OLD schema (flat format)                │
│  - Field renames: other_party_preferences → other                           │
│  - Axis flattening: min/max/range constraints                               │
│  - Location normalization with geocoding                                     │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 4: MATCHING                                     │
│                                                                              │
│  Boolean matching with semantic implication:                                 │
│                                                                              │
│  1. Intent Gate (M-01 to M-04)                                              │
│     - Intent equality: A.intent == B.intent                                 │
│     - SubIntent inverse (product/service): buy ↔ sell                       │
│     - SubIntent same (mutual): connect == connect                           │
│                                                                              │
│  2. Domain/Category Gate (M-05, M-06)                                       │
│     - Domain intersection: A.domain ∩ B.domain ≠ ∅                          │
│                                                                              │
│  3. Items Matching (M-07 to M-12)                                           │
│     - Type matching with semantic_implies()                                 │
│     - Categorical attribute matching                                         │
│     - Numeric constraint satisfaction                                        │
│                                                                              │
│  4. Other→Self Constraints (M-13 to M-17)                                   │
│     - A.other_party_preferences vs B.self_attributes                        │
│                                                                              │
│  5. Location Matching (M-23 to M-28)                                        │
│     - Mode-based: near_me, explicit, global, route                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
Singletap-backend/
│
├── main.py                          # FastAPI app, endpoints, semantic_implies()
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (API keys)
│
├── prompt/
│   └── GLOBAL_REFERENCE_CONTEXT.md  # GPT extraction prompt
│
├── canonicalization/                # Phase 2: Semantic Resolution
│   ├── orchestrator.py              # Main entry: canonicalize_listing()
│   ├── preprocessor.py              # Phase 0: Static text normalization
│   ├── disambiguator.py             # Phase 1: Multi-source disambiguation
│   ├── canonicalizer.py             # Phase 2: Cross-tier propagation
│   ├── ontology_store.py            # DB persistence for ontology
│   ├── hybrid_scorer.py             # Experimental 3-model ensemble
│   ├── llm_fallback.py              # GPT fallback for edge cases
│   ├── resolvers/
│   │   ├── generic_categorical_resolver.py  # Main resolver class
│   │   └── quantitative_resolver.py         # Numeric unit normalization
│   └── static_dicts/                # Static dictionaries
│       ├── abbreviations.py         # AC→air conditioning, TV→television
│       ├── mwe_reductions.py        # "barely used"→"used"
│       ├── spelling_variants.py     # colour→color, grey→gray
│       └── demonyms.py              # indian→india, french→france
│
├── schema/
│   └── schema_normalizer_v2.py      # NEW→OLD schema transformation
│
├── matching/                        # Phase 4: Boolean Matching
│   ├── listing_matcher_v2.py        # Main: listing_matches_v2()
│   ├── item_matchers.py             # Item type/categorical matching
│   ├── item_array_matchers.py       # Multi-item array matching
│   ├── other_self_matchers.py       # Other→Self constraint matching
│   ├── location_matcher_v2.py       # Location mode matching
│   └── numeric_constraints.py       # Min/max/range matching
│
├── services/external/               # External API Wrappers
│   ├── wordnet_wrapper.py           # NLTK WordNet (local)
│   ├── babelnet_wrapper.py          # BabelNet API
│   ├── wikidata_wrapper.py          # Wikidata SPARQL
│   ├── datamuse_wrapper.py          # Datamuse API
│   ├── wordsapi_wrapper.py          # WordsAPI via RapidAPI
│   ├── geocoding_service.py         # Nominatim geocoding
│   ├── currency_service.py          # Currency validation
│   ├── pint_wrapper.py              # Unit conversion
│   └── quantulum_wrapper.py         # Quantity parsing
│
├── embedding/
│   ├── model_provider.py            # Singleton SentenceTransformer
│   └── embedding_builder.py         # Build embedding text from listing
│
├── pipeline/
│   ├── ingestion_pipeline.py        # Store listing in DB + Qdrant
│   └── retrieval_service.py         # Retrieve candidates from Qdrant
│
└── tests/
    ├── e2e_canonicalization_test.py # 18 E2E tests
    └── robustness_test.py           # 20 additional tests
```

---

## Key Components Explained

### 1. Semantic Implies Function (`main.py:123-223`)

The core matching logic that determines if one term semantically implies another:

```python
def semantic_implies(candidate_val: str, required_val: str) -> bool:
    """
    Check if candidate_val implies required_val.

    Strategies (in order):
    1. Exact match (after canonicalization)
    2. WordNet hierarchy check (is_ancestor)
    3. Morphological matching (common prefix ≥5 chars)
    4. BabelNet synonym word-boundary check
    """
```

**Example matches:**
- `"scarlet"` implies `"red"` (WordNet hierarchy: scarlet IS-A red)
- `"plumber"` implies `"plumbing"` (morphological: "plumb" prefix)
- `"coaching"` implies `"tutoring"` (BabelNet synonyms)

### 2. Generic Categorical Resolver (`canonicalization/resolvers/generic_categorical_resolver.py`)

Resolves any categorical attribute to a canonical concept:

```python
class GenericCategoricalResolver:
    """
    Pipeline (USE_NEW_PIPELINE=1):
      Phase 0: Preprocess → Phase 1: Disambiguate → Phase 2: Canonicalize

    Legacy (USE_NEW_PIPELINE=0):
      synonym_registry → WordNet → BabelNet → Wikidata → fallback
    """

    def resolve(self, value: str, attribute_key: str) -> OntologyNode:
        # Returns concept_id, concept_path, parents, siblings, etc.
```

**Output structure:**
```python
OntologyNode(
    concept_id="used",           # Canonical form
    concept_root="condition",    # Attribute category
    concept_path=["condition", "used"],  # Hierarchy
    parents=["goods"],
    siblings=["second-hand", "pre-owned", "secondhand"],
    source="wordnet",            # Resolution source
    confidence=0.8
)
```

### 3. BabelNet Wrapper (`services/external/babelnet_wrapper.py`)

Provides multilingual synonym and hypernym lookups:

```python
class BabelNetClient:
    """
    Key methods:
    - get_synonyms(term) → ["used", "second-hand", "pre-owned"]
    - get_hypernyms(term) → ["goods", "commodity"]
    - get_disambiguated_synset(term, context) → best synset ID
    - get_canonical(term, context) → {canonical_label, synonyms, parents}
    """
```

**Rate limits:** 1000 requests/day (free tier)

### 4. Listing Matcher V2 (`matching/listing_matcher_v2.py`)

Boolean matching with fixed evaluation order:

```python
def listing_matches_v2(A: Dict, B: Dict, implies_fn) -> bool:
    """
    A = requester (what they want)
    B = candidate (what they offer)

    Evaluation order (MANDATORY):
    1. Intent gate → 2. Domain gate → 3. Items → 4. Other→Self → 5. Location

    Returns True only if ALL constraints satisfied.
    """
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Simple health status |
| `/extract` | POST | Extract JSON from natural language |
| `/extract-and-normalize` | POST | Extract + normalize to OLD schema |
| `/extract-and-match` | POST | Extract two queries and match |
| `/match` | POST | Match two pre-formatted listings |
| `/ingest` | POST | Store listing in DB + Qdrant |
| `/search` | POST | Vector search for candidates |
| `/search-and-match` | POST | Full pipeline: extract→search→match→store |
| `/store-listing` | POST | Store listing for future matching |

---

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...           # GPT-4o extraction
SUPABASE_URL=https://...        # Database
SUPABASE_KEY=eyJ...             # Service role key
QDRANT_ENDPOINT=https://...     # Vector DB
QDRANT_API_KEY=eyJ...           # Qdrant auth

# Knowledge Graph APIs
BABELNET_API_KEY=...            # 1000 req/day free
BABELNET_API_KEY2=...           # Backup key
RAPIDAPI_KEY=...                # For WordsAPI (optional)

# Feature Flags
USE_NEW_PIPELINE=1              # 1=new 3-phase, 0=legacy cascade
USE_HYBRID_SCORER=0             # 0=simple embedding, 1=3-model ensemble

# Optional
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Default embedding model
HF_TOKEN=hf_...                   # Hugging Face (for private models)
```

---

## Data Flow Example

### Query: "I need a used laptop"

1. **GPT Extraction:**
```json
{
  "intent": "product",
  "subintent": "buy",
  "domain": ["electronics"],
  "items": [{
    "type": "laptop",
    "categorical": {"condition": "used"}
  }]
}
```

2. **Canonicalization:**
- `"laptop"` → WordNet → `concept_id: "laptop"`, synonyms: ["notebook", "portable computer"]
- `"used"` → WordNet → `concept_id: "used"`, synonyms: ["second-hand", "pre-owned"]

3. **Synonym Registry (persisted):**
```python
{
  "laptop": "laptop",
  "notebook": "laptop",
  "portable computer": "laptop",
  "used": "used",
  "second-hand": "used",
  "pre-owned": "used"
}
```

4. **Matching against seller listing:**
```json
{
  "intent": "product",
  "subintent": "sell",
  "domain": ["electronics"],
  "items": [{
    "type": "notebook",
    "categorical": {"condition": "second hand"}
  }]
}
```

5. **Match result:** ✅ TRUE
- Intent: product == product ✓
- SubIntent: buy ≠ sell ✓ (inverse required)
- Domain: electronics ∩ electronics ✓
- Type: "laptop" == "laptop" (both canonicalized) ✓
- Condition: "used" == "used" (both canonicalized) ✓

---

## Testing

### Run E2E Tests (18 tests)
```bash
python tests/e2e_canonicalization_test.py
```

### Run Robustness Tests (20 tests)
```bash
python tests/robustness_test.py
```

### Current Test Results
- **E2E Tests:** 18/18 (100%)
- **Robustness Tests:** 16/20 (80%)
- **Combined:** 34/38 (89.5%)

---

## Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| BabelNet down / no key | 4 remaining sources work |
| WordsAPI no RAPIDAPI_KEY | `is_available()=False`, skipped |
| Datamuse 502 | Returns [], skipped |
| Wikidata timeout | Returns [], skipped |
| ALL APIs down | WordNet (local) still works |
| ALL sources fail | Lowercase fallback + log miss |
| `USE_NEW_PIPELINE=0` | Instant rollback to old cascade |

---

## Key Design Decisions

1. **No Hardcoding:** All synonym/hierarchy resolution is dynamic via APIs
2. **Cross-Tier Propagation:** If WordNet registers "used", Wikidata's "second-hand" finds it in registry
3. **Embedding-Based Disambiguation:** Scores glosses against context to pick correct sense
4. **Wu-Palmer Similarity:** For hypernym collapse decisions (threshold > 0.87)
5. **Morphological Matching:** Handles plumber/plumbing via common prefix detection
6. **Feature Flags:** `USE_NEW_PIPELINE` and `USE_HYBRID_SCORER` for instant rollback

---

## Common Issues & Solutions

### Issue: "AC" resolves to "actinium" instead of "air conditioning"
**Solution:** Abbreviation expansion in preprocessor handles this

### Issue: "laptop" and "notebook" don't match
**Solution:** Both canonicalize to same concept_id via WordNet synonyms

### Issue: BabelNet API quota exceeded
**Solution:** Swap to BABELNET_API_KEY2 in .env

### Issue: Slow first request
**Solution:** Embedding model loads on first use (~2-3 seconds). Pre-warm on startup.

---

## Contact & Resources

- **API Documentation:** BabelNet: https://babelnet.io/v9/
- **WordNet:** https://wordnet.princeton.edu/
- **Wikidata SPARQL:** https://query.wikidata.org/
- **Datamuse:** https://www.datamuse.com/api/
