# Test Documentation: E2E Canonicalization + Matching Test Suite

| Property | Value |
|----------|-------|
| **Version** | 1.0.0 |
| **Author** | Singletap Backend Team |
| **Created** | 2026-02-13 |
| **Last Updated** | 2026-02-13 17:35:38 |

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

This test suite validates the complete end-to-end pipeline from raw JSON listings to final match decisions.

The pipeline stages tested:
1. **Canonicalization**: Converting raw terms to canonical forms
2. **Normalization**: Schema validation and normalization
3. **Matching**: Semantic comparison with implies function

Test categories:
- **Products**: Electronics, vehicles, fashion items
- **Services**: Education, home services, trades
- **True Positives**: Synonyms that should match (used/second-hand, laptop/notebook)
- **True Negatives**: Different items, brands, or subintents that should not match

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics

## Test Methodology

The E2E test methodology validates the complete matching pipeline:

1. **Input Preparation**:
   - Create listing_a (typically buyer/seeker)
   - Create listing_b (typically seller/provider)
   - Define expected match outcome

2. **Pipeline Execution**:
   - Canonicalize: Convert terms to canonical forms
   - Normalize: Validate and normalize schema
   - Match: Run listing_matches_v2 with semantic_implies

3. **Assertion**:
   - Compare actual match result to expected
   - Verify concept_ids are consistent across synonyms

4. **Coverage Areas**:
   - Intent compatibility (product/service)
   - Subintent complementarity (buy/sell, seek/provide)
   - Domain matching
   - Item type synonym resolution
   - Categorical attribute matching

## Test Cases

### Summary

Total Test Cases: **18**

### Test Case Details

| # | Test Case | Description | Expected Outcome |
|---|-----------|-------------|------------------|
| 1 | P1: 'used' vs 'second hand' smartphone | Tests synonym recognition for condition attribute | True |
| 2 | P2: 'laptop' vs 'notebook' (computing devices) | Tests synonym recognition for item types | True |
| 3 | P3: 'red' vs 'scarlet' clothing | Tests color synonym recognition | True |
| 4 | P4: 'automobile' vs 'car' | Tests vehicle synonym recognition | True |
| 5 | P5: Exact same terms (baseline) | Baseline test - identical listings should match | True |
| 6 | P6: Different domain (electronics vs furniture) | Different domains should not match | False |
| 7 | P7: Same domain, different item type | Different items in same domain should not match | False |
| 8 | P8: Same item, different brand | Brand mismatch should not match | False |
| 9 | P9: Same subintent (both sellers) | Both sellers cannot match - need complementary subintents | False |
| 10 | P10: 'new' vs 'used' condition | Condition mismatch should not match | False |
| 11 | S1: 'tutoring' vs 'coaching' (education) | Tests service synonym recognition | True |
| 12 | S2: 'plumber' vs 'plumbing' service | Tests profession vs service name recognition | True |
| 13 | S3: 'cleaning' vs 'housekeeping' | Tests home service synonyms | True |
| 14 | S4: Exact same service (baseline) | Baseline - identical services should match | True |
| 15 | S5: Different service domain | Education vs health should not match | False |
| 16 | S6: Same domain, different service | Plumber vs electrician should not match | False |
| 17 | S7: Both seekers (same subintent) | Both seeking cannot match | False |
| 18 | S8: Math tutor vs Science tutor | Subject mismatch should not match | False |


## Libraries & Dependencies

### Runtime Dependencies

| Library | Version | Purpose |
|---------|---------|----------|
| nltk | 3.8+ | WordNet access for synonym resolution |
| sentence-transformers | 2.2+ | Semantic similarity scoring |
| requests | 2.28+ | External API access (Wikidata, BabelNet) |


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
| **Total Execution Time** | 308.96 seconds |
| **Timestamp** | 2026-02-13 17:35:38 |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

- No special notes

## Prerequisites

Before running these tests, ensure:

- Environment variables configured (.env file)
- WordNet data downloaded
- Python 3.9+ with all dependencies installed


## Known Limitations

- Requires network access for Wikidata/BabelNet enrichment
- First run may be slower due to model loading


---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: 2026-02-13 17:35:38*