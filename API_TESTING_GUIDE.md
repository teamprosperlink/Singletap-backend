# Singletap Backend API Testing Guide

**Base URL:** `https://singletap-backend.onrender.com`

**Last Tested:** 2026-02-23

---

## Table of Contents
1. [Health Check Endpoints](#1-health-check-endpoints)
2. [Core Listing Operations](#2-core-listing-operations)
3. [GPT Extraction Endpoints](#3-gpt-extraction-endpoints)
4. [Advanced Search & Match Endpoints](#4-advanced-search--match-endpoints)
5. [Testing Endpoints](#5-testing-endpoints)
6. [Schema Reference](#6-schema-reference)
7. [Test Cases with Expected Results](#7-test-cases-with-expected-results)

---

## 1. Health Check Endpoints

### GET `/`
**Description:** Root health check
**Response:**
```json
{
  "status": "online",
  "initialized": true,
  "service": "Vriddhi Matching Engine V2"
}
```

### GET `/health`
**Description:** Simple health check for load balancers
**Response:**
```json
{
  "status": "ok"
}
```

### GET `/ping`
**Description:** Ultra-simple ping endpoint
**Response:**
```
"pong"
```

---

## 2. Core Listing Operations

### POST `/normalize`
**Description:** Transform NEW schema to OLD schema format without storing
**Content-Type:** `application/json`

**Request Body:**
```json
{
  "listing": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple"},
        "max": {"cost": [{"type": "cost", "value": 50000, "unit": "INR"}]}
      }
    ],
    "target_location": {"name": "Mumbai"},
    "location_match_mode": "near_me",
    "reasoning": "Looking for an iPhone"
  }
}
```

**Actual Response:**
```json
{
  "status": "success",
  "normalized_listing": {
    "intent": "product",
    "subintent": "buy",
    "reasoning": "Looking for an iPhone",
    "domain": ["electronics"],
    "category": [""],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple"},
        "min": {},
        "max": {"cost": 50000},
        "range": {}
      }
    ],
    "itemexclusions": [],
    "locationexclusions": [],
    "other": {
      "categorical": {},
      "min": {},
      "max": {},
      "range": {},
      "otherexclusions": []
    },
    "self": {
      "categorical": {},
      "min": {},
      "max": {},
      "range": {},
      "selfexclusions": []
    },
    "location": "mumbai",
    "locationmode": "near_me"
  }
}
```

---

### POST `/ingest`
**Description:** Canonicalize, normalize, and store listing in database
**Required Fields:** `listing`, `user_id` (must be UUID format)

**Request Body:**
```json
{
  "listing": {
    "intent": "product",
    "subintent": "sell",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple", "model": "iPhone 14"},
        "min": {"cost": [{"type": "cost", "value": 45000, "unit": "INR"}]}
      }
    ],
    "target_location": {"name": "Delhi"},
    "location_match_mode": "near_me",
    "reasoning": "Selling my iPhone 14"
  },
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "status": "success",
  "listing_id": "uuid-string",
  "message": "Listing ingested successfully"
}
```

---

### POST `/search`
**Description:** Search for candidate listings
**Query Parameters:** `limit` (default: 10)

**Request Body:**
```json
{
  "listing": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple"}
      }
    ]
  }
}
```

**Response:**
```json
{
  "status": "success",
  "count": 5,
  "candidates": [
    {
      "id": "listing-uuid",
      "score": 0.95,
      "listing": {...}
    }
  ]
}
```

---

### POST `/match`
**Description:** Match two listings with semantic implication

**Request Body:**
```json
{
  "listing_a": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple"},
        "max": {"cost": [{"type": "cost", "value": 80000, "unit": "INR"}]}
      }
    ],
    "target_location": {"name": "Mumbai"},
    "location_match_mode": "near_me"
  },
  "listing_b": {
    "intent": "product",
    "subintent": "sell",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Apple", "model": "iPhone 14"},
        "min": {"cost": [{"type": "cost", "value": 60000, "unit": "INR"}]}
      }
    ],
    "target_location": {"name": "Mumbai"},
    "location_match_mode": "near_me"
  }
}
```

**Actual Response (Match Found):**
```json
{
  "status": "success",
  "match": true,
  "details": "Semantic match successful"
}
```

**Actual Response (No Match):**
```json
{
  "status": "success",
  "match": false,
  "details": "No match found"
}
```

---

## 3. GPT Extraction Endpoints

### POST `/extract`
**Description:** Extract structured schema from natural language query

**Request Body:**
```json
{
  "query": "I want to buy an iPhone 15 under 90000 in Delhi"
}
```

**Actual Response:**
```json
{
  "status": "success",
  "query": "I want to buy an iPhone 15 under 90000 in Delhi",
  "extracted_listing": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["technology & electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"model": "iphone 15"},
        "max": {"cost": [{"type": "price", "value": 90000, "unit": "local"}]}
      }
    ],
    "target_location": {"name": "delhi"},
    "location_match_mode": "explicit",
    "location_exclusions": [],
    "reasoning": "The query was classified as a product purchase because the user is seeking to buy a tangible item..."
  }
}
```

---

### POST `/extract` (Roommate/Mutual Query)
**Request Body:**
```json
{
  "query": "Looking for a female roommate in Bangalore, non-smoker preferred"
}
```

**Actual Response:**
```json
{
  "status": "success",
  "query": "Looking for a female roommate in Bangalore, non-smoker preferred",
  "extracted_listing": {
    "intent": "mutual",
    "subintent": "connect",
    "domain": ["real estate & property"],
    "primary_mutual_category": ["roommates"],
    "items": [],
    "item_exclusions": [],
    "other_party_preferences": {
      "identity": [{"type": "gender", "value": "female"}],
      "habits": {"smoking": "no"}
    },
    "self_attributes": {},
    "self_exclusions": [],
    "target_location": {"name": "bangalore"},
    "location_match_mode": "explicit",
    "location_exclusions": [],
    "reasoning": "The query was classified as a mutual intent because it involves finding a roommate..."
  }
}
```

---

### POST `/extract-and-normalize`
**Description:** Extract from NLP, then transform to OLD schema

**Request Body:**
```json
{
  "query": "Renting out 3BHK apartment in Whitefield for 45000 per month"
}
```

**Actual Response:**
```json
{
  "status": "success",
  "query": "Renting out 3BHK apartment in Whitefield for 45000 per month",
  "extracted_listing": {
    "intent": "product",
    "subintent": "sell",
    "domain": ["real estate & property"],
    "items": [
      {
        "type": "apartment",
        "categorical": {"bedrooms": 3, "location": "whitefield"},
        "range": {"cost": [{"type": "rent", "min": 45000, "max": 45000, "unit": "local"}]}
      }
    ],
    "target_location": {"name": "whitefield"},
    "location_match_mode": "explicit",
    "location_exclusions": [],
    "reasoning": "..."
  },
  "normalized_listing": {
    "intent": "product",
    "subintent": "sell",
    "reasoning": "...",
    "domain": ["real estate & property"],
    "category": [""],
    "items": [
      {
        "type": "apartment",
        "categorical": {"bedrooms": 3, "location": "whitefield"},
        "min": {},
        "max": {},
        "range": {"rent": [45000, 45000]}
      }
    ],
    "itemexclusions": [],
    "locationexclusions": [],
    "other": {"categorical": {}, "min": {}, "max": {}, "range": {}, "otherexclusions": []},
    "self": {"categorical": {}, "min": {}, "max": {}, "range": {}, "selfexclusions": []},
    "location": "whitefield",
    "locationmode": "explicit"
  }
}
```

---

### POST `/extract-and-match`
**Description:** Extract from two queries and match them

**Request Body:**
```json
{
  "query_a": "I want to buy a laptop under 60000",
  "query_b": "Selling HP laptop for 55000"
}
```

**Actual Response:**
```json
{
  "status": "success",
  "query_a": "I want to buy a laptop under 60000",
  "query_b": "Selling HP laptop for 55000",
  "extracted_a": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["technology & electronics"],
    "items": [{"type": "laptop", "max": {"cost": [{"type": "price", "value": 60000, "unit": "local"}]}}],
    "item_exclusions": [],
    "other_party_preferences": {},
    "self_attributes": {},
    "target_location": {},
    "location_match_mode": "near_me",
    "location_exclusions": [],
    "reasoning": "..."
  },
  "extracted_b": {
    "intent": "product",
    "subintent": "sell",
    "domain": ["technology & electronics"],
    "items": [{"type": "laptop", "categorical": {"brand": "hp"}, "range": {"cost": [{"type": "price", "min": 55000, "max": 55000, "unit": "local"}]}}],
    "item_exclusions": [],
    "other_party_preferences": {},
    "self_attributes": {},
    "target_location": {},
    "location_match_mode": "near_me",
    "location_exclusions": [],
    "reasoning": "..."
  },
  "normalized_a": {...},
  "normalized_b": {...},
  "match": true,
  "details": "Semantic match successful"
}
```

---

## 4. Advanced Search & Match Endpoints

### POST `/search-and-match`
**Description:** Complete pipeline - extract -> search -> match -> store
**Required Fields:** `query`, `user_id` (MUST be UUID format)

**Request Body:**
```json
{
  "query": "Looking for a 2BHK flat for rent in Koramangala under 30000 per month",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Actual Response:**
```json
{
  "status": "success",
  "listing_id": "50f7a3ae-0e1f-40ca-9fdf-1cd7b6320526",
  "match_ids": [],
  "query_text": "Looking for a 2BHK flat for rent in Koramangala under 30000 per month",
  "query_json": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["real estate & property"],
    "items": [
      {
        "type": "apartment",
        "categorical": {"bedrooms": 2},
        "max": {"cost": [{"type": "rent", "value": 30000, "unit": "local"}]}
      }
    ],
    "target_location": {"name": "koramangala"},
    "location_match_mode": "explicit",
    "location_exclusions": [],
    "reasoning": "..."
  },
  "has_matches": false,
  "match_count": 0,
  "matched_listings": [],
  "similar_matching_enabled": true,
  "similar_count": 0,
  "similar_listings": [],
  "message": "No matches found. Your listing has been stored for future matching."
}
```

**Error Response (Invalid user_id):**
```json
{
  "detail": "Supabase insertion failed for product_listings: {'message': 'invalid input syntax for type uuid: \"invalid_id\"', 'code': '22P02', 'hint': None, 'details': None}"
}
```

---

### POST `/search-and-match-direct`
**Description:** Search/match with pre-formatted JSON (bypasses GPT)

**Request Body:**
```json
{
  "listing_json": {
    "intent": "product",
    "subintent": "buy",
    "domain": ["Electronics"],
    "items": [
      {
        "type": "smartphone",
        "categorical": {"brand": "Samsung"}
      }
    ]
  },
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "status": "success",
  "has_matches": true,
  "match_count": 3,
  "matches": ["uuid-1", "uuid-2", "uuid-3"],
  "matched_listings": [...]
}
```

---

### POST `/store-listing`
**Description:** Store listing with GPT extraction + embedding generation
**Required Fields:** `query`, `user_id` (MUST be UUID format)

**Request Body:**
```json
{
  "query": "I am a yoga instructor offering private sessions in South Delhi",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "match_id": null
}
```

**Actual Response:**
```json
{
  "status": "success",
  "listing_id": "03a4d09a-e17b-4aef-ad20-5fcddc00968c",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "query": "I am a yoga instructor offering private sessions in South Delhi",
  "extracted_json": {
    "intent": "service",
    "subintent": "provide",
    "domain": ["alternative & holistic health"],
    "items": [{"type": "yoga"}],
    "other_party_preferences": {},
    "self_attributes": {
      "identity": [{"type": "profession", "value": "yoga instructor"}]
    },
    "target_location": {"name": "south delhi"},
    "location_match_mode": "explicit",
    "location_exclusions": [],
    "reasoning": "..."
  },
  "intent": "service",
  "match_id": null,
  "message": "Listing stored successfully. It will be visible to future searches."
}
```

---

## 5. Testing Endpoints

### POST `/test-message-generation`
**Description:** Test smart message generation (template vs LLM)

**Request Body:**
```json
{
  "unsatisfied_constraints": [
    {"field": "budget", "expected": 50000, "actual": 65000}
  ],
  "bonus_attributes": {
    "warranty": "2 years"
  },
  "use_llm": false
}
```

**Response:**
```json
{
  "template_message": "...",
  "llm_message": "...",
  "input": {...},
  "config": {...}
}
```

---

### GET `/test-similar-matching`
**Description:** View similar matching configuration

**Response:**
```json
{
  "config": {
    "enabled": true,
    "min_score": 0.70,
    "max_results": 10
  },
  "test_cases": [...],
  "sample_messages": [...]
}
```

---

## 6. Schema Reference

### Extracted Schema Fields (GPT Output)

| Field | Type | Description |
|-------|------|-------------|
| `intent` | string | `"product"`, `"service"`, `"mutual"` |
| `subintent` | string | `"buy"`, `"sell"`, `"seek"`, `"provide"`, `"connect"` |
| `domain` | array | Domain categories (lowercase) e.g., `["technology & electronics"]` |
| `primary_mutual_category` | array | For mutual intents only, e.g., `["roommates"]` |
| `items` | array | List of item objects |
| `item_exclusions` | array | Items to exclude |
| `other_party_preferences` | object | Preferences about the other party |
| `self_attributes` | object | Attributes about self |
| `self_exclusions` | array | Self exclusions |
| `target_location` | object | `{"name": "location_name"}` (lowercase) |
| `location_match_mode` | string | `"near_me"`, `"explicit"`, `"target_only"`, `"route"`, `"global"` |
| `location_exclusions` | array | Locations to exclude |
| `reasoning` | string | Explanation paragraph |

### Normalized Schema Fields (After normalization)

| Field | Type | Description |
|-------|------|-------------|
| `intent` | string | Same as extracted |
| `subintent` | string | Same as extracted |
| `reasoning` | string | Same as extracted |
| `domain` | array | Lowercase domain |
| `category` | array | Category array |
| `items` | array | Normalized items with simplified cost (number instead of array) |
| `itemexclusions` | array | Item exclusions |
| `locationexclusions` | array | Location exclusions |
| `other` | object | `{categorical, min, max, range, otherexclusions}` |
| `self` | object | `{categorical, min, max, range, selfexclusions}` |
| `location` | string | Location name (lowercase string, not object) |
| `locationmode` | string | Location match mode |

### Item Object Structure (Extracted)

```json
{
  "type": "smartphone",
  "categorical": {
    "brand": "apple",
    "model": "iphone 15"
  },
  "min": {
    "cost": [{"type": "price", "value": 10000, "unit": "local"}]
  },
  "max": {
    "cost": [{"type": "price", "value": 50000, "unit": "local"}]
  },
  "range": {
    "cost": [{"type": "rent", "min": 30000, "max": 45000, "unit": "local"}]
  }
}
```

### Item Object Structure (Normalized)

```json
{
  "type": "smartphone",
  "categorical": {"brand": "apple"},
  "min": {},
  "max": {"cost": 50000},
  "range": {"rent": [30000, 45000]}
}
```

### Common Domains (lowercase)
- `"technology & electronics"`
- `"real estate & property"`
- `"alternative & holistic health"`
- `"home services"`
- `"professional services"`

---

## 7. Test Cases with Expected Results

### Test Case 1: Health Check
```bash
curl -X GET "https://singletap-backend.onrender.com/ping"
```
**Expected:** `"pong"`

---

### Test Case 2: Root Health Check
```bash
curl -X GET "https://singletap-backend.onrender.com/"
```
**Expected:**
```json
{"status":"online","initialized":true,"service":"Vriddhi Matching Engine V2"}
```

---

### Test Case 3: Extract iPhone Query
```bash
curl -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "I want to buy an iPhone 15 under 90000 in Delhi"}'
```
**Expected Result:**
- `status`: `"success"`
- `extracted_listing.intent`: `"product"`
- `extracted_listing.subintent`: `"buy"`
- `extracted_listing.domain`: `["technology & electronics"]`
- `extracted_listing.items[0].type`: `"smartphone"`
- `extracted_listing.target_location.name`: `"delhi"` (lowercase)
- `extracted_listing.location_match_mode`: `"explicit"`

---

### Test Case 4: Extract Roommate Query (Mutual Intent)
```bash
curl -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Looking for a female roommate in Bangalore, non-smoker preferred"}'
```
**Expected Result:**
- `intent`: `"mutual"`
- `subintent`: `"connect"`
- `primary_mutual_category`: `["roommates"]`
- `other_party_preferences.identity`: contains `{"type": "gender", "value": "female"}`
- `other_party_preferences.habits.smoking`: `"no"`

---

### Test Case 5: Extract Service Provider
```bash
curl -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "I am a yoga instructor offering private sessions in South Delhi"}'
```
**Expected Result:**
- `intent`: `"service"`
- `subintent`: `"provide"`
- `domain`: `["alternative & holistic health"]`
- `self_attributes.identity`: contains profession info

---

### Test Case 6: Match Buyer and Seller (Should Match)
```bash
curl -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "max": {"cost": [{"type": "cost", "value": 80000, "unit": "INR"}]}}],
      "target_location": {"name": "Mumbai"},
      "location_match_mode": "near_me"
    },
    "listing_b": {
      "intent": "product",
      "subintent": "sell",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple", "model": "iPhone 14"}, "min": {"cost": [{"type": "cost", "value": 60000, "unit": "INR"}]}}],
      "target_location": {"name": "Mumbai"},
      "location_match_mode": "near_me"
    }
  }'
