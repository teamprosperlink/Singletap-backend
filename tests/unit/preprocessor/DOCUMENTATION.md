# Test Documentation: Preprocessor Unit Test Suite

| Property | Value |
|----------|-------|
| **Version** | 1.0.0 |
| **Author** | Singletap Backend Team |
| **Created** | 2026-02-13 |
| **Last Updated** | 2026-02-13 17:14:10 |

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

This test suite validates the canonicalization preprocessor module.

The preprocessor handles Phase 0 of the canonicalization pipeline:
- **Abbreviation Expansion**: ac -> air conditioning, tv -> television
- **MWE Reduction**: barely used -> used, brand new -> new
- **Spelling Normalization**: colour -> color (UK to US)
- **Compound Normalization**: second-hand / second hand -> secondhand
- **Demonym Resolution**: indian + nationality -> india

All transformations are static, deterministic, and require no API calls.

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics

## Test Methodology

The unit test methodology follows standard practices:

1. **Input/Output Testing**:
   - Define input string and attribute key (if applicable)
   - Define expected output
   - Run preprocessor function
   - Compare actual vs expected

2. **Test Categories**:
   - Abbreviations: Static dictionary lookup
   - MWE Reductions: Pattern matching
   - Spelling: UK to US normalization
   - Compounds: Whitespace/hyphen handling
   - Demonyms: Context-aware resolution

3. **Assertion**:
   - Case-insensitive comparison
   - Whitespace trimmed
   - Pass if actual == expected

## Test Cases

### Summary

Total Test Cases: **22**

### Test Case Details

| # | Test Case | Description | Expected Outcome |
|---|-----------|-------------|------------------|
| 1 | ABBR1: 'ac' -> 'air conditioning' | Common abbreviation expansion | True |
| 2 | ABBR2: 'tv' -> 'television' | Common abbreviation expansion | True |
| 3 | ABBR3: 'pc' -> 'personal computer' | Common abbreviation expansion | True |
| 4 | ABBR4: 'suv' -> 'sport utility vehicle' | Vehicle abbreviation expansion | True |
| 5 | ABBR5: 'ssd' -> 'solid state drive' | Tech abbreviation expansion | True |
| 6 | MWE1: 'barely used' -> 'used' | Reduces multi-word expression to core meaning | True |
| 7 | MWE2: 'brand new' -> 'new' | Reduces emphasis phrase to core meaning | True |
| 8 | MWE3: 'mint condition' -> 'new' | Maps condition phrase to standard term | True |
| 9 | MWE4: 'pre-owned' -> 'used' | Maps euphemism to standard term | True |
| 10 | MWE5: 'gently used' -> 'used' | Reduces qualified phrase to core meaning | True |
| 11 | SPELL1: 'colour' -> 'color' | British to American spelling | True |
| 12 | SPELL2: 'grey' -> 'gray' | British to American spelling | True |
| 13 | SPELL3: 'tyre' -> 'tire' | British to American spelling | True |
| 14 | SPELL4: 'aluminium' -> 'aluminum' | British to American spelling | True |
| 15 | SPELL5: 'centre' -> 'center' | British to American spelling | True |
| 16 | COMP1: 'second hand' -> 'secondhand' (registry) | Spaces removed for registry lookup | True |
| 17 | COMP2: 'second-hand' -> 'secondhand' (registry) | Hyphens removed for registry lookup | True |
| 18 | COMP3: 'air_conditioning' -> 'airconditioning' (registry) | Underscores removed for registry lookup | True |
| 19 | DEM1: 'indian' + nationality -> 'india' | Demonym resolved when attribute is nationality | True |
| 20 | DEM2: 'french' + origin -> 'france' | Demonym resolved when attribute is origin | True |
| 21 | DEM3: 'japanese' + country -> 'japan' | Demonym resolved when attribute is country | True |
| 22 | DEM4: 'indian' + food (no resolution) | Demonym NOT resolved when attribute is not nationality-related | True |


## Libraries & Dependencies

### Runtime Dependencies

| Library | Version | Purpose |
|---------|---------|----------|
| nltk | 3.8+ | WordNetLemmatizer for lemmatization |


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
| **Total Execution Time** | 3.28 seconds |
| **Timestamp** | 2026-02-13 17:14:10 |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

- All tests run locally without API calls
- Tests are deterministic and repeatable


## Prerequisites

Before running these tests, ensure:

- NLTK wordnet data downloaded


---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: 2026-02-13 17:14:10*