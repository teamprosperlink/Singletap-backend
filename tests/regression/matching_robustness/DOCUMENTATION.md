# Test Documentation: Matching Robustness Test Suite

| Property | Value |
|----------|-------|
| **Version** | 1.0.0 |
| **Author** | Singletap Backend Team |
| **Created** | 2026-02-13 |
| **Last Updated** | 2026-02-13 17:38:28 |

## Table of Contents

1. [Overview](#overview)
2. [Test Methodology](#test-methodology)
3. [Test Cases](#test-cases)
4. [Libraries & Dependencies](#libraries--dependencies)
5. [Hardware & Infrastructure](#hardware--infrastructure)
6. [Execution Details](#execution-details)
7. [Prerequisites](#prerequisites)
8. [Known Limitations](#known-limitations)
9. [Related Documents](#related-documents)

## Overview

### Purpose

This test suite validates the robustness of the matching pipeline across diverse domains.

It tests:
1. **Synonym Recognition**: sofa/couch, apartment/flat, physician/doctor
2. **Hyponym Handling**: puppy vs dog (specific vs broad semantics)
3. **Cross-Domain Disambiguation**: table (furniture) vs table (reservation)
4. **Subintent Compatibility**: buy/sell pairs vs same subintent
5. **Categorical Constraints**: yoga vs pilates specialties

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics

## Test Methodology

The test methodology follows a data-driven approach:

1. **Test Case Definition**: Each test defines two listings (A and B) with:
   - Intent (product/service)
   - Subintent (buy/sell, seek/provide)
   - Domain (pets, healthcare, furniture, etc.)
   - Item type and optional categorical constraints

2. **Pipeline Execution**:
   - Canonicalization: Preprocessing, disambiguation, normalization
   - Matching: listing_matches_v2 with semantic_implies function

3. **Expected Behavior**:
   - TRUE POSITIVES: Same/synonymous items with complementary subintents
   - TRUE NEGATIVES: Different items, same subintents, or incompatible categories

4. **Assertion Model**:
   - Expected: Whether listings should match (True/False)
   - Actual: Result from matching pipeline
   - Pass: actual == expected

## Test Cases

### Summary

Total Test Cases: **20**

### Test Case Details

| # | Test Case | Description | Expected Outcome |
|---|-----------|-------------|------------------|
| 1 | R1: 'sofa' vs 'couch' (furniture synonyms) | Tests that sofa and couch are recognized as synonyms | True |
| 2 | R2: 'apartment' vs 'flat' (real estate synonyms) | Tests that apartment and flat are recognized as synonyms | True |
| 3 | R3: 'puppy' vs 'dog' (specific buyer, broad seller = NO MATCH) | Buyer wants puppy but seller only offers dog (not every dog is a puppy) | False |
| 4 | R4: 'physician' vs 'doctor' (healthcare synonyms) | Tests that physician and doctor are recognized as synonyms | True |
| 5 | R5: 'bicycle' vs 'bike' (abbreviation synonym) | Tests that bicycle and bike are recognized as the same | True |
| 6 | R6: 'guitar' buyer vs 'acoustic guitar' seller = MATCH | Broad buyer (guitar) should match specific seller (acoustic guitar) | True |
| 7 | R7: 'hairdresser' vs 'hair stylist' (beauty synonyms) | Tests that hairdresser and hair stylist are synonyms | True |
| 8 | R8: 'farmer' vs 'farm worker' (different roles = NO MATCH) | Farmer and farm worker are different roles | False |
| 9 | R9: 'novel' vs 'book' (specific buyer, broad seller = NO MATCH) | Buyer wants novel but seller only offers book (not every book is a novel) | False |
| 10 | R10: 'gym trainer' vs 'fitness instructor' (specific vs broad = NO MATCH) | Gym trainer is specific, fitness instructor is broader | False |
| 11 | R11: 'cat' vs 'dog' (different pets = NO MATCH) | Cat and dog are completely different pets | False |
| 12 | R12: 'carpenter' vs 'painter' (different trades = NO MATCH) | Carpenter and painter are different construction trades | False |
| 13 | R13: 'table' furniture vs 'table reservation' (different domains = NO MATCH) | Same word but completely different meanings and domains | False |
| 14 | R14: Both buyers for sofa (same subintent = NO MATCH) | Two buyers cannot match - need complementary subintents | False |
| 15 | R15: 'yoga' vs 'pilates' instructor (different specialties = NO MATCH) | Yoga and pilates are different fitness disciplines | False |
| 16 | R16: Orange fruit vs Orange t-shirt (different contexts = NO MATCH) | Orange as fruit vs orange as color on t-shirt | False |
| 17 | R17: 'piano' product vs 'piano lessons' service (different intents = NO MATCH) | Buying a piano is different from seeking piano lessons | False |
| 18 | R18: 'driving lessons' vs 'delivery driving' (different services = NO MATCH) | Learning to drive vs providing delivery service | False |
| 19 | R19: 'sedan' vs 'truck' (different vehicle types = NO MATCH) | Sedan and truck are different vehicle categories | False |
| 20 | R20: 'dentist' buyer vs 'doctor' seller (specific vs broad = NO MATCH) | Buyer wants dentist specifically, seller offers general doctor | False |


## Libraries & Dependencies

### Runtime Dependencies

| Library | Version | Purpose |
|---------|---------|----------|
| nltk | 3.8+ | Natural language processing and WordNet access |
| sentence-transformers | 2.2+ | Embedding model for semantic similarity |
| requests | 2.28+ | HTTP client for Wikidata/BabelNet API calls |
| numpy | 1.24+ | Numerical operations for cosine similarity |


### Installation

```bash
pip install -r requirements.txt
```

## Hardware & Infrastructure

### Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **Operating System** | Windows 11 |
| **Platform** | Windows-11-10.0.26100-SP0 |
| **CPU** | ARMv8 (64-bit) Family 8 Model 1 Revision 201, Qualcomm Technologies Inc |
| **CPU Cores** | 8 |
| **Architecture** | ARM64 |
| **Total Memory** | 15.61 GB |

### Software Environment

| Component | Version |
|-----------|---------|
| **Python Version** | 3.13.12 |
| **Python Implementation** | CPython |
| **Compiler** | MSC v.1944 64 bit (AMD64) |

### Infrastructure

| Property | Value |
|----------|-------|
| **Environment Type** | Local Development |
| **Working Directory** | `D:\vriddhi-github\Singletap-backend` |
| **User** | bhand |

### Environment Variables

| Variable | Status |
|----------|--------|
| `USE_NEW_PIPELINE` | 1 |
| `USE_HYBRID_SCORER` | 0 |
| `BABELNET_API_KEY` | ***SET*** |

## Execution Details

### Timing

| Metric | Value |
|--------|-------|
| **Total Execution Time** | 134.51 seconds |
| **Timestamp** | 2026-02-13 17:38:28 |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

- Tests run in isolation - no shared state between tests
- Each test creates fresh listing objects
- Results are deterministic for same input data


## Prerequisites

Before running these tests, ensure:

- WordNet data downloaded via `python -c "import nltk; nltk.download('wordnet')"
- Environment variables set: BABELNET_API_KEY (optional)
- Python 3.9+ with project dependencies installed


## Known Limitations

- BabelNet API has rate limits (1000 requests/day for free tier)
- Wikidata SPARQL endpoint may have occasional timeouts
- First run may be slower due to model loading


---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: 2026-02-13 17:38:28*