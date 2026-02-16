from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
import uuid
import json
from openai import OpenAI
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# EXTRACTION MODE CONFIGURATION
# ============================================================================
# Two extraction architectures available:
#
# 1. GPT-ONLY (default): Uses GPT-4o-mini for extraction
#    - Fast (~5-15s per query)
#    - 100% accuracy on test cases
#    - Set: EXTRACTION_MODE=gpt (or leave unset)
#
# 2. HYBRID (GPT + NuExtract): GPT extracts, NuExtract validates
#    - Slower (~45-60s on CPU, ~10s with GPU)
#    - Adds schema validation layer
#    - Set: EXTRACTION_MODE=hybrid
#    - Requires: Ollama running with nuextract model
#
# Optional: Skip NuExtract validation in hybrid mode
#    - SKIP_NUEXTRACT=1 runs hybrid extractor but skips Level 2
#    - Useful for testing or when Ollama is unavailable
#
# Legacy flag (backward compatible):
#    USE_HYBRID_EXTRACTION=1 is equivalent to EXTRACTION_MODE=hybrid
#
# Examples:
#    EXTRACTION_MODE=gpt                    # GPT only (default)
#    EXTRACTION_MODE=hybrid                 # GPT + NuExtract validation
#    EXTRACTION_MODE=hybrid SKIP_NUEXTRACT=1  # Hybrid extractor, skip validation
# ============================================================================

EXTRACTION_MODE = os.environ.get("EXTRACTION_MODE", "gpt").lower()
SKIP_NUEXTRACT = os.environ.get("SKIP_NUEXTRACT", "0").lower() in ("1", "true", "yes")

# Backward compatibility: USE_HYBRID_EXTRACTION=1 enables hybrid mode
if os.environ.get("USE_HYBRID_EXTRACTION", "0").lower() in ("1", "true", "yes"):
    EXTRACTION_MODE = "hybrid"

USE_HYBRID_EXTRACTION = (EXTRACTION_MODE == "hybrid")

# Import structured logging
from src.utils.logging import get_logger, configure_structlog

# Import distributed tracing
from src.utils.tracing import init_tracing, shutdown_tracing, get_tracer, traced

# Import error tracking
from src.utils.sentry import init_sentry

# Configure structlog (can set json_output=True for production)
configure_structlog(json_output=False, log_level="INFO")
log = get_logger(__name__)

# Import project modules
from schema.schema_normalizer_v2 import normalize_and_validate_v2
from pipeline.ingestion_pipeline import IngestionClients, ingest_listing
from pipeline.retrieval_service import RetrievalClients, retrieve_candidates
from matching.listing_matcher_v2 import listing_matches_v2
from embedding.embedding_builder import build_embedding_text
from canonicalization.orchestrator import canonicalize_listing

# Import hybrid extractor (optional - used when USE_HYBRID_EXTRACTION=1)
if USE_HYBRID_EXTRACTION:
    from src.core.extraction.hybrid_extractor import HybridExtractor

app = FastAPI(title="Vriddhi Matching Engine API", version="2.0")

# Global clients
ingestion_clients = IngestionClients()
retrieval_clients = RetrievalClients()
openai_client = None
extraction_prompt = None
hybrid_extractor = None  # Used when USE_HYBRID_EXTRACTION=1
is_initialized = False
init_error = None

# Load extraction prompt
def load_extraction_prompt():
    """Load the extraction prompt from file."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompt", "GLOBAL_REFERENCE_CONTEXT.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.warning("Could not load extraction prompt", emoji="warning", error=str(e))
        return None

# Initialize OpenAI client
def initialize_openai():
    """Initialize OpenAI client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return OpenAI(api_key=api_key)
    else:
        log.warning("OPENAI_API_KEY not set. Extraction endpoint will not work.", emoji="warning")
        return None

