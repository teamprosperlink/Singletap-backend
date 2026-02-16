# **Singletap-Backend Complete Technical Documentation**
### **Vriddhi Matching Engine v2.0**
**Auto-generated | February 16, 2026**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack Overview](#2-technology-stack-overview)
3. [Python Libraries - Complete Reference](#3-python-libraries---complete-reference)
4. [External APIs Used](#4-external-apis-used)
5. [Internal API Endpoints](#5-internal-api-endpoints)
6. [System Architecture](#6-system-architecture)
7. [Core Components Deep Dive](#7-core-components-deep-dive)
8. [Database Architecture](#8-database-architecture)
9. [ML Pipeline](#9-ml-pipeline)
10. [Observability Stack](#10-observability-stack)
11. [Deployment Configuration](#11-deployment-configuration)
12. [Environment Variables](#12-environment-variables)
13. [Data Flow & Algorithms](#13-data-flow--algorithms)
14. [Codebase Discovery Summary](#14-codebase-discovery-summary)
15. [Architecture Diagrams](#15-architecture-diagrams)
16. [Actionable Recommendations](#16-actionable-recommendations)

---

## 1. Executive Summary

**Singletap-Backend** is a semantic matching engine that connects users based on their offerings and requirements. The system uses:

- **Natural Language Processing** to extract structured data from user queries
- **Vector Embeddings** for semantic similarity search
- **Multi-source Ontology Resolution** for synonym/hierarchy matching
- **Boolean Constraint Matching** for precise filtering

### Key Capabilities

| Feature | Technology |
|---------|-----------|
| Query Understanding | GPT-4o (OpenAI) |
| Semantic Search | Sentence-Transformers + Qdrant |
| Data Storage | PostgreSQL (Supabase) |
| Ontology Resolution | Wikidata + WordNet + BabelNet |
| Observability | Sentry + OpenTelemetry/Jaeger |

### Architecture Classification

**This is a Python FastAPI ML Backend because:**
1. `requirements.txt` contains FastAPI, torch, sentence-transformers, OpenAI
2. `main.py` is a FastAPI application with ML-heavy endpoints
3. Uses Qdrant (vector database) for semantic similarity search
4. Uses GPT-4o for natural language → structured schema extraction
5. No frontend code detected - pure API backend

---

## 2. Technology Stack Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         SINGLETAP-BACKEND                        │
├─────────────────────────────────────────────────────────────────┤
│  Language:        Python 3.13+                                   │
│  Framework:       FastAPI + Uvicorn                              │
│  Database:        PostgreSQL (Supabase) + Qdrant (Vector)        │
│  ML Models:       GPT-4o + Sentence-Transformers                 │
│  Deployment:      Docker + Railway/Render                        │
│  Observability:   Sentry + Jaeger (OpenTelemetry)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Python Libraries - Complete Reference

### 3.1 Web Framework & Server

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **fastapi** | Latest | Web framework | High-performance async API framework with automatic OpenAPI docs, type validation via Pydantic, and native async support. Chosen for its speed (comparable to Node.js/Go) and developer experience. |
| **uvicorn[standard]** | Latest | ASGI server | Production-grade ASGI server for FastAPI. The `[standard]` extra includes uvloop and httptools for maximum performance. |
| **pydantic** | Latest | Data validation | Provides runtime type validation for API request/response models. Ensures data integrity at API boundaries. |
| **python-dotenv** | Latest | Environment config | Loads `.env` files into environment variables. Enables local development without modifying system env. |

### 3.2 Database & Storage

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **supabase** | Latest | PostgreSQL client | Official Supabase Python client. Provides PostgreSQL access + real-time subscriptions + auth. Chosen for managed PostgreSQL with built-in REST API. |
| **qdrant-client** | ≥1.16.0 | Vector database | Official Qdrant client for vector similarity search. Supports payload filtering, batch operations, and high-performance nearest-neighbor search. |

**Why Supabase + Qdrant?**
- Supabase: Managed PostgreSQL for structured data (listings, matches, users)
- Qdrant: Specialized vector database for embedding-based semantic search
- This hybrid approach gives us both SQL flexibility and vector search performance

### 3.3 Machine Learning & NLP

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **openai** | Latest | GPT-4o API | Official OpenAI Python client. Used for natural language → structured JSON extraction. GPT-4o provides superior instruction-following for schema extraction. |
| **torch** | CPU build | Deep learning | PyTorch (CPU-only). Required by sentence-transformers for neural network inference. Using CPU build to reduce deployment size and avoid GPU requirements. |
| **sentence-transformers** | Latest | Text embeddings | Generates 384/1024-dimensional embeddings for semantic similarity. Uses transformer models fine-tuned for sentence similarity tasks. |
| **transformers** | ≥4.30.0 | Hugging Face | Core transformer library. Provides model loading, tokenization, and inference for sentence-transformers. |
| **scikit-learn** | ≥1.3.0 | ML utilities | Provides cosine similarity, normalization, and other ML utilities used in embedding comparisons. |
| **numpy** | Latest | Numerical computing | Fundamental array operations for embeddings, distance calculations, and data manipulation. |

**Why This ML Stack?**
```
User Query → GPT-4o (extraction) → Sentence-Transformers (embedding) → Qdrant (search)
```
- GPT-4o: Best-in-class for structured extraction from natural language
- Sentence-Transformers: Pre-trained models specifically optimized for semantic similarity
- The combination provides both understanding (GPT) and retrieval (embeddings)

### 3.4 NLP & Ontology

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **nltk** | Latest | WordNet access | Natural Language Toolkit. Provides local access to WordNet lexical database for synonyms, hypernyms, and semantic relationships. |
| **pint** | Latest | Unit conversion | Physical unit handling library. Converts between units (kg↔lb, km↔miles) for numeric constraint normalization. |
| **quantulum3** | Latest | Quantity extraction | Extracts quantities from text ("256gb" → 256 gigabytes). Uses NER-style parsing for unit detection. |

**Why NLTK + Pint + Quantulum3?**
- NLTK/WordNet: Local synonym/hierarchy lookup (no API calls, instant)
- Pint: Handles all physical unit conversions with dimensional analysis
- Quantulum3: Parses natural language quantities into structured values
- Together they handle: "looking for 16gb ram laptop" → `{memory: 16, unit: "gigabyte"}`

### 3.5 HTTP & Networking

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **requests** | Latest | HTTP client | Simple HTTP client for external API calls (Wikidata, BabelNet, Nominatim). Used by all external service wrappers. |

### 3.6 Observability & Monitoring

| Library | Version | Purpose | Why We Use It |
|---------|---------|---------|---------------|
| **structlog** | ≥25.5.0 | Structured logging | Modern structured logging with JSON output support. Provides contextual logging with emoji indicators for better debugging. |
| **sentry-sdk[fastapi]** | ≥2.0.0 | Error tracking | Automatic exception capture, performance monitoring, and error grouping. Integrates with FastAPI for request-level context. |
| **opentelemetry-api** | ≥1.25.0 | Tracing API | OpenTelemetry tracing standards. Provides vendor-neutral tracing API. |
| **opentelemetry-sdk** | ≥1.25.0 | Tracing SDK | OpenTelemetry implementation. Handles span creation, context propagation, and export. |
| **opentelemetry-exporter-otlp** | ≥1.25.0 | Trace export | Exports traces to Jaeger/Grafana via OTLP protocol. Supports both gRPC and HTTP. |
| **opentelemetry-instrumentation-fastapi** | ≥0.46b0 | Auto-instrumentation | Automatically traces all FastAPI endpoints without code changes. |
| **opentelemetry-instrumentation-requests** | ≥0.46b0 | HTTP tracing | Traces outgoing HTTP requests to external APIs. |
| **opentelemetry-instrumentation-logging** | ≥0.46b0 | Log correlation | Adds trace IDs to log messages for correlation. |

**Why This Observability Stack?**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sentry    │     │   Jaeger    │     │  structlog  │
│  (Errors)   │     │  (Traces)   │     │   (Logs)    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    FastAPI Application
```
- **Sentry**: Catches errors before users report them
- **Jaeger**: Visualizes request flow across services
- **structlog**: Structured logs for easier debugging

### 3.7 Complete requirements.txt

```txt
fastapi
uvicorn[standard]
supabase
qdrant-client>=1.16.0
python-dotenv
pydantic
numpy
openai
--extra-index-url https://download.pytorch.org/whl/cpu
torch
sentence-transformers
transformers>=4.30.0
scikit-learn>=1.3.0
pint
quantulum3
requests
nltk
structlog>=25.5.0

# OpenTelemetry for Jaeger distributed tracing
opentelemetry-api>=1.25.0
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp>=1.25.0
opentelemetry-instrumentation-fastapi>=0.46b0
opentelemetry-instrumentation-requests>=0.46b0
opentelemetry-instrumentation-logging>=0.46b0

# Sentry for error tracking and performance monitoring
sentry-sdk[fastapi]>=2.0.0
```

---

## 4. External APIs Used

### 4.1 OpenAI API

| Endpoint | Purpose | File Location |
|----------|---------|---------------|
| `chat.completions.create` | GPT-4o extraction | `main.py:538-551`, `src/core/extraction/gpt_extractor.py:121-135` |

**Configuration:**
```python
model: "gpt-4o"
temperature: 0.0
response_format: {"type": "json_object"}
```

**Why GPT-4o?**
- Best structured output following
- JSON mode ensures valid JSON response
- Temperature 0.0 for deterministic extraction
- 100% accuracy on test cases for schema extraction

**Usage Example:**
```python
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": query}
    ],
    temperature=0.0,
    response_format={"type": "json_object"}
)
```

---

### 4.2 Wikidata API

| Endpoint | Purpose | File Location |
|----------|---------|---------------|
| `wbsearchentities` | Entity search | `src/services/external/wikidata_wrapper.py:57-85` |
| SPARQL endpoint | Hierarchy queries | `src/services/external/wikidata_wrapper.py:105-151` |

**Endpoints:**
```python
api_endpoint = "https://www.wikidata.org/w/api.php"
sparql_endpoint = "https://query.wikidata.org/sparql"
```

**Why Wikidata?**
- Free, no API key required
- Comprehensive hierarchical data (P31: instance of, P279: subclass of)
- Multilingual canonical labels
- Covers: item types, professions, categories

**Example Use Case:**
```
"dentist" → Wikidata → Q27349 → subclass_of → Q39631 (physician) → is_a → "doctor"
```

**Key Methods:**
```python
# Search for entities
search_entity(term: str, language: str = "en", limit: int = 5) -> List[Dict]

# Get canonical label
get_canonical_label(term: str, language: str = "en") -> Optional[str]

# Get superclasses via SPARQL
get_superclasses(entity_id: str, language: str = "en") -> List[Tuple[str, str]]

# Get full hierarchy path
get_hierarchy_path(term: str, max_depth: int = 5) -> List[List[Dict]]
```

---

### 4.3 OpenStreetMap Nominatim API

| Endpoint | Purpose | File Location |
|----------|---------|---------------|
| `/search` | Geocoding | `src/services/external/geocoding_service.py:107-178` |

**Endpoint:**
```python
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
```

**Why Nominatim?**
- Completely free (no API key)
- Covers worldwide locations
- Returns canonical names ("Bangalore" → "Bengaluru")
- Provides coordinates for distance calculations

**Rate Limiting:**
- 1 request per second (Nominatim policy)
- File-based caching to minimize API calls

**Key Methods:**
```python
# Geocode a location
geocode(location_name: str) -> Optional[Dict]
# Returns: {"lat": 12.9716, "lng": 77.5946, "canonical_name": "Bengaluru"}

# Calculate distance between locations
distance(location1: str, location2: str) -> Optional[float]
# Returns: distance in kilometers

# Check if within range
is_within_distance(location1: str, location2: str, max_km: float = 50.0) -> bool
```

---

### 4.4 Frankfurter API (Currency Exchange)

| Endpoint | Purpose | File Location |
|----------|---------|---------------|
| `/latest` | Exchange rates | `src/services/external/currency_service.py:154-180` |
| `/currencies` | Currency list | `src/services/external/currency_service.py:126-152` |

**Endpoint:**
```python
BASE_URL = "https://api.frankfurter.app"
```

**Why Frankfurter?**
- Free, no API key required
- European Central Bank data (reliable)
- 30+ currencies including INR, USD, EUR
- Daily updates

**Key Methods:**
```python
# Get exchange rate
get_rate(from_currency: str, to_currency: str = "USD") -> Optional[float]

# Convert amount
convert(amount: float, from_currency: str, to_currency: str = "USD") -> Optional[float]

# Check if valid currency code
is_currency_code(code: str) -> bool
```

**Caching:**
- In-memory cache with 6-hour TTL
- Thread-safe via Lock

---

### 4.5 BabelNet API (Optional)

| Endpoint | Purpose | File Location |
|----------|---------|---------------|
| Synset search | Multilingual synonyms | `src/services/external/babelnet_wrapper.py` |

**Why BabelNet?**
- Largest multilingual semantic network
- Combines WordNet + Wikipedia + Wiktionary
- Disambiguation via embedding-based context matching
- **Requires API key** (optional, fallback to WordNet if unavailable)

---

### 4.6 WordNet (Local via NLTK)

| Function | Purpose | File Location |
|----------|---------|---------------|
| `wn.synsets()` | Synonym lookup | `main.py:274-291` |
| `hypernym_paths()` | Hierarchy traversal | `canonicalization/resolvers/generic_categorical_resolver.py:164-193` |

**Why WordNet?**
- Local database (no API calls, instant)
- Built into NLTK
- Comprehensive English lexical database
- Provides: synonyms, hypernyms, hyponyms, derivations

**Example Usage:**
```python
from nltk.corpus import wordnet as wn

# Get synsets
synsets = wn.synsets("laptop")

# Check if two terms share a synset (true synonyms)
c_synsets = set(wn.synsets("laptop"))
r_synsets = set(wn.synsets("notebook"))
if c_synsets & r_synsets:
    return True  # They're synonyms

# Get hypernym paths
for synset in synsets:
    for path in synset.hypernym_paths():
        print(path)  # [entity, artifact, device, machine, computer, laptop]
```

---

### 4.7 External API Summary Table

| API | Auth Required | Rate Limit | Cache TTL | Purpose |
|-----|---------------|------------|-----------|---------|
| OpenAI GPT-4o | API Key | Per-account | None | Extraction |
| Wikidata | None | None | In-memory | Ontology |
| Nominatim | None | 1 req/sec | File-based | Geocoding |
| Frankfurter | None | None | 6 hours | Currency |
| BabelNet | API Key | Per-account | In-memory | Synonyms |
| WordNet | None (local) | N/A | N/A | Synonyms |

---

## 5. Internal API Endpoints

### 5.1 Health & Status

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/` | GET | Service status | `{status, initialized, service}` |
| `/health` | GET | Health check (load balancers) | `{status: "ok"}` |
| `/ping` | GET | Ultra-simple ping | `"pong"` |

---

### 5.2 Extraction Endpoints

| Endpoint | Method | Input | Output | File |
|----------|--------|-------|--------|------|
| `/extract` | POST | `{query: string}` | `{extracted_listing: NEW_SCHEMA}` | `main.py:557-599` |
| `/extract-and-normalize` | POST | `{query: string}` | `{extracted_listing, normalized_listing}` | `main.py:601-632` |
| `/extract-and-match` | POST | `{query_a, query_b}` | `{match: boolean, details}` | `main.py:634-695` |

**`/extract` Example:**
```json
// Input
{"query": "need a plumber who speaks kannada"}

// Output
{
  "status": "success",
  "query": "need a plumber who speaks kannada",
  "extracted_listing": {
    "intent": "service",
    "subintent": "seek",
    "domain": ["construction & trades"],
    "primary_mutual_category": [],
    "items": [{"type": "plumbing", "categorical": {}, "min": {}, "max": {}, "range": {}}],
    "item_exclusions": [],
    "other_party_preferences": {
      "categorical": {"language": "kannada"},
      "min": {},
      "max": {},
      "range": {}
    },
    "other_party_exclusions": [],
    "self_attributes": {"categorical": {}, "min": {}, "max": {}, "range": {}},
    "self_exclusions": [],
    "target_location": {},
    "location_match_mode": "near_me",
    "location_exclusions": [],
    "reasoning": "User is seeking plumbing services with language preference for Kannada"
  }
}
```

---

### 5.3 Matching Endpoints

| Endpoint | Method | Input | Output | File |
|----------|--------|-------|--------|------|
| `/match` | POST | `{listing_a, listing_b}` | `{match: boolean}` | `main.py:453-472` |
| `/search-and-match` | POST | `{query, user_id}` | `{matched_listings[], match_count}` | `main.py:702-845` |
| `/search-and-match-direct` | POST | `{listing_json, user_id}` | `{matches[]}` | `main.py:848-940` |

**`/search-and-match` Example:**
```json
// Input
{
  "query": "I need a plumber in Bangalore",
  "user_id": "user-uuid-123"
}

// Output
{
  "status": "success",
  "listing_id": "new-listing-uuid",
  "match_ids": ["match-uuid-1", "match-uuid-2"],
  "query_text": "I need a plumber in Bangalore",
  "query_json": { /* extracted JSON */ },
  "has_matches": true,
  "match_count": 2,
  "matched_listings": [
    {
      "listing_id": "listing-uuid-1",
      "user_id": "provider-uuid-1",
      "data": { /* listing data */ }
    }
  ],
  "message": "Found 2 matches"
}
```

---

### 5.4 Storage Endpoints

| Endpoint | Method | Input | Output | File |
|----------|--------|-------|--------|------|
| `/ingest` | POST | `{listing, user_id}` | `{listing_id}` | `main.py:400-430` |
| `/store-listing` | POST | `{query, user_id}` | `{listing_id, extracted_json}` | `main.py:943-1053` |
| `/search` | POST | `{listing, limit?}` | `{candidates[]}` | `main.py:432-451` |
| `/normalize` | POST | `{listing}` | `{normalized_listing}` | `main.py:474-483` |

---

### 5.5 Request/Response Models

```python
# Pydantic Models (main.py)

class ListingRequest(BaseModel):
    listing: Dict[str, Any]
    user_id: Optional[str] = None

class MatchRequest(BaseModel):
    listing_a: Dict[str, Any]
    listing_b: Dict[str, Any]

class QueryRequest(BaseModel):
    query: str

class DualQueryRequest(BaseModel):
    query_a: str
    query_b: str

class SearchAndMatchRequest(BaseModel):
    query: str
    user_id: str

class StoreListingRequest(BaseModel):
    query: str
    user_id: str
    match_id: Optional[str] = None
```

---

### 5.6 Complete API Reference

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/` | GET | No | Service status |
| `/health` | GET | No | Health check |
| `/ping` | GET | No | Simple ping |
| `/extract` | POST | No | NL → JSON extraction |
| `/extract-and-normalize` | POST | No | Extract + normalize |
| `/extract-and-match` | POST | No | Extract two queries, match |
| `/normalize` | POST | No | Normalize listing |
| `/match` | POST | No | Match two listings |
| `/search` | POST | No | Vector search |
| `/ingest` | POST | No | Store listing |
| `/search-and-match` | POST | No | Full pipeline |
| `/search-and-match-direct` | POST | No | Full pipeline (no GPT) |
| `/store-listing` | POST | No | Extract + store |

---

## 6. System Architecture

### 6.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPS                                  │
│                    (Flutter Mobile / Web Browser)                         │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ HTTPS
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI SERVER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   /extract  │  │   /match    │  │  /search    │  │   /ingest   │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                │                │                │              │
│  ┌──────▼──────────────────────────────────────────────────▼──────┐      │
│  │                    PROCESSING PIPELINE                          │      │
│  │  ┌────────────┐  ┌────────────────┐  ┌─────────────────┐       │      │
│  │  │ Extraction │→ │ Canonicalization│→ │  Normalization  │       │      │
│  │  │  (GPT-4o)  │  │ (Ontology APIs) │  │  (NEW→OLD)      │       │      │
│  │  └────────────┘  └────────────────┘  └─────────────────┘       │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    MATCHING ENGINE                               │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │      │
│  │  │  Intent  │→ │  Domain  │→ │   Items  │→ │ Location │        │      │
│  │  │   Gate   │  │   Gate   │  │  Matcher │  │  Matcher │        │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │      │
│  └─────────────────────────────────────────────────────────────────┘      │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    PostgreSQL    │    │      Qdrant      │    │   External APIs  │
│   (Supabase)     │    │  (Vector DB)     │    │                  │
│                  │    │                  │    │  • OpenAI GPT-4o │
│  • Listings      │    │  • product_      │    │  • Wikidata      │
│  • Matches       │    │    vectors       │    │  • Nominatim     │
│  • Ontology      │    │  • service_      │    │  • Frankfurter   │
│                  │    │    vectors       │    │  • BabelNet      │
│                  │    │  • mutual_       │    │                  │
│                  │    │    vectors       │    │                  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 6.2 Folder Structure

```
Singletap-backend/
├── main.py                          # FastAPI application (1054 lines)
├── requirements.txt                 # Python dependencies
│
├── src/                             # Modular source code
│   ├── api/                         # API routes
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── config/                      # Settings, constants, clients
│   │   ├── __init__.py
│   │   ├── settings.py              # Configuration management
│   │   ├── constants.py             # Application constants
│   │   └── clients.py               # Database clients
│   ├── core/
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── gpt_extractor.py     # GPT-4o extraction logic
│   │   │   └── hybrid_extractor.py  # Hybrid GPT + NuExtract
│   │   ├── matching/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py      # Matching orchestration
│   │   │   ├── item_matchers.py     # Item matching logic
│   │   │   ├── item_array_matchers.py
│   │   │   ├── other_self_matchers.py
│   │   │   ├── location_matcher.py  # Location matching
│   │   │   ├── numeric_constraints.py
│   │   │   ├── mutual_matcher.py
│   │   │   └── ontology_resolver.py
│   │   ├── canonicalization/
│   │   │   ├── __init__.py
│   │   │   └── resolvers/
│   │   │       ├── __init__.py
│   │   │       ├── generic_categorical_resolver.py
│   │   │       ├── quantitative_resolver.py
│   │   │       └── type_resolver.py
│   │   └── schema/
│   │       ├── __init__.py
│   │       └── normalizer.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── embedding/
│   │   │   ├── __init__.py
│   │   │   └── service.py
│   │   ├── ranking/
│   │   │   ├── __init__.py
│   │   │   ├── ranking_engine.py
│   │   │   ├── rrf.py               # Reciprocal Rank Fusion
│   │   │   └── cross_encoder_wrapper.py
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   └── service.py
│   │   ├── storage/
│   │   │   └── __init__.py
│   │   └── external/                # External API Wrappers
│   │       ├── __init__.py
│   │       ├── wikidata_wrapper.py  # Wikidata API
│   │       ├── geocoding_service.py # Nominatim geocoding
│   │       ├── currency_service.py  # Frankfurter currency
│   │       ├── babelnet_wrapper.py  # BabelNet API
│   │       ├── conceptnet_wrapper.py
│   │       ├── pint_wrapper.py      # Unit conversion
│   │       └── quantulum_wrapper.py # Quantity extraction
│   ├── setup/
│   │   ├── __init__.py
│   │   └── qdrant_setup.py          # Qdrant collection setup
│   ├── data/
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── gpc_loader.py
│   │   │   └── unspsc_loader.py
│   │   └── type_hierarchy.json
│   └── utils/
│       ├── __init__.py
│       ├── logging.py               # structlog configuration
│       ├── tracing.py               # OpenTelemetry setup
│       ├── sentry.py                # Error tracking
│       └── helpers.py
│
├── pipeline/                        # Data pipelines
│   ├── __init__.py
│   ├── ingestion_pipeline.py        # Supabase + Qdrant ingestion
│   └── retrieval_service.py         # Candidate retrieval
│
├── matching/                        # Matching engine
│   ├── __init__.py
│   ├── listing_matcher_v2.py        # Main orchestrator
│   ├── item_array_matchers.py
│   ├── other_self_matchers.py
│   └── location_matcher_v2.py
│
├── canonicalization/                # Ontology resolution
│   ├── __init__.py
│   ├── orchestrator.py              # Main canonicalization entry
│   ├── ontology_store.py            # Persistence layer
│   ├── preprocessor.py
│   ├── disambiguator.py
│   ├── canonicalizer.py
│   └── resolvers/
│       └── generic_categorical_resolver.py
│
├── schema/                          # Schema transformation
│   ├── __init__.py
│   └── schema_normalizer_v2.py      # NEW → OLD schema
│
├── embedding/                       # Embedding generation
│   ├── __init__.py
│   ├── embedding_builder.py         # Text → embedding text
│   └── model_provider.py            # Singleton model loader
│
├── services/                        # Legacy services (being migrated)
│   └── external/
│       ├── babelnet_wrapper.py
│       └── wordnet_wrapper.py
│
├── prompt/                          # GPT prompts
│   └── GLOBAL_REFERENCE_CONTEXT.md  # Extraction prompt (system message)
│
├── migrations/                      # SQL migrations
│   ├── 001_create_matches_table.sql
│   ├── 002_create_listings_tables.sql
│   └── 003_create_concept_ontology.sql
│
├── tests/                           # Test suites
│   ├── unit_testing/
│   │   ├── test_item_matchers.py
│   │   ├── test_item_array_matchers.py
│   │   ├── test_location_matchers.py
│   │   ├── test_mutual_matcher.py
│   │   ├── test_normalizer.py
│   │   ├── test_numeric_constraints.py
│   │   ├── test_other_self_matchers.py
│   │   ├── test_ranking_engine.py
│   │   ├── test_embedding_v2.py
│   │   └── verify_qdrant.py
│   ├── integration_testing/
│   │   ├── test_canonicalization.py
│   │   ├── test_extraction_api.py
│   │   ├── test_gpt_extraction.py
│   │   ├── test_qdrant_search.py
│   │   └── test_single_query.py
│   ├── feature_testing/
│   │   ├── test_all_examples.py
│   │   ├── test_complete_flow.py
│   │   ├── test_debug_matches.py
│   │   ├── test_e2e_matching.py
│   │   ├── test_flow_direct.py
│   │   ├── test_mutual_queries.py
│   │   ├── test_search_debug.py
│   │   └── test_user_queries.py
│   └── files_functions_testing/
│       ├── fix_test_files.py
│       └── test_schema_update.py
│
├── scripts/                         # Utility scripts
│   ├── check_tables.py
│   ├── create_payload_indexes.py
│   ├── create_qdrant_collections.py
│   ├── download_model.py
│   ├── fix_user_id_type.py
│   ├── qdrant_setup.py
│   ├── run_migration.py
│   └── run_migration_direct.py
│
├── legacy/                          # Deprecated code
│   ├── cross_encoder_wrapper.py
│   ├── integration_example_v2.py
│   ├── listing_matcher.py
│   ├── location_matchers.py
│   ├── mutual_matcher.py
│   ├── new_endpoints.py
│   ├── query_pipeline_example.py
│   ├── ranking_engine.py
│   ├── rrf.py
│   └── schema_normalizer.py
│
├── docs/                            # Documentation
│   └── ARCHITECTURE_DOCUMENTATION.md  # This file
│
├── test_queries/                    # Test query files
│
├── models/                          # ML models directory
│
├── nltk_data/                       # NLTK data (WordNet, etc.)
│
├── docker-compose.yaml              # Docker orchestration
├── docker-compose.jaeger.yml        # Jaeger tracing setup
├── Procfile                         # Railway deployment
├── railway.toml                     # Railway config
├── render.yaml                      # Render deployment
├── geocoding_cache.json             # Geocoding cache file
│
└── README.md                        # Project README
```

---

## 7. Core Components Deep Dive

### 7.1 GPT Extraction Pipeline

**Location:** `src/core/extraction/gpt_extractor.py`

**Purpose:** Convert natural language queries into structured 14-field NEW schema.

**Process:**
```
"looking for a plumber who speaks kannada in bangalore"
                           │
                           ▼
              ┌────────────────────────┐
              │   Load System Prompt   │
              │   (GLOBAL_REFERENCE_   │
              │    CONTEXT.md)         │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   GPT-4o API Call      │
              │   model: "gpt-4o"      │
              │   temperature: 0.0     │
              │   format: json_object  │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Parse JSON Response  │
              └────────────┬───────────┘
                           │
                           ▼
{
  "intent": "service",
  "subintent": "seek",
  "domain": ["construction & trades"],
  "items": [{"type": "plumbing", "categorical": {}}],
  "other_party_preferences": {
    "categorical": {"language": "kannada"}
  },
  "target_location": {"name": "bangalore"},
  "location_match_mode": "near_me"
}
```

**Extraction Modes:**
| Mode | Environment Variable | Description |
|------|---------------------|-------------|
| GPT-Only (default) | `EXTRACTION_MODE=gpt` | Fast (~5-15s), 100% accuracy |
| Hybrid | `EXTRACTION_MODE=hybrid` | GPT + NuExtract validation layer |
| Hybrid (skip validation) | `EXTRACTION_MODE=hybrid` + `SKIP_NUEXTRACT=1` | Hybrid extractor without Level 2 |

**Code Structure:**
```python
class GPTExtractor:
    def __init__(self):
        self.openai_client: Optional[OpenAI] = None
        self.extraction_prompt: Optional[str] = None
        self.initialized: bool = False

    def initialize(self, api_key=None, prompt_path=None) -> bool:
        """Load prompt + OpenAI client"""

    def extract(self, query: str, model="gpt-4o", temperature=0.0) -> Dict[str, Any]:
        """Extract structured schema from query"""
```

---

### 7.2 Canonicalization Pipeline

**Location:** `canonicalization/orchestrator.py`

**Purpose:** Resolve non-deterministic values to canonical forms.

**Pipeline Flow:**
```
GPT-4o → NEW Schema → CANONICALIZE → Canonical NEW → Normalize → OLD Schema
```

**Canonicalization Steps:**
1. **Domain canonicalization** - Lowercase normalization
2. **Item type canonicalization** - Wikidata with domain context
3. **Categorical attribute resolution** - Multi-source ontology
4. **Quantitative normalization** - Pint + Quantulum3
5. **Location canonicalization** - Nominatim geocoding
6. **Flush to ontology DB** - Write-behind persistence

**Resolution Cascade:**
```
Input Value
     │
     ▼
┌────────────────────┐
│ Synonym Registry?  │ ─Yes→ Return cached concept_id
└────────┬───────────┘
         │No
         ▼
┌────────────────────┐
│ WordNet (local)?   │ ─Yes→ Return with hierarchy
└────────┬───────────┘
         │No
         ▼
┌────────────────────┐
│ BabelNet (API)?    │ ─Yes→ Return with synonyms
└────────┬───────────┘
         │No
         ▼
┌────────────────────┐
│ Wikidata (API)?    │ ─Yes→ Return with hierarchy
└────────┬───────────┘
         │No
         ▼
┌────────────────────┐
│ Lowercase Fallback │
└────────────────────┘
```

**OntologyNode Structure:**
```python
@dataclass
class OntologyNode:
    concept_id: str          # Canonical identifier
    concept_root: str        # Root category
    concept_path: List[str]  # Full path from root
    parents: List[str]       # Direct parents
    children: List[str]      # Direct children
    siblings: List[str]      # Related concepts
    source: str              # wordnet/babelnet/wikidata/fallback
    confidence: float        # 0.0 to 1.0
```

---

### 7.3 Schema Normalization

**Location:** `schema/schema_normalizer_v2.py`

**Purpose:** Transform 14-field NEW schema → 12-field OLD schema for matching engine compatibility.

**Field Transformations:**

| NEW Schema Field | OLD Schema Field |
|------------------|------------------|
| `intent` | `intent` |
| `subintent` | `subintent` |
| `domain` | `domain` |
| `primary_mutual_category` | `category` |
| `items` | `items` |
| `item_exclusions` | `itemexclusions` |
| `other_party_preferences` | `other` |
| `other_party_exclusions` | `otherexclusions` |
| `self_attributes` | `self` |
| `self_exclusions` | `selfexclusions` |
| `target_location` | `location` |
| `location_match_mode` | `locationmode` |
| `location_exclusions` | `locationexclusions` |
| `reasoning` | `reasoning` |

**Constraint Flattening:**
```python
# NEW Schema (axis-based)
{
    "min": {
        "capacity": [{"type": "memory", "value": 16, "unit": "gb"}]
    }
}

# OLD Schema (flat)
{
    "min": {
        "memory": 16
    }
}
```

**Valid Axes (10 fixed):**
- identity, capacity, performance, quality, quantity
- time, space, cost, mode, skill

---

### 7.4 Matching Engine

**Location:** `matching/listing_matcher_v2.py`

**Purpose:** Determine if listing B satisfies listing A's requirements.

**Direction:** A → B (unidirectional)
- A = requester (what they want)
- B = candidate (what they offer)

**Matching Rules (Short-Circuit Evaluation):**

```python
def listing_matches_v2(A: Dict, B: Dict, implies_fn=None) -> bool:
    """
    Returns True only if B satisfies ALL of A's constraints.
    Short-circuits on first failure.
    """

    # ══════════════════════════════════════════════════════
    # GATE 1: Intent Equality (Rule M-01)
    # ══════════════════════════════════════════════════════
    if A["intent"] != B["intent"]:
        return False  # Intent mismatch

    # ══════════════════════════════════════════════════════
    # GATE 2: SubIntent Rules (Rules M-02, M-03)
    # ══════════════════════════════════════════════════════
    intent = A["intent"]

    if intent in ["product", "service"]:
        # M-02: SubIntent Inverse Rule
        # buyer/seller, seeker/provider must be opposite
        if A["subintent"] == B["subintent"]:
            return False  # Both buyers or both sellers

    elif intent == "mutual":
        # M-03: SubIntent Same Rule
        # Both must be "connect"
        if A["subintent"] != B["subintent"]:
            return False

    # ══════════════════════════════════════════════════════
    # GATE 3: Domain/Category Intersection (Rules M-05, M-06)
    # ══════════════════════════════════════════════════════
    if intent in ["product", "service"]:
        # M-05: Domain must have non-empty intersection
        if not has_intersection(A["domain"], B["domain"]):
            return False

    elif intent == "mutual":
        # M-06: Category must have non-empty intersection
        if not has_intersection(A["category"], B["category"]):
            return False

    # ══════════════════════════════════════════════════════
    # GATE 4: Items Matching (Rules M-07 to M-12)
    # ══════════════════════════════════════════════════════
    if intent in ["product", "service"]:
        if not all_required_items_match(A["items"], B["items"], implies_fn):
            return False

    # ══════════════════════════════════════════════════════
    # GATE 5: Other→Self Matching (Rules M-13 to M-17)
    # ══════════════════════════════════════════════════════
    if not match_other_to_self(A["other"], B["self"], implies_fn):
        return False

    # ══════════════════════════════════════════════════════
    # GATE 6: Location Matching (Rules M-23 to M-28)
    # ══════════════════════════════════════════════════════
    if not match_location_v2(A, B):
        return False

    # ══════════════════════════════════════════════════════
    # ALL GATES PASSED
    # ══════════════════════════════════════════════════════
    return True
```

**Matching Rules Reference:**

| Rule | Gate | Logic |
|------|------|-------|
| M-01 | Intent | `A.intent == B.intent` |
| M-02 | SubIntent (product/service) | `A.subintent ≠ B.subintent` |
| M-03 | SubIntent (mutual) | `A.subintent == B.subintent` |
| M-04 | Intent-SubIntent Validity | Schema validated |
| M-05 | Domain | `A.domain ∩ B.domain ≠ ∅` |
| M-06 | Category | `A.category ∩ B.category ≠ ∅` |
| M-07 to M-12 | Items | Type + Categorical + Numeric |
| M-13 to M-17 | Other→Self | Preferences matching |
| M-23 to M-28 | Location | Mode-based matching |

---

### 7.5 Semantic Implication Engine

**Location:** `main.py:217-356`

**Purpose:** Check if one categorical term implies another.

**Strategies (in order of evaluation):**

1. **Exact Match**
   ```python
   if candidate.lower() == required.lower():
       return True
   ```

2. **Curated Synonyms**
   ```python
   CURATED_SYNONYMS = {
       frozenset({"laptop", "notebook"}),
       frozenset({"cleaning", "housekeeping", "housework"}),
       frozenset({"couch", "sofa"}),
       frozenset({"automobile", "car", "auto"}),
       frozenset({"phone", "telephone", "cellphone", "mobile"}),
       frozenset({"apartment", "flat"}),
   }
   ```

3. **Wikidata Hierarchy**
   ```python
   # "dentist" is subclass of "doctor"
   if wikidata.is_subclass_of(candidate, required, max_depth=3):
       return True
   ```

4. **WordNet Ancestor**
   ```python
   if resolver.is_ancestor(required, candidate):
       return True
   ```

5. **WordNet Synset Overlap**
   ```python
   if candidate_synsets & required_synsets:
       return True  # Same synset = true synonyms
   ```

6. **Morphological Matching**
   ```python
   # "plumber" ↔ "plumbing" share root "plumb"
   if len(common_prefix) >= 5:
       return True
   ```

7. **BabelNet Synonyms**
   ```python
   if candidate in babelnet.get_synonyms(required):
       return True
   ```

---

### 7.6 Embedding Pipeline

**Location:** `embedding/embedding_builder.py`

**Purpose:** Build text representation for embedding generation.

**Strategy by Intent:**

| Intent | Strategy | Example Output |
|--------|----------|----------------|
| Product/Service | Structured concatenation | `"product buy electronics laptop brand apple ram memory"` |
| Mutual | Natural language | `"mutual exchange in categories: tutoring offering math tutoring wanting english lessons"` |

**Code:**
```python
def build_embedding_text(listing: Dict[str, Any]) -> str:
    """Route to appropriate builder based on intent."""
    intent = listing["intent"]

    if intent in ["product", "service"]:
        return build_embedding_text_product_service(listing)
    elif intent == "mutual":
        return build_embedding_text_mutual(listing)
    else:
        raise ValueError(f"Unknown intent: {intent}")

def build_embedding_text_product_service(listing: Dict) -> str:
    """Concatenate: intent + subintent + domain + items (type + categorical)"""
    parts = []

    if listing.get("intent"):
        parts.append(listing["intent"])

    if listing.get("subintent"):
        parts.append(listing["subintent"])

    for domain in listing.get("domain", []):
        parts.append(str(domain))

    for item in listing.get("items", []):
        if item.get("type"):
            parts.append(str(item["type"]))
        for key, value in item.get("categorical", {}).items():
            parts.append(str(key))
            parts.append(str(value))

    return " ".join(parts)
```

---

### 7.7 Retrieval Pipeline

**Location:** `pipeline/retrieval_service.py`

**Purpose:** Retrieve candidate listings for matching.

**Two-Stage Retrieval:**

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 1: SQL FILTER                       │
│                      (Supabase)                              │
│                                                              │
│  • Filter by intent (product/service/mutual)                 │
│  • Filter by domain/category intersection                    │
│  • Returns: candidate_ids (coarse filter)                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   STAGE 2: VECTOR SEARCH                     │
│                      (Qdrant)                                │
│                                                              │
│  • Generate query embedding                                  │
│  • Search with payload filters (intent, domain)              │
│  • Returns: ranked candidate_ids (semantic similarity)       │
└─────────────────────────────────────────────────────────────┘
```

**Code:**
```python
def retrieve_candidates(
    clients: RetrievalClients,
    query_listing: Dict[str, Any],
    limit: int = 100,
    use_sql_filter: bool = True
) -> List[str]:
    """
    Pipeline:
    1. SQL filter (Supabase) - optional
    2. Qdrant vector search with payload filters
    3. Return candidate listing_ids

    NO ranking. NO boolean matching. NO scoring returned.
    """
```

---

## 8. Database Architecture

### 8.1 PostgreSQL Schema (Supabase)

**Listings Tables:**

```sql
-- Product Listings
CREATE TABLE IF NOT EXISTS product_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    match_id UUID REFERENCES matches(match_id),
    data JSONB NOT NULL,  -- Complete listing object
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_product_user ON product_listings(user_id);
CREATE INDEX idx_product_created ON product_listings(created_at DESC);
CREATE INDEX idx_product_match ON product_listings(match_id);

-- Same structure for: service_listings, mutual_listings
```

**Matches Table:**

```sql
CREATE TABLE IF NOT EXISTS matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_user_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    query_json JSONB NOT NULL,
    has_matches BOOLEAN NOT NULL,
    match_count INTEGER NOT NULL DEFAULT 0,
    matched_user_ids UUID[] DEFAULT '{}',
    matched_listing_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_matches_user ON matches(query_user_id);
CREATE INDEX idx_matches_created ON matches(created_at DESC);
CREATE INDEX idx_matches_has_matches ON matches(has_matches);
```

### 8.2 Qdrant Collections

```
┌────────────────────────────────────────────────────────────────┐
│                     QDRANT COLLECTIONS                          │
├────────────────────────────────────────────────────────────────┤
│  Collection: product_vectors                                    │
│  ├── Dimension: 384 (all-MiniLM-L6-v2) or 1024 (bge-large)     │
│  ├── Distance: Cosine                                           │
│  └── Payload Schema:                                            │
│      {                                                          │
│        "listing_id": "uuid-string",                            │
│        "intent": "product",                                     │
│        "domain": ["electronics", "computers"],                  │
│        "created_at": 1708099200                                 │
│      }                                                          │
├────────────────────────────────────────────────────────────────┤
│  Collection: service_vectors                                    │
│  ├── Dimension: 384/1024                                        │
│  ├── Distance: Cosine                                           │
│  └── Payload: {listing_id, intent, domain[], created_at}        │
├────────────────────────────────────────────────────────────────┤
│  Collection: mutual_vectors                                     │
│  ├── Dimension: 384/1024                                        │
│  ├── Distance: Cosine                                           │
│  └── Payload: {listing_id, intent, category[], created_at}      │
└────────────────────────────────────────────────────────────────┘
```

### 8.3 Data Model Relationships

```
┌─────────────────┐       ┌─────────────────┐
│     users       │       │     matches     │
│  (external)     │       ├─────────────────┤
└────────┬────────┘       │ match_id (PK)   │
         │                │ query_user_id   │◄──────────┐
         │                │ query_text      │           │
         │                │ query_json      │           │
         │                │ has_matches     │           │
         │                │ matched_user_ids│           │
         │                │ matched_listing_ids         │
         │                │ created_at      │           │
         │                └────────┬────────┘           │
         │                         │                    │
         ▼                         ▼                    │
┌─────────────────┐       ┌─────────────────┐          │
│ product_listings│       │ service_listings│          │
├─────────────────┤       ├─────────────────┤          │
│ id (PK)         │       │ id (PK)         │          │
│ user_id ────────┼───────┼─user_id ────────┼──────────┤
│ match_id (FK)───┼───────┼─match_id (FK)───┼──────────┘
│ data (JSONB)    │       │ data (JSONB)    │
│ created_at      │       │ created_at      │
└─────────────────┘       └─────────────────┘

         ┌─────────────────┐
         │ mutual_listings │
         ├─────────────────┤
         │ id (PK)         │
         │ user_id         │
         │ match_id (FK)   │
         │ data (JSONB)    │
         │ created_at      │
         └─────────────────┘
```

---

## 9. ML Pipeline

### 9.1 Model Configuration

| Component | Model | Dimension | Purpose |
|-----------|-------|-----------|---------|
| Extraction | GPT-4o | N/A | Natural Language → JSON |
| Embedding (default) | all-MiniLM-L6-v2 | 384 | Fast, lightweight |
| Embedding (large) | BAAI/bge-large-en-v1.5 | 1024 | Better quality |

### 9.2 Model Selection

```python
# Environment variable
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Dimension depends on model
EMBEDDING_DIM = 1024 if "large" in EMBEDDING_MODEL else 384
```

### 9.3 Embedding Generation Flow

```
Listing Object
      │
      ▼
┌─────────────────────┐
│ build_embedding_text│  ← Converts structured data to text
│   (embedding_builder│
│    .py)             │
└──────────┬──────────┘
           │
           ▼
    "product buy electronics laptop brand apple..."
           │
           ▼
┌─────────────────────┐
│ SentenceTransformer │  ← Generates vector
│    .encode(text)    │
│                     │
│  Model: all-MiniLM  │
│  or BAAI/bge-large  │
└──────────┬──────────┘
           │
           ▼
    [0.023, -0.156, 0.089, ...] (384/1024 dimensions)
           │
           ▼
┌─────────────────────┐
│  Qdrant Collection  │  ← Stored for search
│                     │
│  - Point ID: UUID   │
│  - Vector: [...]    │
│  - Payload: {...}   │
└─────────────────────┘
```

### 9.4 Model Provider (Singleton)

```python
# embedding/model_provider.py

_embedding_model = None

def get_embedding_model():
    """Get singleton embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model
```

---

## 10. Observability Stack

### 10.1 Structured Logging (structlog)

**Location:** `src/utils/logging.py`

**Features:**
- Emoji indicators for log types
- JSON output for production
- Contextual logging with key-value pairs
- Timestamp formatting

**Emoji Indicators:**
| Emoji | Key | Usage |
|-------|-----|-------|
| 🚀 | start | Server startup, initialization |
| ✅ | success | Successful operations |
| ❌ | error | Errors and failures |
| ⚠️ | warning | Warnings |
| ℹ️ | info | Informational messages |
| 🔍 | search | Search operations |
| 💾 | store | Storage operations |
| 🎯 | match | Matching operations |
| 🤖 | extract | GPT extraction |
| 🔎 | filter | Filtering operations |
| 🧠 | semantic | Semantic matching |
| ⚖️ | boolean | Boolean matching |
| 📍 | location | Location matching |

**Usage:**
```python
from src.utils.logging import get_logger

log = get_logger(__name__)

log.info("Server starting", emoji="start", port=8000)
# Output: 🚀 Server starting    port=8000

log.error("Connection failed", emoji="error", error=str(e))
# Output: ❌ Connection failed    error="..."

log.info("Found matches", emoji="match", count=5, user_id="abc")
# Output: 🎯 Found matches    count=5  user_id=abc
```

**Configuration:**
```python
configure_structlog(
    json_output=False,  # True for production
    log_level="INFO",
    include_timestamp=True
)
```

---

### 10.2 Error Tracking (Sentry)

**Location:** `src/utils/sentry.py`

**Captures:**
- Unhandled exceptions
- HTTP errors (4xx, 5xx)
- Performance traces
- User context

**Configuration:**
```python
sentry_sdk.init(
    dsn=SENTRY_DSN,
    environment=ENVIRONMENT,  # development/staging/production
    release=f"vriddhi-matching-engine@{SERVICE_VERSION}",

    # Performance monitoring
    traces_sample_rate=0.1 if ENVIRONMENT == "production" else 1.0,
    profiles_sample_rate=0.1 if ENVIRONMENT == "production" else 1.0,

    # Integrations
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        StarletteIntegration(transaction_style="endpoint"),
    ],

    # Privacy
    send_default_pii=False,

    # Filter noise
    before_send=_filter_events,
)
```

**Event Filtering:**
```python
def _filter_events(event, hint):
    """Filter out noisy events."""
    # Don't send health check errors
    if transaction in ["/health", "/ping", "/"]:
        return None

    # Don't send 404 errors
    if status_code == 404:
        return None

    return event
```

---

### 10.3 Distributed Tracing (OpenTelemetry → Jaeger)

**Location:** `src/utils/tracing.py`

**Auto-instrumented:**
- FastAPI endpoints
- HTTP requests (external APIs)
- Logging (trace ID correlation)

**Configuration:**
```python
# Environment Variables
TRACING_ENABLED = os.getenv("TRACING_ENABLED", "false")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "vriddhi-matching-engine")
OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
```

**Custom Spans:**
```python
from src.utils.tracing import get_tracer, traced

# Decorator approach
@traced("extract-listing")
async def extract_endpoint(request):
    ...

# Context manager approach
tracer = get_tracer(__name__)
with tracer.start_as_current_span("my-operation") as span:
    span.set_attribute("user_id", user_id)
    # ... your code
```

**Graceful Degradation:**
- Returns no-op tracer if OpenTelemetry not installed
- Returns no-op tracer if `TRACING_ENABLED=false`
- Code works identically with or without tracing

---

## 11. Deployment Configuration

### 11.1 Docker Compose

```yaml
# docker-compose.yaml
services:
  web:
    build: .
    ports:
      - "${PORT}:${PORT}"
    depends_on:
      - qdrant
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_storage:/qdrant/storage

volumes:
  qdrant_storage:
```

### 11.2 Docker Compose with Jaeger

```yaml
# docker-compose.jaeger.yml
services:
  jaeger:
    image: jaegertracing/jaeger:2.0
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

### 11.3 Railway Deployment

**Procfile:**
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**railway.toml:**
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
```

### 11.4 Render Deployment

**render.yaml:**
```yaml
services:
  - type: web
    name: vriddhi-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
```

---

## 12. Environment Variables

### 12.1 Required Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `SUPABASE_URL` | PostgreSQL connection | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase API key | `eyJ...` |
| `OPENAI_API_KEY` | GPT-4o access | `sk-...` |

### 12.2 Vector Database Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `QDRANT_ENDPOINT` | Qdrant Cloud URL | - |
| `QDRANT_API_KEY` | Qdrant Cloud key | - |
| `QDRANT_HOST` | Local Qdrant host | `localhost` |
| `QDRANT_PORT` | Local Qdrant port | `6333` |

### 12.3 ML Configuration Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EMBEDDING_MODEL` | Model selection | `all-MiniLM-L6-v2` |
| `EXTRACTION_MODE` | `gpt` or `hybrid` | `gpt` |
| `SKIP_NUEXTRACT` | Skip NuExtract in hybrid | `0` |
| `USE_HYBRID_EXTRACTION` | Legacy hybrid flag | `0` |
| `USE_NEW_PIPELINE` | Canonicalization pipeline | `1` |

### 12.4 Observability Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SENTRY_ENABLED` | Enable Sentry | `false` |
| `SENTRY_DSN` | Sentry DSN | - |
| `TRACING_ENABLED` | Enable Jaeger | `false` |
| `OTLP_ENDPOINT` | Jaeger OTLP endpoint | `http://localhost:4317` |
| `OTLP_HEADERS` | OTLP auth headers | - |
| `OTEL_SERVICE_NAME` | Service name for traces | `vriddhi-matching-engine` |
| `OTEL_SERVICE_VERSION` | Service version | `2.0.0` |
| `ENVIRONMENT` | Environment name | `development` |

### 12.5 External API Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `BABELNET_API_KEY` | BabelNet access | - (optional) |

### 12.6 Server Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `PORT` | Server port | `8000` |

---

## 13. Data Flow & Algorithms

### 13.1 Complete Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         1. INPUT                                 │
│                   Natural Language Query                         │
│            "looking for a plumber in bangalore"                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    2. EXTRACTION (GPT-4o)                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Load System Prompt (GLOBAL_REFERENCE_CONTEXT.md)        │    │
│  │                        ↓                                 │    │
│  │ OpenAI API Call (gpt-4o, temperature=0, json_object)    │    │
│  │                        ↓                                 │    │
│  │ Parse JSON Response → 14-Field NEW Schema               │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   3. CANONICALIZATION                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Domain → lowercase                                       │    │
│  │ Item Type → Wikidata resolution                          │    │
│  │ Categorical → WordNet/BabelNet/Wikidata cascade         │    │
│  │ Quantities → Pint unit normalization                     │    │
│  │ Location → Nominatim geocoding                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    4. NORMALIZATION                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Field Renaming (other_party_preferences → other)        │    │
│  │ Axis Flattening ({capacity: [{type, value}]} → {type})  │    │
│  │ 14-Field NEW Schema → 12-Field OLD Schema               │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      5. RETRIEVAL                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Stage 1: SQL Filter (Supabase)                          │    │
│  │   - Filter by intent                                     │    │
│  │   - Filter by domain intersection                        │    │
│  │   - Returns: coarse candidate_ids                        │    │
│  │                        ↓                                 │    │
│  │ Stage 2: Vector Search (Qdrant)                         │    │
│  │   - Generate query embedding                             │    │
│  │   - Search with payload filters                          │    │
│  │   - Returns: ranked candidate_ids                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       6. MATCHING                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ For each candidate:                                      │    │
│  │   - Fetch from Supabase                                  │    │
│  │   - Run listing_matches_v2(query, candidate)             │    │
│  │     - Gate 1: Intent equality                            │    │
│  │     - Gate 2: SubIntent rules                            │    │
│  │     - Gate 3: Domain intersection                        │    │
│  │     - Gate 4: Items matching                             │    │
│  │     - Gate 5: Other→Self matching                        │    │
│  │     - Gate 6: Location matching                          │    │
│  │   - If all gates pass → add to matches                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       7. OUTPUT                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Store query as listing (Supabase + Qdrant)              │    │
│  │ Create match records in matches table                    │    │
│  │ Return matched_listings to client                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 Matching Algorithm Complexity

| Gate | Time Complexity | Description |
|------|-----------------|-------------|
| Intent | O(1) | String equality |
| SubIntent | O(1) | String equality/inequality |
| Domain | O(n) | Set intersection |
| Items | O(n×m) | n required items × m candidate items |
| Other→Self | O(k) | k categorical keys |
| Location | O(1) | Mode-based comparison |

**Overall Complexity:** O(n × m × k) where:
- n = number of required items
- m = number of candidate items
- k = number of categorical attributes

### 13.3 Semantic Implication Algorithm

```python
def semantic_implies(candidate_val: str, required_val: str) -> bool:
    """
    Check if candidate_val implies required_val.
    Returns True if candidate satisfies requirement.
    """
    c, r = candidate_val.lower().strip(), required_val.lower().strip()

    # 1. Exact match (O(1))
    if c == r:
        return True

    # 2. Curated synonyms (O(n) where n = synonym groups)
    for syn_group in CURATED_SYNONYMS:
        if c in syn_group and r in syn_group:
            return True

    # 3. Wikidata hierarchy (O(d) where d = max_depth)
    if wikidata.is_subclass_of(c, r, max_depth=3):
        return True

    # 4. WordNet ancestor (O(p) where p = hypernym path length)
    if resolver.is_ancestor(r, c):
        return True

    # 5. WordNet synset overlap (O(s1 × s2) where s = synsets)
    if get_synsets(c) & get_synsets(r):
        return True

    # 6. Morphological matching (O(min(len(c), len(r))))
    if common_prefix_length(c, r) >= 5:
        return True

    # 7. BabelNet synonyms (O(API call))
    if c in babelnet.get_synonyms(r) or r in babelnet.get_synonyms(c):
        return True

    return False
```

---

## 14. Codebase Discovery Summary

```
Total Files:          ~80+ Python files
Core Language:        Python 3.13
Primary Framework:    FastAPI + Uvicorn
Database:             PostgreSQL (Supabase) + Qdrant (Vector)
ML Models:            GPT-4o + Sentence-Transformers
External APIs:        Wikidata, Nominatim, Frankfurter, BabelNet

Key Components Found:
  ✅ Backend APIs (FastAPI REST endpoints)
  ✅ ML Pipeline (GPT-4o extraction + embeddings)
  ✅ Semantic Matching Engine (Multi-strategy boolean matching)
  ✅ Vector Database (Qdrant for semantic search)
  ✅ Relational Database (PostgreSQL via Supabase)
  ✅ Canonicalization Pipeline (Wikidata, WordNet, BabelNet)
  ✅ Observability (Sentry + OpenTelemetry/Jaeger)
  ✅ DevOps/CI (Docker + Railway/Render)

Lines of Code:
  - main.py: ~1,054 lines
  - Total Python: ~15,000+ lines
  - Tests: ~50+ test files
```

---

## 15. Architecture Diagrams

### 15.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│                     (Flutter Mobile / Web Browser)                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS/REST
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY                                   │
│                         FastAPI Server                                   │
│                          (main.py:77)                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Endpoints: /extract, /match, /search, /ingest, /search-and-match│    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   PROCESSING    │   │     MATCHING    │   │    RETRIEVAL    │
│    PIPELINE     │   │     ENGINE      │   │    SERVICE      │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ • Extraction    │   │ • Intent Gate   │   │ • SQL Filter    │
│ • Canonicalize  │   │ • Domain Gate   │   │ • Vector Search │
│ • Normalize     │   │ • Items Match   │   │ • Candidate IDs │
└────────┬────────┘   │ • Other→Self    │   └────────┬────────┘
         │            │ • Location      │            │
         │            └────────┬────────┘            │
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │   PostgreSQL    │ │   Qdrant    │ │  External APIs  │
    │   (Supabase)    │ │ (Vector DB) │ │                 │
    ├─────────────────┤ ├─────────────┤ ├─────────────────┤
    │ • Listings      │ │ • Embeddings│ │ • OpenAI GPT-4o │
    │ • Matches       │ │ • Payload   │ │ • Wikidata      │
    │ • Users         │ │ • Search    │ │ • Nominatim     │
    └─────────────────┘ └─────────────┘ │ • Frankfurter   │
                                        │ • BabelNet      │
                                        └─────────────────┘
```

### 15.2 Request Flow Sequence

```
Client          FastAPI         GPT-4o        Supabase        Qdrant
   │                │              │              │              │
   │ POST /search-and-match       │              │              │
   │────────────────>│             │              │              │
   │                │              │              │              │
   │                │ Extract      │              │              │
   │                │─────────────>│              │              │
   │                │              │              │              │
   │                │ JSON Schema  │              │              │
   │                │<─────────────│              │              │
   │                │              │              │              │
   │                │ Canonicalize (Wikidata/WordNet)           │
   │                │──────────────────────────────────────────>│
   │                │              │              │              │
   │                │ SQL Filter   │              │              │
   │                │─────────────────────────────>│             │
   │                │              │              │              │
   │                │ Candidate IDs│              │              │
   │                │<─────────────────────────────│             │
   │                │              │              │              │
   │                │ Vector Search│              │              │
   │                │─────────────────────────────────────────────>│
   │                │              │              │              │
   │                │ Ranked IDs   │              │              │
   │                │<─────────────────────────────────────────────│
   │                │              │              │              │
   │                │ Fetch Candidates            │              │
   │                │─────────────────────────────>│             │
   │                │              │              │              │
   │                │ Boolean Matching (local)    │              │
   │                │──────────────│              │              │
   │                │              │              │              │
   │                │ Store Matches│              │              │
   │                │─────────────────────────────>│             │
   │                │              │              │              │
   │ Matched Listings              │              │              │
   │<───────────────│              │              │              │
   │                │              │              │              │
```

---

## 16. Actionable Recommendations

### 16.1 High Priority

| Issue | Location | Recommendation |
|-------|----------|----------------|
| SQL Filter Optimization | `retrieval_service.py:135-165` | Replace Python-side filtering with PostgreSQL `?|` operator for array overlap |
| Duplicate Legacy Code | `matching/`, `schema/`, `canonicalization/` vs `src/core/` | Complete migration to `src/` structure, deprecate root modules |
| Embedding Model Loading | `main.py` startup | Implement lazy loading or warm-up endpoint |

### 16.2 Medium Priority

| Issue | Location | Recommendation |
|-------|----------|----------------|
| Rate Limiting | `/extract` endpoint | Add rate limiting for OpenAI API calls |
| Caching | External API wrappers | Add Redis cache for Wikidata/BabelNet responses |
| Batch Ingestion | `ingestion_pipeline.py` | Optimize with async/parallel writes |

### 16.3 Technical Debt

| Location | Issue | Severity |
|----------|-------|----------|
| `main.py:238-246` | Hardcoded `CURATED_SYNONYMS` | Medium |
| `retrieval_service.py:285-289` | Qdrant ID filter not implemented | Low |
| Root-level `matching/`, `schema/` | Duplicate of `src/core/` | Medium |

### 16.4 Scalability Recommendations

| Component | Concern | Mitigation |
|-----------|---------|------------|
| GPT-4o | Rate limits, latency | Batch requests, response caching |
| Qdrant | Memory for 1024D vectors | Use 384D model, collection sharding |
| Supabase | Connection pooling | PgBouncer, async queries |
| Embedding | Model load time | Pre-warm, singleton pattern |

---

## Summary

**Singletap-Backend** is a sophisticated semantic matching engine that combines:

1. **GPT-4o** for natural language understanding
2. **Multi-source ontology resolution** (Wikidata, WordNet, BabelNet)
3. **Vector embeddings** for semantic similarity search
4. **Boolean constraint matching** for precise filtering
5. **Comprehensive observability** (Sentry, Jaeger, structlog)

The architecture follows a clear pipeline:

```
Extract → Canonicalize → Normalize → Retrieve → Match → Store
```

Each stage is optimized for its specific task, with fallback mechanisms and caching to ensure reliability and performance.

---

**Architecture Grade: A-**

| Aspect | Assessment |
|--------|------------|
| Code Quality | Good - modular, well-documented |
| Test Coverage | Unit + Integration + Feature tests present |
| Deployment Readiness | Production-ready (Docker, PaaS configs) |
| Observability | Excellent (Sentry + Jaeger + structlog) |
| Scalability | Medium - needs SQL optimization, caching |
| Security | API key management via env vars |

---

*Generated by Principal Architect Analysis*
*Singletap-Backend v2.0 | February 16, 2026*