```
**Expected:**
```json
{"status":"success","match":true,"details":"Semantic match successful"}
```

---

### Test Case 7: Match Buyer and Seller (Should NOT Match - Budget Too Low)
```bash
curl -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "max": {"cost": [{"type": "cost", "value": 40000, "unit": "INR"}]}}]
    },
    "listing_b": {
      "intent": "product",
      "subintent": "sell",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "min": {"cost": [{"type": "cost", "value": 60000, "unit": "INR"}]}}]
    }
  }'
```
**Expected:**
```json
{"status":"success","match":false,"details":"No match found"}
```

---

### Test Case 8: Store Listing (Requires UUID)
```bash
curl -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Selling Samsung Galaxy S23 for 55000 in Hyderabad",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```
**Expected:**
- `status`: `"success"`
- `listing_id`: UUID string
- `intent`: `"product"`
- `message`: `"Listing stored successfully..."`

---

### Test Case 9: Search and Match (Requires UUID)
```bash
curl -X POST "https://singletap-backend.onrender.com/search-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Want to buy a Samsung phone under 60000 in Hyderabad",
    "user_id": "550e8400-e29b-41d4-a716-446655440001"
  }'
```
**Expected:**
- `status`: `"success"`
- `listing_id`: UUID string
- `has_matches`: boolean
- `match_count`: number
- `similar_matching_enabled`: boolean
- `message`: string