async def initialize_services():
    """Run initialization in a background thread to allow instant server startup."""
    global is_initialized, init_error, openai_client, extraction_prompt, hybrid_extractor
    log.info("Starting background initialization...", emoji="loading")
    if USE_HYBRID_EXTRACTION:
        mode_desc = "GPT + NuExtract validation" if not SKIP_NUEXTRACT else "Hybrid (NuExtract skipped)"
    else:
        mode_desc = "GPT only"
    log.info("Extraction mode configured", emoji="config",
             EXTRACTION_MODE=EXTRACTION_MODE,
             SKIP_NUEXTRACT=SKIP_NUEXTRACT if USE_HYBRID_EXTRACTION else "N/A",
             mode_description=mode_desc)
    log.info("Environment check", emoji="config",
             SUPABASE_URL="SET" if os.environ.get("SUPABASE_URL") else "NOT SET",
             OPENAI_API_KEY="SET" if os.environ.get("OPENAI_API_KEY") else "NOT SET")

    try:
        # Initialize OpenAI client (fast, non-blocking)
        log.info("Initializing OpenAI client...", emoji="db")
        openai_client = initialize_openai()
        log.info("OpenAI client ready", emoji="success")

        # Load extraction prompt (fast, non-blocking)
        log.info("Loading extraction prompt...", emoji="doc")
        extraction_prompt = load_extraction_prompt()
        log.info("Extraction prompt loaded", emoji="success",
                 chars=len(extraction_prompt) if extraction_prompt else 0)

        # Initialize hybrid extractor if enabled
        if USE_HYBRID_EXTRACTION:
            mode_desc = "GPT + NuExtract" if not SKIP_NUEXTRACT else "GPT only (NuExtract skipped)"
            log.info(f"Initializing HybridExtractor ({mode_desc})...", emoji="sync")
            hybrid_extractor = HybridExtractor(skip_nuextract=SKIP_NUEXTRACT)
            if hybrid_extractor.initialize():
                log.info("HybridExtractor initialized", emoji="success",
                         skip_nuextract=SKIP_NUEXTRACT)
            else:
                log.warning("HybridExtractor initialization failed, falling back to GPT-only", emoji="warning")
                hybrid_extractor = None

        if os.environ.get("SUPABASE_URL"):
            # Run heavy init calls in a separate thread
            log.info("Initializing ingestion clients (in background)...", emoji="sync")
            await asyncio.to_thread(ingestion_clients.initialize)
            log.info("Ingestion clients initialized", emoji="success")

            log.info("Initializing retrieval clients (in background)...", emoji="sync")
            await asyncio.to_thread(retrieval_clients.initialize)
            log.info("Retrieval clients initialized", emoji="success")

            # Initialize OntologyStore with Supabase client (loads persisted concepts)
            log.info("Initializing OntologyStore...", emoji="sync")
            from canonicalization.ontology_store import get_ontology_store
            ontology_store = get_ontology_store()
            ontology_store.initialize(ingestion_clients.supabase)
            data = ontology_store.load_from_db()
            # Inject persisted ontology into the resolver
            from canonicalization.orchestrator import _get_categorical_resolver
            resolver = _get_categorical_resolver()
            resolver._synonym_registry.update(data.get("synonym_registry", {}))
            resolver._concept_paths.update(data.get("concept_paths", {}))
            log.info("OntologyStore initialized", emoji="success",
                     synonyms=len(data.get("synonym_registry", {})),
                     paths=len(data.get("concept_paths", {})))

            is_initialized = True
            log.info("ALL clients initialized successfully", emoji="success")
        else:
            log.warning("SUPABASE_URL not set. Skipping database/vector clients.", emoji="warning")
            is_initialized = True  # Mark as initialized for extraction endpoints
            log.info("Server ready (extraction-only mode)", emoji="success")
    except Exception as e:
        init_error = str(e)
        log.error("Error initializing clients", emoji="error", error=str(e), exc_info=True)

