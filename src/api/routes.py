"""
API Routes for Vriddhi Matching Engine V2.

All FastAPI endpoints for the matching engine.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
import numpy as np

# Import from new modular structure
from src.core.schema import normalize_and_validate_v2
from src.core.matching import listing_matches_v2
from src.core.extraction import extract_from_query
from src.core.canonicalization import canonicalize_listing
from src.services.embedding import build_embedding_text
from src.services.retrieval import retrieve_candidates
from src.config.clients import db_clients

# Import legacy ingestion function (will be refactored later)
from ingestion_pipeline import ingest_listing

# Create router
router = APIRouter()

# Global state (managed by main.py startup)
_openai_client = None
_extraction_prompt = None
_is_initialized = False
_init_error = None
_ontology_resolver = None


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def set_global_state(openai_client, extraction_prompt, is_initialized, init_error):
    """Set global state from main.py startup"""
    global _openai_client, _extraction_prompt, _is_initialized, _init_error
    _openai_client = openai_client
    _extraction_prompt = extraction_prompt
    _is_initialized = is_initialized
    _init_error = init_error


def set_ontology_resolver(resolver):
    """Set global ontology resolver from main.py startup"""
    global _ontology_resolver
    _ontology_resolver = resolver


def get_global_state():
    """Get current global state"""
    return {
        "openai_client": _openai_client,
        "extraction_prompt": _extraction_prompt,
        "is_initialized": _is_initialized,
        "init_error": _init_error
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_service_health():
    """Helper to check if services are ready."""
    if _init_error:
        raise HTTPException(
            status_code=500,
            detail=f"Service initialization failed: {_init_error}"
        )
    if not _is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Service is still starting up (loading models). Please try again in 30 seconds."
        )


def semantic_implies(candidate_val, required_val) -> bool:
    """
    Enhanced semantic implication with ontology awareness.

    Resolution order:
    1. Exact match
    2. Ontology resolver (hierarchical/antonym detection)
    3. Fallback to embedding similarity

    Args:
        candidate_val: Value from candidate (str or ontology dict)
        required_val: Required value (str or ontology dict)

    Returns:
        True if candidate implies or matches required, False otherwise

    Examples:
        >>> semantic_implies("chicken", "non-veg")
        True  # chicken implies non-veg (via ontology)

        >>> semantic_implies("veg", "non-veg")
        False  # incompatible (via ontology)
    """
    # Extract concept_id from ontology dicts if needed
    if isinstance(candidate_val, dict):
        candidate_val = candidate_val.get("concept_id", str(candidate_val))
    if isinstance(required_val, dict):
        required_val = required_val.get("concept_id", str(required_val))
    # Ensure strings
    candidate_val = str(candidate_val)
    required_val = str(required_val)

    # Exact match
    if candidate_val.lower() == required_val.lower():
        return True

    # Try ontology resolver first
    if _ontology_resolver:
        satisfied, reason = _ontology_resolver.check_value_satisfies_requirement(
            candidate_val, required_val
        )

        # If ontology has a definitive answer (not "unrelated"), use it
        if "unrelated" not in reason:
            return satisfied

    # Fallback to embedding similarity
    if not db_clients.embedding_model:
        return False

    v1 = db_clients.embedding_model.encode(candidate_val)
    v2 = db_clients.embedding_model.encode(required_val)

    sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return float(sim) > 0.82


def extract_with_gpt(query: str) -> Dict[str, Any]:
    """
    Extract structured NEW schema from natural language query using GPT-4o.

    Uses global state for openai_client and extraction_prompt.
    """
    if not _openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API not configured. Set OPENAI_API_KEY environment variable."
        )

    if not _extraction_prompt:
        raise HTTPException(
            status_code=500,
            detail="Extraction prompt not loaded. Check prompt/GLOBAL_REFERENCE_CONTEXT.md exists."
        )

    try:
        return extract_from_query(
            query=query,
            openai_client=_openai_client,
            extraction_prompt=_extraction_prompt
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# ============================================================================
# REQUEST MODELS
# ============================================================================

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
    listing_json: Dict[str, Any]
    user_id: str
    match_id: Optional[str] = None


# ============================================================================
# BASIC ENDPOINTS
# ============================================================================

@router.get("/")
def read_root():
    """Root endpoint - API status"""
    return {
        "status": "online",
        "initialized": _is_initialized,
        "service": "Vriddhi Matching Engine V2"
    }


@router.get("/health")
def health_check():
    """Simple health check for Render - responds immediately"""
    return {"status": "ok"}


@router.get("/ping")
def ping():
    """Ultra-simple ping endpoint"""
    return "pong"


# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@router.post("/ingest")
async def ingest_endpoint(request: ListingRequest):
    """Ingest a listing (normalize + store in DB + Qdrant)"""
    check_service_health()
    try:
        # 1. Canonicalize (units, currency, ontology)
        canonical = canonicalize_listing(request.listing)

        # 2. Normalize
        listing_old = normalize_and_validate_v2(canonical)

        # 3. Ingest (using legacy function for now)
        listing_id, _ = ingest_listing(db_clients, listing_old, verbose=True)

        return {
            "status": "success",
            "listing_id": listing_id,
            "message": "Listing normalized and ingested successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_endpoint(request: ListingRequest, limit: int = 10):
    """Search for candidate listings"""
    check_service_health()
    try:
        # 1. Canonicalize (units, currency, ontology)
        canonical = canonicalize_listing(request.listing)

        # 2. Normalize
        listing_old = normalize_and_validate_v2(canonical)

        # 3. Retrieve
        candidate_ids = retrieve_candidates(
            db_clients,
            listing_old,
            limit=limit,
            verbose=True
        )

        return {
            "status": "success",
            "count": len(candidate_ids),
            "candidates": candidate_ids
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error in /search endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match")
async def match_endpoint(request: MatchRequest):
    """Match two listings"""
    check_service_health()
    try:
        # 1. Canonicalize (units, currency, ontology)
        canonical_a = canonicalize_listing(request.listing_a)
        canonical_b = canonicalize_listing(request.listing_b)

        # 2. Normalize
        listing_a_old = normalize_and_validate_v2(canonical_a)
        listing_b_old = normalize_and_validate_v2(canonical_b)

        # 3. Match with semantic implication and ontology resolver
        is_match = listing_matches_v2(
            listing_a_old,
            listing_b_old,
            implies_fn=semantic_implies,
            ontology_resolver=_ontology_resolver
        )

        return {
            "status": "success",
            "match": is_match,
            "details": "Semantic match successful" if is_match else "No match found"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/normalize")
async def normalize_endpoint(request: ListingRequest):
    """Helper endpoint to just normalize a listing (NEW -> OLD) without ingesting"""
    try:
        listing_old = normalize_and_validate_v2(request.listing)
        return {"status": "success", "normalized_listing": listing_old}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# GPT EXTRACTION ENDPOINTS
# ============================================================================

@router.post("/extract")
async def extract_endpoint(request: QueryRequest):
    """
    Extract structured schema from natural language query.

    Input: Natural language query
    Output: Structured NEW schema (14 fields, axis-based)
    """
    try:
        extracted_listing = extract_with_gpt(request.query)

        return {
            "status": "success",
            "query": request.query,
            "extracted_listing": extracted_listing
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-and-normalize")
async def extract_and_normalize_endpoint(request: QueryRequest):
    """
    Extract from natural language, canonicalize, then normalize to OLD schema.

    Pipeline:
    1. GPT extraction (natural language -> NEW schema)
    2. Canonicalization (NEW schema -> Canonical NEW schema)
    3. Schema normalization (Canonical NEW -> OLD schema)
    """
    try:
        # Step 1: Extract NEW schema
        extracted_listing = extract_with_gpt(request.query)

        # Step 2: Canonicalize (resolve non-deterministic values)
        canonical_listing = canonicalize_listing(extracted_listing)

        # Step 3: Normalize to OLD schema
        normalized_listing = normalize_and_validate_v2(canonical_listing)

        return {
            "status": "success",
            "query": request.query,
            "extracted_listing": extracted_listing,
            "canonical_listing": canonical_listing,
            "normalized_listing": normalized_listing
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-and-match")
async def extract_and_match_endpoint(request: DualQueryRequest):
    """
    Extract from TWO natural language queries, canonicalize, and match them.

    Complete pipeline:
    1. Extract listing A from query_a (GPT)
    2. Extract listing B from query_b (GPT)
    3. Canonicalize both (resolve non-deterministic values)
    4. Normalize both (Canonical NEW -> OLD)
    5. Match them (semantic matching)
    """
    check_service_health()
    try:
        # Step 1: Extract both queries
        extracted_a = extract_with_gpt(request.query_a)
        extracted_b = extract_with_gpt(request.query_b)

        # Step 2: Canonicalize both
        canonical_a = canonicalize_listing(extracted_a)
        canonical_b = canonicalize_listing(extracted_b)

        # Step 3: Normalize both
        listing_a_old = normalize_and_validate_v2(canonical_a)
        listing_b_old = normalize_and_validate_v2(canonical_b)

        # Step 3: Match with semantic implication and ontology resolver
        is_match = listing_matches_v2(
            listing_a_old,
            listing_b_old,
            implies_fn=semantic_implies,
            ontology_resolver=_ontology_resolver
        )

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
# SEARCH AND MATCH ENDPOINTS
# ============================================================================

@router.post("/search-and-match")
async def search_and_match_endpoint(request: SearchAndMatchRequest):
    """
    Complete search and match flow with history storage.

    Flow:
    1. Extract structured JSON from natural language query (GPT)
    2. Search database for matching listings (Qdrant + SQL)
    3. Boolean match each candidate (listing_matches_v2)
    4. Store EVERYTHING in matches table (query + results)
    5. Return matches and query_json

    This endpoint ALWAYS stores search history (even if 0 matches found).
    """
    check_service_health()

    try:
        # Step 1: GPT Extraction
        print(f"\n🔍 Search and Match for user: {request.user_id}")
        print(f"📝 Query: {request.query}")

        extracted_json = extract_with_gpt(request.query)

        # Step 2: Canonicalize (units, currency, ontology)
        canonical_json = canonicalize_listing(extracted_json)

        # Step 3: Normalize
        normalized_query = normalize_and_validate_v2(canonical_json)

        # Step 3: Search database for candidates
        print(f"🔎 Searching database...")
        candidate_ids = retrieve_candidates(
            db_clients,
            normalized_query,
            limit=100,
            verbose=True
        )

        print(f"📊 Found {len(candidate_ids)} candidates")

        # Step 4: Boolean match each candidate
        matched_listings = []
        matched_user_ids = []
        matched_listing_ids = []

        if candidate_ids:
            # Fetch candidates from Supabase
            intent = normalized_query.get("intent")
            table_name = f"{intent}_listings"

            print(f"🔍 Fetching candidates from {table_name}...")

            for listing_id in candidate_ids:
                try:
                    # Fetch from Supabase
                    response = db_clients.supabase.table(table_name).select("*").eq("id", listing_id).execute()

                    if response.data and len(response.data) > 0:
                        candidate_row = response.data[0]
                        candidate_data = candidate_row["data"]
                        candidate_user_id = candidate_row.get("user_id")

                        # Boolean match with ontology resolver
                        is_match = listing_matches_v2(
                            normalized_query,
                            candidate_data,
                            implies_fn=semantic_implies,
                            ontology_resolver=_ontology_resolver
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
                    print(f"⚠️ Error fetching/matching listing {listing_id}: {e}")
                    continue

        # Step 5: Store in matches table
        match_id = str(uuid.uuid4())
        has_matches = len(matched_listings) > 0
        match_count = len(matched_listings)

        matches_data = {
            "match_id": match_id,
            "query_user_id": request.user_id,
            "query_text": request.query,
            "query_json": extracted_json,
            "has_matches": has_matches,
            "match_count": match_count,
            "matched_user_ids": matched_user_ids,
            "matched_listing_ids": matched_listing_ids
        }

        print(f"💾 Storing search history in matches table...")
        try:
            db_clients.supabase.table("matches").insert(matches_data).execute()
            print(f"✅ Stored with match_id: {match_id}")
        except Exception as history_err:
            print(f"⚠️ Could not store search history (non-fatal): {history_err}")
            # Search results are still returned even if history storage fails

        return {
            "status": "success",
            "match_id": match_id,
            "query_text": request.query,
            "query_json": extracted_json,
            "has_matches": has_matches,
            "match_count": match_count,
            "matched_listings": matched_listings,
            "message": f"Found {match_count} matches" if has_matches else "No matches found. You can store your query for future matching."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in search-and-match: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-and-match-direct")
async def search_and_match_direct_endpoint(request: StoreListingRequest):
    """
    TESTING ENDPOINT: Complete search and match flow with pre-formatted JSON (bypasses GPT).

    Flow:
    1. Accept pre-formatted JSON directly (skip GPT extraction)
    2. Search database for matching listings (Qdrant + SQL)
    3. Boolean match each candidate (listing_matches_v2)
    4. Return matches (does NOT store search history)

    This endpoint is for testing only - bypasses GPT extraction.
    """
    check_service_health()

    try:
        # Step 1: Canonicalize (units, currency, ontology)
        canonical = canonicalize_listing(request.listing_json)

        # Step 2: Normalize (skip GPT extraction)
        normalized_query = normalize_and_validate_v2(canonical)

        # Step 3: Search database for candidates
        candidate_ids = retrieve_candidates(
            db_clients,
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
            
                response = db_clients.supabase.table(table_name).select("*").eq("id", listing_id).execute()

                if response.data and len(response.data) > 0:
                    row = response.data[0]
                    candidate_data = row.get("data")
                    candidate_user_id = row.get("user_id")

                    # Skip if we've already matched this user
                    if candidate_user_id in seen_user_ids:
                        continue

                    # Run boolean match with ontology resolver
                    is_match = listing_matches_v2(
                        normalized_query,
                        candidate_data,
                        implies_fn=semantic_implies,
                        ontology_resolver=_ontology_resolver
                    )

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
                print(f"⚠️ Error fetching/matching listing {listing_id}: {e}")
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
        print(f"❌ Error in search-and-match-direct: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store-listing")
async def store_listing_endpoint(request: StoreListingRequest):
    """
    Store listing in database for future matching.

    Flow:
    1. Validate listing JSON
    2. Normalize to OLD format
    3. Store in appropriate listings table (with user_id and optional match_id)
    4. Generate embedding
    5. Store embedding in Qdrant
    6. Return listing_id

    This endpoint ONLY stores. It does NOT search or match.
    """
    check_service_health()

    try:
        print(f"\n💾 Store Listing for user: {request.user_id}")

        # Step 1: Canonicalize (units, currency, ontology)
        canonical_listing = canonicalize_listing(request.listing_json)

        # Step 2: Validate and normalize
        normalized_listing = normalize_and_validate_v2(canonical_listing)

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

        print(f"📝 Storing in {table_name}...")
        db_clients.supabase.table(table_name).insert(data).execute()
        print(f"✅ Stored in Supabase with listing_id: {listing_id}")

        # Step 3: Generate and store embedding in Qdrant
        embedding_text = build_embedding_text(normalized_listing)
        embedding = db_clients.embedding_model.encode(embedding_text).tolist()

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

        print(f"🔢 Storing embedding in {collection_name}...")
        db_clients.qdrant.upsert(
            collection_name=collection_name,
            points=[point]
        )
        print(f"✅ Stored in Qdrant")

        return {
            "status": "success",
            "listing_id": listing_id,
            "user_id": request.user_id,
            "intent": intent,
            "match_id": request.match_id,
            "message": f"Listing stored successfully. It will be visible to future searches."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in store-listing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