---

### Test Case 10: Extract and Normalize
```bash
curl -X POST "https://singletap-backend.onrender.com/extract-and-normalize" \
  -H "Content-Type: application/json" \
  -d '{"query": "Renting out 3BHK apartment in Whitefield for 45000 per month"}'
```
**Expected Result:**
- `extracted_listing.intent`: `"product"`
- `extracted_listing.subintent`: `"sell"`
- `normalized_listing.location`: `"whitefield"` (lowercase string)
- `normalized_listing.locationmode`: `"explicit"`

---

### Test Case 11: Extract and Match Two Queries
```bash
curl -X POST "https://singletap-backend.onrender.com/extract-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query_a": "I want to buy a laptop under 60000",
    "query_b": "Selling HP laptop for 55000"
  }'
```
**Expected:**
- `match`: `true`
- `details`: `"Semantic match successful"`
- `extracted_a` and `extracted_b` contain the parsed listings
- `normalized_a` and `normalized_b` contain the normalized versions

---

## Quick Reference: cURL Commands

```bash
# Health check
curl https://singletap-backend.onrender.com/ping

# Root status
curl https://singletap-backend.onrender.com/

# Extract query
curl -X POST https://singletap-backend.onrender.com/extract \
  -H "Content-Type: application/json" \
  -d '{"query": "your query here"}'

# Extract and normalize
curl -X POST https://singletap-backend.onrender.com/extract-and-normalize \
  -H "Content-Type: application/json" \
  -d '{"query": "your query here"}'

# Match two listings
curl -X POST https://singletap-backend.onrender.com/match \
  -H "Content-Type: application/json" \
  -d '{"listing_a": {...}, "listing_b": {...}}'

# Extract and match two queries
curl -X POST https://singletap-backend.onrender.com/extract-and-match \
  -H "Content-Type: application/json" \
  -d '{"query_a": "buyer query", "query_b": "seller query"}'

# Store listing (UUID required)
curl -X POST https://singletap-backend.onrender.com/store-listing \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "user_id": "550e8400-e29b-41d4-a716-446655440000"}'

# Full search and match (UUID required)
curl -X POST https://singletap-backend.onrender.com/search-and-match \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "user_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

---

## Error Responses

**Validation Error (Invalid UUID):**
```json
{
  "detail": "Supabase insertion failed for product_listings: {'message': 'invalid input syntax for type uuid: \"invalid_id\"', 'code': '22P02', 'hint': None, 'details': None}"
}
```

**Missing Required Field:**
```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

