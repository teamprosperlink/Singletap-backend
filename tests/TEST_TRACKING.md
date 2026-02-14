# Test Tracking Scratchpad

This document tracks all test files, their execution status, and documentation/report generation status.

**Last Updated:** 2026-02-13 18:45

---

## Summary

| Category | Total Files | Migrated | Run | Docs Generated | Reports Generated |
|----------|-------------|----------|-----|----------------|-------------------|
| Unit Tests | 5 | 1 | 1 | 1 | 1 |
| Integration Tests | 6 | 1 | 1 | 1 | 1 |
| E2E Tests | 2 | 1 | 1 | 1 | 1 |
| Regression Tests | 4 | 2 | 2 | 2 | 2 |
| Feature Tests | 9 | 0 | 0 | 0 | 0 |
| **TOTAL** | **26** | **5** | **5** | **5** | **5** |

---

## New Framework Test Files (Migrated)

### Unit Tests (`tests/unit/`)

| # | Test File | Status | Run | Docs | Reports | Notes |
|---|-----------|--------|-----|------|---------|-------|
| 1 | `unit/preprocessor/test_preprocessor.py` | MIGRATED | RAN (22/22 PASS) | GENERATED | JSON, HTML, XML | Abbreviations, MWE, Spelling, Demonyms |

### Integration Tests (`tests/integration/`)

| # | Test File | Status | Run | Docs | Reports | Notes |
|---|-----------|--------|-----|------|---------|-------|
| 1 | `integration/semantic_implies/test_semantic_implies.py` | MIGRATED | RAN (22/23 PASS) | GENERATED | JSON, HTML, XML | 1 failure due to API timeout |

### E2E Tests (`tests/e2e/`)

| # | Test File | Status | Run | Docs | Reports | Notes |
|---|-----------|--------|-----|------|---------|-------|
| 1 | `e2e/canonicalization/test_e2e_canonicalization.py` | MIGRATED | RAN (18/18 PASS) | GENERATED | JSON, HTML, XML | Products + Services |

### Regression Tests (`tests/regression/`)

| # | Test File | Status | Run | Docs | Reports | Notes |
|---|-----------|--------|-----|------|---------|-------|
| 1 | `regression/matching_robustness/test_matching_robustness.py` | MIGRATED | RAN (20/20 PASS) | GENERATED | JSON, HTML, XML | Synonyms, hyponyms, domains |
| 2 | `regression/reverse_hierarchy/test_reverse_hierarchy.py` | MIGRATED | RAN (8/8 PASS) | GENERATED | JSON, HTML, XML | Hierarchy direction tests |

---

## Legacy Test Files (Need Migration)

### Root Level Tests (`tests/`)

| # | Test File | Status | Action Required |
|---|-----------|--------|-----------------|
| 1 | `e2e_canonicalization_test.py` | LEGACY | Superseded by `e2e/canonicalization/` |
| 2 | `robustness_test.py` | LEGACY | Superseded by `regression/matching_robustness/` |
| 3 | `reverse_hierarchy_test.py` | LEGACY | Superseded by `regression/reverse_hierarchy/` |
| 4 | `test_hybrid_scorer.py` | LEGACY | Migrate to `unit/hybrid_scorer/` |
| 5 | `run_all_tests.py` | UTILITY | Master test runner (new framework) |

### Feature Testing (`tests/feature_testing/`)

| # | Test File | Status | Action Required |
|---|-----------|--------|-----------------|
| 1 | `test_all_examples.py` | LEGACY | Review and migrate to `e2e/` |
| 2 | `test_complete_flow.py` | LEGACY | Review and migrate to `e2e/` |
| 3 | `test_debug_matches.py` | LEGACY | Review - may be debug script |
| 4 | `test_e2e_matching.py` | LEGACY | Migrate to `e2e/matching/` |
| 5 | `test_flow_direct.py` | LEGACY | Review and migrate |
| 6 | `test_mutual_queries.py` | LEGACY | Migrate to `e2e/` |
| 7 | `test_mutual_with_all_results.py` | LEGACY | Migrate to `e2e/` |
| 8 | `test_search_debug.py` | LEGACY | Review - may be debug script |
| 9 | `test_user_queries.py` | LEGACY | Migrate to `e2e/` |

### Integration Testing (`tests/integration_testing/`)

| # | Test File | Status | Action Required |
|---|-----------|--------|-----------------|
| 1 | `test_canonicalization.py` | LEGACY | Migrate to `integration/canonicalization/` |
| 2 | `test_extraction_api.py` | LEGACY | Migrate to `integration/extraction/` |
| 3 | `test_gpt_extraction.py` | LEGACY | Migrate to `integration/gpt/` |
| 4 | `test_qdrant_search.py` | LEGACY | Migrate to `integration/qdrant/` |
| 5 | `test_single_query.py` | LEGACY | Migrate to `integration/` |