@app.on_event("startup")
async def startup_event():
    """Start server immediately, run initialization in background."""
    log.info("FastAPI server starting...", emoji="start")
    log.info("Server should be available", emoji="location",
             port=os.environ.get("PORT", "8000"))

    # Initialize Sentry error tracking (should be first!)
    init_sentry()

    # Initialize distributed tracing (Jaeger/Grafana via OpenTelemetry)
    init_tracing(app)
    log.info("Observability initialized (Sentry + Tracing)", emoji="trace")

    # Start initialization as a fire-and-forget background task
    asyncio.create_task(initialize_services())
    log.info("Server startup complete (initialization running in background)", emoji="success")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    log.info("FastAPI server shutting down...", emoji="stop")
    shutdown_tracing()
    log.info("Server shutdown complete", emoji="success")

def check_service_health():
    """Helper to check if services are ready."""
    if init_error:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {init_error}")
    if not is_initialized:
        raise HTTPException(status_code=503, detail="Service is still starting up (loading models). Please try again in 30 seconds.")

def semantic_implies(candidate_val: str, required_val: str) -> bool:
    """
    Check if candidate_val implies required_val.

    Uses multiple strategies:
    1. Exact match (after canonicalization with BabelNet enrichment)
    1.5. Curated synonyms (laptop/notebook, cleaning/housekeeping)
    2. WordNet hierarchy check (is required_val an ancestor?)
    2.5. WordNet synset overlap (true synonyms)
    3. Morphological matching (same stem - plumber/plumbing)
    4. BabelNet exact synonym check

    With BabelNet enrichment during canonicalization, synonyms like
    tutor/coach should already have the same concept_id.
    """
    c, r = candidate_val.lower().strip(), required_val.lower().strip()
    if c == r:
        return True

    # Strategy 1.5: Curated synonyms (common synonyms not in same WordNet synset)
    # These are semantically identical but WordNet has them in different synsets
    CURATED_SYNONYMS = {
        frozenset({"laptop", "notebook"}),
        frozenset({"cleaning", "housekeeping", "housework"}),
        frozenset({"couch", "sofa"}),
        frozenset({"automobile", "car", "auto"}),
        frozenset({"phone", "telephone", "cellphone", "mobile"}),
        frozenset({"apartment", "flat"}),
    }
    for syn_group in CURATED_SYNONYMS:
        if c in syn_group and r in syn_group:
            return True

    # Strategy 1.6: Wikidata hierarchy check (dynamic, not hardcoded)
    # Uses P31 (instance of) and P279 (subclass of) to check if candidate is a type of required
    # Example: dentist is a type of doctor, iphone is a type of smartphone
    try:
        from services.external.wikidata_wrapper import get_wikidata_client
        wikidata = get_wikidata_client()
        if wikidata.is_subclass_of(c, r, max_depth=3):
            return True
    except Exception:
        # Wikidata may timeout or fail - continue to other strategies
        pass

    # Strategy 2: WordNet hierarchy check (is required_val an ancestor of candidate_val?)
    try:
        from canonicalization.orchestrator import _get_categorical_resolver
        resolver = _get_categorical_resolver()
        if resolver.is_ancestor(r, c):
            return True
    except Exception:
        pass

    # Strategy 2.5: WordNet synonym check (are they in the same synset?)
    # Handles cases like laptop/notebook, cleaning/housekeeping
    try:
        from nltk.corpus import wordnet as wn
        c_synsets = set(wn.synsets(c.replace(" ", "_")))
        r_synsets = set(wn.synsets(r.replace(" ", "_")))
        # Check if they share any synset (true synonyms)
        if c_synsets & r_synsets:
            return True
        # Check if candidate is a lemma in any of required's synsets
        for syn in r_synsets:
            lemma_names = {lem.name().lower().replace("_", " ") for lem in syn.lemmas()}
            if c in lemma_names:
                return True
        # Check if required is a lemma in any of candidate's synsets
        for syn in c_synsets:
            lemma_names = {lem.name().lower().replace("_", " ") for lem in syn.lemmas()}
            if r in lemma_names:
                return True
    except Exception:
        pass

    # Strategy 3: Morphological matching (shared root)
    # Handles cases like plumber/plumbing, cleaning/cleaner
    try:
        # Get the first word of each
        c_word = c.split()[0]
        r_word = r.split()[0]

        # Check if one is a prefix of the other (min 4 chars)
        min_len = min(len(c_word), len(r_word))
        if min_len >= 4:
            # Find longest common prefix
            common_prefix = ""
            for i in range(min_len):
                if c_word[i] == r_word[i]:
                    common_prefix += c_word[i]
                else:
                    break
            # If common prefix is at least 5 chars (e.g., "plumb" from plumber/plumbing)
            if len(common_prefix) >= 5:
                return True

        # Also check WordNet derivationally related forms
        from nltk.corpus import wordnet as wn
        c_synsets = wn.synsets(c_word)
        r_synsets = wn.synsets(r_word)
        if c_synsets and r_synsets:
            # Check if they share any derivationally related lemmas
            c_derivations = set()
            for syn in c_synsets[:2]:
                for lemma in syn.lemmas():
                    for df in lemma.derivationally_related_forms():
                        c_derivations.add(df.name().lower())
            for syn in r_synsets[:2]:
                for lemma in syn.lemmas():
                    if lemma.name().lower() in c_derivations:
                        return True
    except Exception:
        pass

    # Strategy 4: BabelNet EXACT synonym check
    # Only matches if candidate is an EXACT synonym of required
    # (no partial word matching to avoid false positives like "doctor" matching "dental doctor")
    try:
        from services.external.babelnet_wrapper import get_babelnet_client
        import os
        api_key = os.getenv("BABELNET_API_KEY", "")
        if api_key and len(c) >= 3 and len(r) >= 3:
            bn = get_babelnet_client()

            # Check if candidate appears as exact synonym of required
            r_synonyms = bn.get_synonyms(r)
            r_synonyms_lower = [s.lower().strip() for s in r_synonyms]
            if c in r_synonyms_lower:
                return True

            # Check if required appears as exact synonym of candidate
            c_synonyms = bn.get_synonyms(c)
            c_synonyms_lower = [s.lower().strip() for s in c_synonyms]
            if r in c_synonyms_lower:
                return True
    except Exception:
        pass

    return False