Common HTTP Status Codes:
- `200`: Success
- `400`: Bad Request (missing/invalid parameters)
- `422`: Validation Error (schema mismatch, invalid UUID)
- `500`: Internal Server Error

---

## Important Notes

1. **UUID Requirement:** Endpoints that store data (`/store-listing`, `/search-and-match`, `/ingest`) require `user_id` to be a valid UUID format (e.g., `550e8400-e29b-41d4-a716-446655440000`)

2. **Lowercase Values:** Extracted domains and locations are returned in lowercase (e.g., `"technology & electronics"`, `"delhi"`)

3. **GPT Extraction:** Endpoints using `/extract`, `/search-and-match`, `/store-listing` require OpenAI API calls and may take 2-5 seconds

4. **Direct Endpoints:** Use `/match` or `/extract-and-match` for testing without database storage (faster)

5. **Match Response:** The `details` field is a string message, not an object

6. **Similar Matching:** The `/search-and-match` endpoint returns additional fields for similar matching: `similar_matching_enabled`, `similar_count`, `similar_listings`

---

## 8. Complete Curl Scripts (Copy-Paste Ready)

### Health Check Scripts

```bash
# ============================================
# HEALTH CHECK ENDPOINTS
# ============================================

# 1. Ping endpoint
curl -s "https://singletap-backend.onrender.com/ping"
# Expected: "pong"

# 2. Health endpoint
curl -s "https://singletap-backend.onrender.com/health"
# Expected: {"status":"ok"}

# 3. Root endpoint
curl -s "https://singletap-backend.onrender.com/"
# Expected: {"status":"online","initialized":true,"service":"Vriddhi Matching Engine V2"}
```

