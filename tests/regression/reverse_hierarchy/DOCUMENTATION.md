# Test Documentation: Reverse Hierarchy Test Suite

| Property | Value |
|----------|-------|
| **Version** | 1.0.0 |
| **Author** | Singletap Backend Team |
| **Created** | 2026-02-13 |
| **Last Updated** | 2026-02-13 18:53:40 |

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

This test suite validates the critical hierarchy matching behavior.

The core principle being tested:
- **Broad buyer + Specific seller = MATCH**: If someone wants a "dog", they should see puppies (puppy is a dog)
- **Specific buyer + Broad seller = NO MATCH**: If someone wants a "puppy", a generic "dog" listing doesn't guarantee a puppy

This is implemented using:
1. Wikidata P31 (instance of) and P279 (subclass of) properties
2. BFS traversal through the hierarchy graph
3. Asymmetric matching: `implies(candidate, required)` checks if candidate satisfies required

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics

## Test Methodology

The test methodology validates asymmetric hierarchy matching:

1. **Semantic Direction**:
   - `semantic_implies(candidate, required)` returns True if candidate satisfies required
   - For hierarchy: puppy satisfies dog, but dog does NOT satisfy puppy

2. **Wikidata Integration**:
   - Uses P31 (instance of) and P279 (subclass of) to traverse hierarchy
   - BFS search up to max_depth=3 to find parent-child relationships

3. **Test Pattern**:
   - Each test creates buyer (listing_a) and seller (listing_b)
   - Tests broad-buyer/specific-seller (should match)
   - Tests specific-buyer/broad-seller (should NOT match)

4. **Verification**:
   - Run full pipeline (canonicalize + normalize + match)
   - Compare actual match result against expected

## Test Cases

### Summary

Total Test Cases: **8**

### Test Case Details

| # | Test Case | Description | Expected Outcome |
|---|-----------|-------------|------------------|
| 1 | RH1: dog (broad buyer) -> puppy (specific seller) = MATCH | A puppy IS a dog, so buyer wanting dog should match seller with puppy | True |
| 2 | RH2: doctor (broad buyer) -> dentist (specific seller) = MATCH | A dentist IS a type of doctor, so buyer wanting doctor should match dentist | True |
| 3 | RH3: book (broad buyer) -> novel (specific seller) = MATCH | A novel IS a type of book, so buyer wanting book should match novel | True |
| 4 | RH4: vehicle (broad buyer) -> car (specific seller) = MATCH | A car IS a vehicle, so buyer wanting vehicle should match car | True |
| 5 | RH5: smartphone (broad buyer) -> iphone (specific seller) = MATCH | An iPhone IS a smartphone, so buyer wanting smartphone should match iPhone | True |
| 6 | RH6: puppy (specific buyer) -> dog (broad seller) = NO MATCH | Not every dog is a puppy - buyer wants puppy specifically | False |
| 7 | RH7: dentist (specific buyer) -> doctor (broad seller) = NO MATCH | Not every doctor is a dentist - buyer wants dentist specifically | False |
| 8 | RH8: iphone (specific buyer) -> smartphone (broad seller) = NO MATCH | Not every smartphone is an iPhone - buyer wants iPhone specifically | False |


## Libraries & Dependencies

### Runtime Dependencies

| Library | Version | Purpose |
|---------|---------|----------|
| requests | 2.28+ | HTTP client for Wikidata SPARQL queries |
| nltk | 3.8+ | WordNet for fallback hierarchy information |
| sentence-transformers | 2.2+ | Embedding similarity for disambiguation |


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
| **Total Execution Time** | 4485.71 seconds |
| **Timestamp** | 2026-02-13 18:53:40 |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

- Tests validate both directions of hierarchy matching
- Results depend on Wikidata's current taxonomy


## Prerequisites

Before running these tests, ensure:

- Internet connection for Wikidata API access
- WordNet data downloaded
- Environment configured (.env file)


## Known Limitations

- Wikidata hierarchy depth limited to 3 levels
- Some niche items may not have Wikidata entries
- First run may be slower due to cache building


---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: 2026-02-13 18:53:40*