class ListingRequest(BaseModel):
    listing: Dict[str, Any]

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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "initialized": is_initialized,
        "service": "Vriddhi Matching Engine V2"
    }

@app.get("/health")
def health_check():
    """Simple health check for Render - responds immediately"""
    return {"status": "ok"}

@app.get("/ping")
def ping():
    """Ultra-simple ping endpoint"""
    return "pong"

@app.post("/ingest")
async def ingest_endpoint(request: ListingRequest):
    check_service_health()
    try:
        # 1. Canonicalize
        canonical_listing = canonicalize_listing(request.listing)

        # 2. Normalize
        listing_old = normalize_and_validate_v2(canonical_listing)

        # 3. Ingest
        listing_id, _ = ingest_listing(ingestion_clients, listing_old, verbose=True)
        
        return {
            "status": "success",
            "listing_id": listing_id,
            "message": "Listing normalized and ingested successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_endpoint(request: ListingRequest, limit: int = 10):
    check_service_health()
    try:
        # 1. Normalize
        listing_old = normalize_and_validate_v2(request.listing)

        # 2. Retrieve
        candidate_ids = retrieve_candidates(retrieval_clients, listing_old, limit=limit, verbose=True)

        return {
            "status": "success",
            "count": len(candidate_ids),
            "candidates": candidate_ids
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Error in /search endpoint", emoji="error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/match")
async def match_endpoint(request: MatchRequest):
    check_service_health()
    try:
        # 1. Normalize
        listing_a_old = normalize_and_validate_v2(request.listing_a)
        listing_b_old = normalize_and_validate_v2(request.listing_b)
        
        # 2. Match with semantic implication
        is_match = listing_matches_v2(listing_a_old, listing_b_old, implies_fn=semantic_implies)
        
        return {
            "status": "success",
            "match": is_match,
            "details": "Semantic match successful" if is_match else "No match found"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/normalize")
async def normalize_endpoint(request: ListingRequest):
    """
    Helper endpoint to just normalize a listing (NEW -> OLD) without ingesting.
    """
    try:
        listing_old = normalize_and_validate_v2(request.listing)
        return {"status": "success", "normalized_listing": listing_old}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================================
# NEW: GPT EXTRACTION ENDPOINTS
# ============================================================================

def extract_from_query(query: str) -> Dict[str, Any]:
    """
    Extract structured NEW schema from natural language query.

    Uses hybrid extraction (GPT + NuExtract) when USE_HYBRID_EXTRACTION=1,
    otherwise uses GPT-only extraction.

    Args:
        query: Natural language query (e.g., "need a plumber who speaks kannada")

    Returns:
        Structured NEW schema dictionary

    Raises:
        HTTPException: If extraction fails
    """
    # Use hybrid extractor if available and enabled
    if USE_HYBRID_EXTRACTION and hybrid_extractor:
        try:
            log.info("Using hybrid extraction (GPT + NuExtract)", emoji="hybrid")
            result = hybrid_extractor.extract(query)
            if result.success and result.final_json:
                log.info("Hybrid extraction success", emoji="success",
                         fallback_used=result.fallback_used,
                         total_ms=f"{result.total_latency_ms:.0f}")
                return result.final_json
            else:
                log.warning("Hybrid extraction failed, falling back to GPT-only", emoji="warning",
                            error=result.gpt_error or result.nuextract_error)
                # Fall through to GPT-only extraction
        except Exception as e:
            log.warning("Hybrid extraction error, falling back to GPT-only", emoji="warning", error=str(e))
            # Fall through to GPT-only extraction

    # GPT-only extraction (default or fallback)
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API not configured. Set OPENAI_API_KEY environment variable."
        )

    if not extraction_prompt:
        raise HTTPException(
            status_code=500,
            detail="Extraction prompt not loaded. Check prompt/GLOBAL_REFERENCE_CONTEXT.md exists."
        )

    try:
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        # Parse response
        output_text = response.choices[0].message.content
        extracted_data = json.loads(output_text)

        return extracted_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.post("/extract")
async def extract_endpoint(request: QueryRequest):
    """
    NEW ENDPOINT: Extract structured schema from natural language query.

    Input: Natural language query
    Output: Structured NEW schema (14 fields, axis-based)

    Example:
        POST /extract
        {
            "query": "need a plumber who speaks kannada"
        }

        Returns:
        {
            "status": "success",
            "query": "need a plumber who speaks kannada",
            "extracted_listing": {
                "intent": "service",
                "subintent": "seek",
                "domain": ["construction & trades"],
                "items": [{"type": "plumbing", ...}],
                "other_party_preferences": {
                    "categorical": {"language": "kannada"},
                    ...
                },
                ...
            }
        }
    """
    try:
        extracted_listing = extract_from_query(request.query)

        return {
            "status": "success",
            "query": request.query,
            "extracted_listing": extracted_listing
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-and-normalize")
async def extract_and_normalize_endpoint(request: QueryRequest):
    """
    NEW ENDPOINT: Extract from natural language, then normalize to OLD schema.

    This combines:
    1. GPT extraction (natural language -> NEW schema)
    2. Schema normalization (NEW schema -> OLD schema)

    Input: Natural language query
    Output: OLD schema format ready for matching
    """
    try:
        # Step 1: Extract NEW schema
        extracted_listing = extract_from_query(request.query)

        # Step 2: Canonicalize
        canonical_listing_data = canonicalize_listing(extracted_listing)

        # Step 3: Normalize to OLD schema
        normalized_listing = normalize_and_validate_v2(canonical_listing_data)

        return {
            "status": "success",
            "query": request.query,
            "extracted_listing": extracted_listing,
            "normalized_listing": normalized_listing
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-and-match")
async def extract_and_match_endpoint(request: DualQueryRequest):
    """
    NEW ENDPOINT: Extract from TWO natural language queries and match them.

    Complete pipeline:
    1. Extract listing A from query_a (GPT)
    2. Extract listing B from query_b (GPT)
    3. Normalize both (NEW -> OLD)
    4. Match them (semantic matching)

    Input: Two natural language queries
    Output: Match result (true/false) with details

    Example:
        POST /extract-and-match
        {
            "query_a": "need a plumber who speaks kannada",
            "query_b": "I am a plumber, I speak kannada and english"
        }

        Returns:
        {
            "status": "success",
            "query_a": "...",
            "query_b": "...",
            "match": true,
            "details": "Semantic match successful"
        }
    """
    check_service_health()
    try:
        # Step 1: Extract both queries
        extracted_a = extract_from_query(request.query_a)
        extracted_b = extract_from_query(request.query_b)

        # Step 2: Canonicalize both
        canonical_a = canonicalize_listing(extracted_a)
        canonical_b = canonicalize_listing(extracted_b)

        # Step 3: Normalize both
        listing_a_old = normalize_and_validate_v2(canonical_a)
        listing_b_old = normalize_and_validate_v2(canonical_b)

        # Step 3: Match with semantic implication
        is_match = listing_matches_v2(listing_a_old, listing_b_old, implies_fn=semantic_implies)

        return {
            "status": "success",
            "query_a": request.query_a,
            "query_b": request.query_b,
            "extracted_a": extracted_a,
            "extracted_b": extracted_b,
            "normalized_a": listing_a_old,
            "normalized_b": listing_b_old,
            "match": is_match,
            "details": "Semantic match successful" if is_match else "No match found"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NEW: SEARCH AND MATCH + STORE LISTING ENDPOINTS
# ============================================================================

@app.post("/search-and-match")
async def search_and_match_endpoint(request: SearchAndMatchRequest):
    """
    NEW ENDPOINT: Complete search and match flow with history storage.

    Flow:
    1. Extract structured JSON from natural language query (GPT)
    2. Search database for matching listings (Qdrant + SQL)
    3. Boolean match each candidate (listing_matches_v2)
    4. Store EVERYTHING in matches table (query + results)
    5. Return matches and query_json

    This endpoint ALWAYS stores search history (even if 0 matches found).

    Input:
        - query: Natural language query
        - user_id: User performing the search

    Output:
        - match_id: UUID of matches table entry
        - query_text: Original query
        - query_json: GPT extracted JSON
        - has_matches: True/False
        - match_count: Number of matches
        - matched_listings: Full details of matched listings
    """
    check_service_health()

    try:
        # Step 1: GPT Extraction
        log.info("Search and Match request", emoji="search",
                 user_id=request.user_id, query=request.query)

        extracted_json = extract_from_query(request.query)

        # Step 2: Canonicalize
        canonical_json = canonicalize_listing(extracted_json)

        # Step 3: Normalize
        normalized_query = normalize_and_validate_v2(canonical_json)

        # Step 4: Search database for candidates
        log.info("Searching database...", emoji="filter")
        candidate_ids = retrieve_candidates(
            retrieval_clients,
            normalized_query,
            limit=100,
            verbose=True
        )

        log.info("Found candidates", emoji="data", count=len(candidate_ids))

        # Step 4: Boolean match each candidate
        matched_listings = []
        matched_user_ids = []
        matched_listing_ids = []

        if candidate_ids:
            # Fetch candidates from Supabase
            intent = normalized_query.get("intent")
            table_name = f"{intent}_listings"

            log.info("Fetching candidates from table", emoji="search", table=table_name)

            for listing_id in candidate_ids:
                try:
                    # Fetch from Supabase
                    response = ingestion_clients.supabase.table(table_name).select("*").eq("id", listing_id).execute()

                    if response.data and len(response.data) > 0:
                        candidate_row = response.data[0]
                        candidate_data = candidate_row["data"]
                        candidate_user_id = candidate_row.get("user_id")

                        # Boolean match
                        is_match = listing_matches_v2(
                            normalized_query,
                            candidate_data,
                            implies_fn=semantic_implies
                        )

                        if is_match:
                            matched_listings.append({
                                "listing_id": listing_id,
                                "user_id": candidate_user_id,
                                "data": candidate_data
                            })
                            if candidate_user_id:
                                matched_user_ids.append(candidate_user_id)
                            matched_listing_ids.append(listing_id)

                except Exception as e:
                    log.warning("Error fetching/matching listing", emoji="warning",
                                listing_id=listing_id, error=str(e))
                    continue

        # Step 5: Store query as a listing and create match records
        has_matches = len(matched_listings) > 0
        match_count = len(matched_listings)

        # Auto-store the query as a listing to get a listing_a_id
        query_listing_id, _ = ingest_listing(ingestion_clients, normalized_query, user_id=request.user_id, verbose=True)
        log.info("Query stored as listing", emoji="success", listing_id=query_listing_id)

        # Insert one match record per matched listing
        match_ids = []
        if has_matches:
            log.info("Storing match records...", emoji="store", count=match_count)
            for matched in matched_listings:
                match_row = {
                    "listing_a_id": query_listing_id,
                    "listing_b_id": matched["listing_id"],
                    "user_a_id": request.user_id,
                    "user_b_id": matched.get("user_id") or request.user_id,
                    "match_score": 1.0,
                    "match_type": normalized_query.get("intent", "service"),
                    "is_bidirectional": False,
                    "status": "pending"
                }
                try:
                    resp = ingestion_clients.supabase.table("matches").insert(match_row).execute()
                    if resp.data:
                        match_ids.append(resp.data[0]["match_id"])
                except Exception as e:
                    log.warning("Error storing match record", emoji="warning", error=str(e))
            log.info("Stored match records", emoji="success", count=len(match_ids))

        return {
            "status": "success",
            "listing_id": query_listing_id,
            "match_ids": match_ids,
            "query_text": request.query,
            "query_json": extracted_json,
            "has_matches": has_matches,
            "match_count": match_count,
            "matched_listings": matched_listings,
            "message": f"Found {match_count} matches" if has_matches else "No matches found. Your listing has been stored for future matching."
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error in search-and-match", emoji="error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search-and-match-direct")
async def search_and_match_direct_endpoint(request: StoreListingRequest):
    """
    TESTING ENDPOINT: Complete search and match flow with pre-formatted JSON (bypasses GPT).

    Flow:
    1. Accept pre-formatted JSON directly (skip GPT extraction)
    2. Search database for matching listings (Qdrant + SQL)
    3. Boolean match each candidate (listing_matches_v2)
    4. Return matches (does NOT store search history)

    This endpoint is for testing only - bypasses GPT extraction.

    Input:
        - listing_json: Complete listing JSON (NEW schema format)
        - user_id: User performing the search

    Output:
        - has_matches: True/False
        - match_count: Number of matches
        - matches: List of matched user_ids or listing objects
    """
    check_service_health()

    try:
        # Step 1: Canonicalize + Normalize (skip GPT extraction)
        canonical_query = canonicalize_listing(request.listing_json)
        normalized_query = normalize_and_validate_v2(canonical_query)

        # Step 2: Search database for candidates
        candidate_ids = retrieve_candidates(
            retrieval_clients,
            normalized_query,
            limit=100,
            verbose=False
        )

        # Step 3: Boolean match each candidate
        matched_listings = []
        matched_user_ids = []
        seen_user_ids = set()  # Track unique user_ids to avoid duplicates

        intent = normalized_query.get("intent")
        table_name = f"{intent}_listings"

        for listing_id in candidate_ids:
            try:
                # Fetch candidate listing from database
                response = ingestion_clients.supabase.table(table_name).select("*").eq("id", listing_id).execute()

                if response.data and len(response.data) > 0:
                    row = response.data[0]
                    candidate_data = row.get("data")
                    candidate_user_id = row.get("user_id")

                    # Skip if we've already matched this user
                    if candidate_user_id in seen_user_ids:
                        continue

                    # Run boolean match
                    is_match = listing_matches_v2(normalized_query, candidate_data, implies_fn=semantic_implies)

                    if is_match:
                        matched_listings.append({
                            "listing_id": listing_id,
                            "user_id": candidate_user_id,
                            "data": candidate_data
                        })
                        if candidate_user_id:
                            matched_user_ids.append(candidate_user_id)
                            seen_user_ids.add(candidate_user_id)  # Mark as seen

            except Exception as e:
                log.warning("Error fetching/matching listing", emoji="warning",
                            listing_id=listing_id, error=str(e))
                continue

        has_matches = len(matched_listings) > 0
        match_count = len(matched_listings)

        return {
            "status": "success",
            "has_matches": has_matches,
            "match_count": match_count,
            "matches": matched_user_ids,  # Return user_ids for compatibility with test
            "matched_listings": matched_listings
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error in search-and-match-direct", emoji="error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/store-listing")
async def store_listing_endpoint(request: StoreListingRequest):
    """
    Store listing in database for future matching.

    Flow:
    1. GPT Extraction (natural language -> structured JSON)
    2. Canonicalize (units, currency, ontology)
    3. Normalize to OLD format
    4. Store in appropriate listings table (with user_id and optional match_id)
    5. Generate embedding
    6. Store embedding in Qdrant
    7. Return listing_id and extracted_json

    This endpoint ONLY stores. It does NOT search or match.

    Input:
        - query: Natural language query
        - user_id: User who owns this listing
        - match_id: Optional reference to matches table (if from search)

    Output:
        - listing_id: UUID of stored listing
        - extracted_json: GPT-extracted structured JSON
        - intent: Product/Service/Mutual
        - message: Confirmation
    """
    check_service_health()

    try:
        log.info("Store Listing request", emoji="store", user_id=request.user_id, query=request.query)

        # Step 1: GPT Extraction (natural language -> structured JSON)
        extracted_json = extract_from_query(request.query)
        log.info("GPT extraction complete", emoji="success", intent=extracted_json.get("intent"))

        # Step 2: Canonicalize and normalize
        canonical_store = canonicalize_listing(extracted_json)
        normalized_listing = normalize_and_validate_v2(canonical_store)

        # Step 2: Ingest (stores in Supabase + Qdrant)
        listing_id = str(uuid.uuid4())

        # Get intent for table selection
        intent = normalized_listing.get("intent")
        if not intent:
            raise ValueError("Listing missing 'intent' field")

        table_name = f"{intent}_listings"

        # Prepare data with user_id and match_id
        data = {
            "id": listing_id,
            "user_id": request.user_id,
            "match_id": request.match_id,
            "data": normalized_listing
        }

        log.info("Storing in table...", emoji="db", table=table_name)
        ingestion_clients.supabase.table(table_name).insert(data).execute()
        log.info("Stored in Supabase", emoji="success", listing_id=listing_id)

        # Step 3: Generate and store embedding in Qdrant
        embedding_text = build_embedding_text(normalized_listing)
        embedding = ingestion_clients.embedding_model.encode(embedding_text).tolist()

        # Select Qdrant collection
        collection_name = f"{intent}_vectors"

        # Build payload
        payload = {
            "listing_id": listing_id,
            "intent": intent
        }

        if intent in ["product", "service"]:
            payload["domain"] = normalized_listing.get("domain", [])
        elif intent == "mutual":
            payload["category"] = normalized_listing.get("category", [])

        # Store in Qdrant
        from qdrant_client.models import PointStruct
        point = PointStruct(
            id=listing_id,
            vector=embedding,
            payload=payload
        )

        log.info("Storing embedding in collection...", emoji="vector", collection=collection_name)
        ingestion_clients.qdrant.upsert(
            collection_name=collection_name,
            points=[point]
        )
        log.info("Stored in Qdrant", emoji="success")

        return {
            "status": "success",
            "listing_id": listing_id,
            "user_id": request.user_id,
            "query": request.query,
            "extracted_json": extracted_json,
            "intent": intent,
            "match_id": request.match_id,
            "message": f"Listing stored successfully. It will be visible to future searches."
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error in store-listing", emoji="error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