---

### Extract Endpoint Scripts

```bash
# ============================================
# /extract - Natural Language to Schema
# ============================================

# 1. Product Buy Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "I want to buy an iPhone 15 under 90000 in Delhi"}'

# 2. Product Sell Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Selling my MacBook Pro M2 for 1.2 lakhs in Bangalore"}'

# 3. Mutual/Roommate Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Looking for a female roommate in Bangalore, non-smoker preferred, budget 15000"}'

# 4. Service Provider Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "I am a yoga instructor offering private sessions in South Delhi, 500 per session"}'

# 5. Service Seeker Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Need a plumber for bathroom renovation in Mumbai, budget 20000"}'

# 6. Real Estate Rental Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Looking for a 2BHK flat for rent in Koramangala under 30000 per month"}'

# 7. Vehicle Query
curl -s -X POST "https://singletap-backend.onrender.com/extract" \
  -H "Content-Type: application/json" \
  -d '{"query": "Want to buy a used Honda City 2020 model under 8 lakhs in Pune"}'
```

---

### Extract and Normalize Scripts

```bash
# ============================================
# /extract-and-normalize - Extract + Transform to Old Schema
# ============================================

# 1. Apartment Rental
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-normalize" \
  -H "Content-Type: application/json" \
  -d '{"query": "Renting out 3BHK apartment in Whitefield for 45000 per month"}'

# 2. Electronics Sale
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-normalize" \
  -H "Content-Type: application/json" \
  -d '{"query": "Selling Samsung 65 inch Smart TV for 60000 in Chennai"}'

# 3. Professional Service
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-normalize" \
  -H "Content-Type: application/json" \
  -d '{"query": "CA offering tax filing services starting 5000 rupees in Delhi NCR"}'
```