### Unit Testing (`tests/unit_testing/`)

| # | Test File | Status | Action Required |
|---|-----------|--------|-----------------|
| 1 | `test_embedding_v2.py` | LEGACY | Migrate to `unit/embedding/` |
| 2 | `test_item_array_matchers.py` | LEGACY | Migrate to `unit/matchers/` |
| 3 | `test_item_matchers.py` | LEGACY | Migrate to `unit/matchers/` |
| 4 | `test_listing_matcher.py` | LEGACY | Migrate to `unit/matchers/` |

### Files/Functions Testing (`tests/files_functions_testing/`)

| # | Test File | Status | Action Required |
|---|-----------|--------|-----------------|
| 1 | `fix_test_files.py` | UTILITY | Not a test - review |
| 2 | `test_schema_update.py` | LEGACY | Migrate to `unit/schema/` |

---

## Generated Documentation

| Test Suite | DOCUMENTATION.md | Location |
|------------|------------------|----------|
| Preprocessor Unit Tests | GENERATED | `tests/unit/preprocessor/DOCUMENTATION.md` |
| Semantic Implies Integration | GENERATED | `tests/integration/semantic_implies/DOCUMENTATION.md` |
| E2E Canonicalization | GENERATED | `tests/e2e/canonicalization/DOCUMENTATION.md` |
| Matching Robustness | GENERATED | `tests/regression/matching_robustness/DOCUMENTATION.md` |
| Reverse Hierarchy | GENERATED | `tests/regression/reverse_hierarchy/DOCUMENTATION.md` |

---

## Generated Reports

| Test Suite | JSON | HTML | XML | Location |
|------------|------|------|-----|----------|
| Preprocessor Unit Tests | YES | YES | YES | `tests/unit/preprocessor/REPORT.*` |
| Semantic Implies Integration | YES | YES | YES | `tests/integration/semantic_implies/REPORT.*` |
| E2E Canonicalization | YES | YES | YES | `tests/e2e/canonicalization/REPORT.*` |
| Matching Robustness | YES | YES | YES | `tests/regression/matching_robustness/REPORT.*` |
| Reverse Hierarchy | YES | YES | YES | `tests/regression/reverse_hierarchy/REPORT.*` |

---

## Test Execution Log

| Date | Test Suite | Result | Duration | Notes |
|------|------------|--------|----------|-------|
| 2026-02-13 17:14 | Preprocessor Unit Tests | 22/22 PASS (100%) | 3.28s | All tests passed |
| 2026-02-13 17:20 | Semantic Implies Integration | 22/23 PASS (95.7%) | 340.02s | 1 fail (API timeout on used/second-hand) |
| 2026-02-13 17:35 | E2E Canonicalization | 18/18 PASS (100%) | 308.96s | All tests passed |
| 2026-02-13 17:45 | Matching Robustness | 20/20 PASS (100%) | 134.51s | All tests passed |
| 2026-02-13 18:30 | Reverse Hierarchy | 8/8 PASS (100%) | 4485.71s | All tests passed (slow due to API timeouts) |

---

## Next Steps

### Priority 1: Run Remaining Migrated Tests
- [x] Run `e2e/canonicalization/test_e2e_canonicalization.py` - DONE (18/18 PASS)
- [x] Run `regression/matching_robustness/test_matching_robustness.py` - DONE (20/20 PASS)
- [x] Run `regression/reverse_hierarchy/test_reverse_hierarchy.py` - DONE (8/8 PASS)

### Priority 2: Migrate Legacy Unit Tests
- [ ] Migrate `unit_testing/test_embedding_v2.py`
- [ ] Migrate `unit_testing/test_item_matchers.py`
- [ ] Migrate `unit_testing/test_item_array_matchers.py`
- [ ] Migrate `unit_testing/test_listing_matcher.py`

### Priority 3: Migrate Legacy Integration Tests
- [ ] Migrate `integration_testing/test_canonicalization.py`
- [ ] Migrate `integration_testing/test_qdrant_search.py`
- [ ] Migrate `integration_testing/test_extraction_api.py`

### Priority 4: Review Feature Tests
- [ ] Review `feature_testing/` folder for relevant tests
- [ ] Migrate applicable tests to `e2e/`

---

## Commands Reference

```bash
# Run individual test
python3 tests/unit/preprocessor/test_preprocessor.py

# Run all tests (master runner)
python3 tests/run_all_tests.py

# Run with pytest
python3 -m pytest tests/unit/preprocessor/ -v
```

---

*This tracking document is maintained to ensure all tests have proper documentation and reports.*
