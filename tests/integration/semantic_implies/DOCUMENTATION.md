# Test Documentation: Semantic Implies Integration Test Suite

| Property | Value |
|----------|-------|
| **Version** | 1.0.0 |
| **Author** | Singletap Backend Team |
| **Created** | 2026-02-13 |
| **Last Updated** | 2026-02-13 17:20:03 |

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

This test suite validates the semantic_implies function which is the
core matching logic for determining if a candidate value satisfies a required value.

The function implements multiple strategies in priority order:
1. **Exact Match**: Direct string comparison (case-insensitive)
2. **Synonym Registry**: Pre-registered synonym mappings
3. **Curated Synonyms**: Hardcoded synonym pairs (laptop/notebook)
4. **Wikidata Hierarchy**: P31/P279 traversal for subclass relationships
5. **WordNet Synset**: Same synset membership
6. **WordNet Ancestry**: Hypernym chain traversal
7. **BabelNet Synonyms**: External synonym database

Key semantics:
- implies(puppy, dog) = True (puppy IS a dog)
- implies(dog, puppy) = False (not every dog is a puppy)

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics

## Test Methodology

The integration test methodology tests the complete implies logic:

1. **Strategy Coverage**:
   - Tests each matching strategy individually
   - Verifies priority order is correct

2. **Direction Testing**:
   - Verifies asymmetric relationships work correctly
   - Child implies parent, but parent does NOT imply child

3. **Negative Testing**:
   - Verifies unrelated items do not match
   - Prevents false positives

4. **Edge Cases**:
   - Case sensitivity
   - Whitespace handling
   - Empty strings

## Test Cases

### Summary

Total Test Cases: **23**

### Test Case Details

| # | Test Case | Description | Expected Outcome |
|---|-----------|-------------|------------------|
| 1 | EXACT1: 'car' == 'car' | Exact same string should match | True |
| 2 | EXACT2: 'Car' == 'car' (case insensitive) | Case differences should still match | True |
| 3 | EXACT3: '  car  ' == 'car' (whitespace) | Extra whitespace should be trimmed | True |
| 4 | SYN1: 'sofa' implies 'couch' | Furniture synonyms | True |
| 5 | SYN2: 'couch' implies 'sofa' | Symmetric synonym relationship | True |
| 6 | SYN3: 'used' implies 'second hand' | Condition synonyms | True |
| 7 | SYN4: 'laptop' implies 'notebook' | Computing device synonyms | True |
| 8 | SYN5: 'automobile' implies 'car' | Vehicle synonyms | True |
| 9 | HIER1: 'puppy' implies 'dog' | Specific (puppy) satisfies broad (dog) | True |
| 10 | HIER2: 'dentist' implies 'doctor' | Specific profession satisfies broad category | True |
| 11 | HIER3: 'novel' implies 'book' | Specific item type satisfies broad category | True |
| 12 | HIER4: 'iphone' implies 'smartphone' | Brand implies category | True |
| 13 | HIER5: 'car' implies 'vehicle' | Specific implies general | True |
| 14 | HIER_NEG1: 'dog' does NOT imply 'puppy' | Broad (dog) does not satisfy specific (puppy) | True |
| 15 | HIER_NEG2: 'doctor' does NOT imply 'dentist' | General doctor does not satisfy specific dentist | True |
| 16 | HIER_NEG3: 'book' does NOT imply 'novel' | General book does not satisfy specific novel | True |
| 17 | HIER_NEG4: 'smartphone' does NOT imply 'iphone' | Category does not imply specific brand | True |
| 18 | HIER_NEG5: 'vehicle' does NOT imply 'car' | General does not imply specific | True |
| 19 | DIFF1: 'cat' does NOT imply 'dog' | Different animals | True |
| 20 | DIFF2: 'plumber' does NOT imply 'electrician' | Different professions | True |
| 21 | DIFF3: 'sedan' does NOT imply 'truck' | Different vehicle types | True |
| 22 | DIFF4: 'yoga' does NOT imply 'pilates' | Different fitness activities | True |
| 23 | DIFF5: 'laptop' does NOT imply 'refrigerator' | Completely different product categories | True |


## Libraries & Dependencies

### Runtime Dependencies

| Library | Version | Purpose |
|---------|---------|----------|
| nltk | 3.8+ | WordNet for synset and hypernym checking |
| requests | 2.28+ | Wikidata SPARQL queries for hierarchy |
| sentence-transformers | 2.2+ | Embedding similarity fallback |


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
| **Total Execution Time** | 340.02 seconds |
| **Timestamp** | 2026-02-13 17:20:03 |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

- Tests may be slower on first run due to caching
- Results are deterministic for cached queries


## Prerequisites

Before running these tests, ensure:

- WordNet data downloaded
- Internet access for Wikidata API
- Environment variables configured


## Known Limitations

- Wikidata queries may timeout occasionally
- Some niche items may not have hierarchy data
- BabelNet requires API key for full functionality


---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: 2026-02-13 17:20:03*