---

### Match Endpoint Scripts

```bash
# ============================================
# /match - Match Two Listings
# ============================================

# 1. Smartphone Buyer-Seller Match (Should MATCH - budget >= price)
curl -s -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "max": {"cost": [{"type": "cost", "value": 80000, "unit": "INR"}]}}],
      "target_location": {"name": "Mumbai"},
      "location_match_mode": "near_me"
    },
    "listing_b": {
      "intent": "product",
      "subintent": "sell",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple", "model": "iPhone 14"}, "min": {"cost": [{"type": "cost", "value": 60000, "unit": "INR"}]}}],
      "target_location": {"name": "Mumbai"},
      "location_match_mode": "near_me"
    }
  }'
# Expected: {"status":"success","match":true,"details":"Semantic match successful"}

# 2. Budget Too Low (Should NOT MATCH)
curl -s -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "max": {"cost": [{"type": "cost", "value": 40000, "unit": "INR"}]}}]
    },
    "listing_b": {
      "intent": "product",
      "subintent": "sell",
      "domain": ["Electronics"],
      "items": [{"type": "smartphone", "categorical": {"brand": "Apple"}, "min": {"cost": [{"type": "cost", "value": 60000, "unit": "INR"}]}}]
    }
  }'
# Expected: {"status":"success","match":false,"details":"No match found"}

# 3. Laptop Buyer-Seller Match
curl -s -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["technology & electronics"],
      "items": [{"type": "laptop", "max": {"cost": [{"type": "price", "value": 70000, "unit": "local"}]}}],
      "location_match_mode": "near_me"
    },
    "listing_b": {
      "intent": "product",
      "subintent": "sell",
      "domain": ["technology & electronics"],
      "items": [{"type": "laptop", "categorical": {"brand": "dell"}, "min": {"cost": [{"type": "price", "value": 55000, "unit": "local"}]}}],
      "location_match_mode": "near_me"
    }
  }'

# 4. Service Seeker-Provider Match
curl -s -X POST "https://singletap-backend.onrender.com/match" \
  -H "Content-Type: application/json" \
  -d '{
    "listing_a": {
      "intent": "service",
      "subintent": "seek",
      "domain": ["home services"],
      "items": [{"type": "plumbing"}],
      "target_location": {"name": "mumbai"},
      "location_match_mode": "explicit"
    },
    "listing_b": {
      "intent": "service",
      "subintent": "provide",
      "domain": ["home services"],
      "items": [{"type": "plumbing"}],
      "target_location": {"name": "mumbai"},
      "location_match_mode": "explicit"
    }
  }'
```

---

### Extract and Match Scripts

```bash
# ============================================
# /extract-and-match - Extract Two Queries and Match
# ============================================

# 1. Laptop Buyer vs Seller
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query_a": "I want to buy a laptop under 60000",
    "query_b": "Selling HP laptop for 55000"
  }'
# Expected: match = true

# 2. Service Seeker vs Provider
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query_a": "Need a CA for tax filing, budget 10000",
    "query_b": "Chartered Accountant offering tax services starting 8000"
  }'

# 3. Phone Buyer vs Seller (Different Brands - may not match)
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query_a": "Want to buy an iPhone under 80000",
    "query_b": "Selling Samsung Galaxy S23 for 70000"
  }'

# 4. Roommate Matching
curl -s -X POST "https://singletap-backend.onrender.com/extract-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query_a": "Looking for a female roommate in Bangalore, budget 15000",
    "query_b": "Female looking for a roommate in Bangalore, rent 12000"
  }'
```

---

### Normalize Endpoint Scripts

```bash
# ============================================
# /normalize - Transform NEW Schema to OLD Schema
# ============================================

# 1. Simple Product Listing
curl -s -X POST "https://singletap-backend.onrender.com/normalize" \
  -H "Content-Type: application/json" \
  -d '{
    "listing": {
      "intent": "product",
      "subintent": "buy",
      "domain": ["Electronics"],
      "items": [
        {
          "type": "smartphone",
          "categorical": {"brand": "Apple"},
          "max": {"cost": [{"type": "cost", "value": 50000, "unit": "INR"}]}
        }
      ],
      "target_location": {"name": "Mumbai"},
      "location_match_mode": "near_me",
      "reasoning": "Looking for an iPhone"
    }
  }'

# 2. Service Listing
curl -s -X POST "https://singletap-backend.onrender.com/normalize" \
  -H "Content-Type: application/json" \
  -d '{
    "listing": {
      "intent": "service",
      "subintent": "provide",
      "domain": ["home services"],
      "items": [{"type": "plumbing"}],
      "self_attributes": {
        "identity": [{"type": "profession", "value": "plumber"}]
      },
      "target_location": {"name": "Delhi"},
      "location_match_mode": "explicit",
      "reasoning": "Offering plumbing services"
    }
  }'
```

---

### Store Listing Scripts (Requires UUID)

```bash
# ============================================
# /store-listing - Store with GPT Extraction
# NOTE: user_id MUST be a valid UUID
# ============================================

# 1. Store a Seller Listing
curl -s -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Selling Samsung Galaxy S23 for 55000 in Hyderabad",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'

# 2. Store a Buyer Listing
curl -s -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Want to buy an iPhone 14 Pro under 90000 in Mumbai",
    "user_id": "550e8400-e29b-41d4-a716-446655440001"
  }'

# 3. Store a Service Provider
curl -s -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I am a yoga instructor offering private sessions in South Delhi",
    "user_id": "550e8400-e29b-41d4-a716-446655440002"
  }'

# 4. Store a Rental Listing
curl -s -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "3BHK apartment available for rent in Koramangala for 40000 per month",
    "user_id": "550e8400-e29b-41d4-a716-446655440003"
  }'

# 5. Store with Match ID (linking to an existing match)
curl -s -X POST "https://singletap-backend.onrender.com/store-listing" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Interested in the iPhone listing",
    "user_id": "550e8400-e29b-41d4-a716-446655440004",
    "match_id": "existing-listing-uuid-here"
  }'
```

---

### Search and Match Scripts (Requires UUID)

```bash
# ============================================
# /search-and-match - Full Pipeline
# NOTE: user_id MUST be a valid UUID
# ============================================

# 1. Search for Phones
curl -s -X POST "https://singletap-backend.onrender.com/search-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Want to buy a Samsung phone under 60000 in Hyderabad",
    "user_id": "550e8400-e29b-41d4-a716-446655440010"
  }'

# 2. Search for Apartments
curl -s -X POST "https://singletap-backend.onrender.com/search-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Looking for a 2BHK flat for rent in Koramangala under 30000 per month",
    "user_id": "550e8400-e29b-41d4-a716-446655440011"
  }'

# 3. Search for Services
curl -s -X POST "https://singletap-backend.onrender.com/search-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Need a plumber urgently in Andheri Mumbai",
    "user_id": "550e8400-e29b-41d4-a716-446655440012"
  }'

# 4. Search for Roommates
curl -s -X POST "https://singletap-backend.onrender.com/search-and-match" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Looking for a female roommate in HSR Layout Bangalore",
    "user_id": "550e8400-e29b-41d4-a716-446655440013"
  }'
```

---

### Windows PowerShell Scripts

```powershell
# ============================================
# WINDOWS POWERSHELL VERSIONS
# ============================================

# Health Check
Invoke-RestMethod -Uri "https://singletap-backend.onrender.com/ping"

# Extract Query
$body = @{ query = "I want to buy an iPhone 15 under 90000 in Delhi" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://singletap-backend.onrender.com/extract" -Method Post -Body $body -ContentType "application/json"

# Match Two Listings
$matchBody = @{
    listing_a = @{
        intent = "product"
        subintent = "buy"
        domain = @("Electronics")
        items = @(@{ type = "smartphone"; categorical = @{ brand = "Apple" }; max = @{ cost = @(@{ type = "cost"; value = 80000; unit = "INR" }) } })
    }
    listing_b = @{
        intent = "product"
        subintent = "sell"
        domain = @("Electronics")
        items = @(@{ type = "smartphone"; categorical = @{ brand = "Apple" }; min = @{ cost = @(@{ type = "cost"; value = 60000; unit = "INR" }) } })
    }
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri "https://singletap-backend.onrender.com/match" -Method Post -Body $matchBody -ContentType "application/json"

# Store Listing (UUID required)
$storeBody = @{
    query = "Selling iPhone 14 for 65000 in Delhi"
    user_id = "550e8400-e29b-41d4-a716-446655440000"
} | ConvertTo-Json
Invoke-RestMethod -Uri "https://singletap-backend.onrender.com/store-listing" -Method Post -Body $storeBody -ContentType "application/json"

# Search and Match (UUID required)
$searchBody = @{
    query = "Want to buy iPhone under 70000"
    user_id = "550e8400-e29b-41d4-a716-446655440001"
} | ConvertTo-Json
Invoke-RestMethod -Uri "https://singletap-backend.onrender.com/search-and-match" -Method Post -Body $searchBody -ContentType "application/json"
```

---

### Sample UUIDs for Testing

```
550e8400-e29b-41d4-a716-446655440000
550e8400-e29b-41d4-a716-446655440001
550e8400-e29b-41d4-a716-446655440002
550e8400-e29b-41d4-a716-446655440003
550e8400-e29b-41d4-a716-446655440004
550e8400-e29b-41d4-a716-446655440005
550e8400-e29b-41d4-a716-446655440006
550e8400-e29b-41d4-a716-446655440007
550e8400-e29b-41d4-a716-446655440008
550e8400-e29b-41d4-a716-446655440009
```

Generate your own UUID online: https://www.uuidgenerator.net/
