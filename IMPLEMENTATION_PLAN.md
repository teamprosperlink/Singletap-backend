# Hybrid WSD Implementation Plan

## Executive Summary
Implement a 4-stage hybrid Word Sense Disambiguation (WSD) system to improve canonicalization accuracy from ~72% to 85%+, solving all 4 failing E2E tests.

## Current State Analysis

### Existing Components (Keep)
✅ `canonicalization/static_dicts/` - Abbreviations, MWEs, spelling variants
✅ `canonicalization/preprocessor.py` - Phase 0 normalization
✅ `embedding/model_provider.py` - SentenceTransformer singleton (all-MiniLM-L6-v2)
✅ `services/external/wordnet_wrapper.py` - Local WordNet access
✅ `services/external/wikidata_wrapper.py` - Wikidata API with caching

### Components to Modify
⚠️ `canonicalization/disambiguator.py` - Replace single-scorer with hybrid ensemble
⚠️ `canonicalization/resolvers/generic_categorical_resolver.py` - Integrate new scorer

### Components to Create
🆕 `canonicalization/hybrid_scorer.py` - 3-model ensemble scorer
🆕 `canonicalization/llm_fallback.py` - Llama-3.2-1B fallback
🆕 `models/distilbert-wsd/` - Fine-tuned DistilBERT checkpoint (after training)

### Components to Remove/Skip
❌ ConceptNet integration (API deprecated)

---

## Architecture Overview

```
Input: "I need a laptop for coding"
       Term: "laptop"
       Context: "electronics"

┌─────────────────────────────────────────────────────────┐
│ Stage 1: Deterministic Cache (EXISTING - NO CHANGES)   │
│ - Custom mappings DB                                    │
│ - Static dicts (abbreviations, MWEs)                   │
│ - Monosemous word check                                │
└─────────────────────────────────────────────────────────┘
                        ↓ (No match)
┌─────────────────────────────────────────────────────────┐
│ Stage 2: Sense Gathering (MODIFY - Remove ConceptNet)  │
│ ✅ WordNet (local) → glosses, synsets, hypernyms       │
│ ✅ Wikidata (API) → entities, descriptions, aliases    │
│ ✅ BabelNet (optional) → cross-linked synsets          │
│ Output: List[CandidateSense]                           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Stage 3: Hybrid Ensemble Scoring (NEW)                 │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ Scorer 1: Gloss-Transformer (Primary, 50%)     │  │
│  │ Model: DistilBERT fine-tuned on SemCor         │  │
│  │ Input: [CLS] context [SEP] gloss [SEP]         │  │
│  │ Output: Relevance score [0-1]                  │  │
│  └─────────────────────────────────────────────────┘  │
│                        +                                │
│  ┌─────────────────────────────────────────────────┐  │
│  │ Scorer 2: Embedding Similarity (Secondary, 35%)│  │
│  │ Model: all-MiniLM-L6-v2 (existing)             │  │
│  │ Input: cosine(context_emb, gloss_emb)          │  │
│  │ Output: Similarity score [0-1]                 │  │
│  └─────────────────────────────────────────────────┘  │
│                        +                                │
│  ┌─────────────────────────────────────────────────┐  │
│  │ Scorer 3: Knowledge-Based (Tertiary, 15%)      │  │
│  │ Model: WordNet path_similarity()                │  │
│  │ Input: Graph relations between synsets         │  │
│  │ Output: Structural score [0-1]                 │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  Ensemble: 0.5*S1 + 0.35*S2 + 0.15*S3                  │
│  Confidence Check: (top - second_best) > threshold?    │
└─────────────────────────────────────────────────────────┘
                        ↓
              High confidence? YES → Return sense
                        ↓ NO (low confidence)
┌─────────────────────────────────────────────────────────┐
│ Stage 4: LLM Fallback (NEW)                            │
│ Model: Llama-3.2-1B-Instruct                           │
│ Prompt: "Which definition fits? 1. ... 2. ... 3. ..."  │
│ Output: Reasoned choice (1, 2, or 3)                   │
└─────────────────────────────────────────────────────────┘
                        ↓
              Final: DisambiguatedSense
```

---

## Implementation Phases

### Phase 1: Foundation Setup (Day 1-2)
**Goal:** Prepare environment and dependencies

**Tasks:**
1. Install dependencies
   ```bash
   pip install transformers torch datasets accelerate
   pip install scikit-learn  # For cosine_similarity
   ```

2. Download NLTK data
   ```python
   import nltk
   nltk.download('wordnet')
   nltk.download('omw-1.4')
   nltk.download('averaged_perceptron_tagger')
   ```

3. Create model directory structure
   ```
   models/
   └── distilbert-wsd/
       ├── config.json
       ├── pytorch_model.bin
       └── tokenizer/
   ```

**Deliverables:**
- ✅ All dependencies installed
- ✅ NLTK corpora downloaded
- ✅ Model directories created

---

### Phase 2: Hybrid Scorer Implementation (Day 3-5)
**Goal:** Build the 3-model ensemble scorer

**Tasks:**

1. **Create `canonicalization/hybrid_scorer.py`**
   - Implement `HybridSenseScorer` class
   - Implement `_score_with_transformer()` method
   - Implement `_score_with_embeddings()` method
   - Implement `_score_with_knowledge()` method
   - Implement `score_candidates()` ensemble method

2. **Test each scorer independently**
   - Unit test: Transformer scoring
   - Unit test: Embedding scoring
   - Unit test: Knowledge scoring
   - Integration test: Ensemble scoring

**File Structure:**
```python
# canonicalization/hybrid_scorer.py

class HybridSenseScorer:
    def __init__(self, model_path: Optional[str] = None):
        # Load 3 models
        pass

    def score_candidates(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        # Ensemble scoring
        pass

    def _score_with_transformer(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        # Primary scorer
        pass

    def _score_with_embeddings(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        # Secondary scorer
        pass

    def _score_with_knowledge(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        # Tertiary scorer
        pass
```

**Deliverables:**
- ✅ `hybrid_scorer.py` created
- ✅ All 3 scorers functional
- ✅ Ensemble weighting implemented
- ✅ Unit tests passing

---

### Phase 3: LLM Fallback (Day 6-7)
**Goal:** Implement confidence-based LLM fallback

**Tasks:**

1. **Create `canonicalization/llm_fallback.py`**
   - Implement `LLMFallback` class
   - Load Llama-3.2-1B model
   - Implement prompt formatting
   - Implement response parsing

2. **Add confidence threshold logic**
   - Calculate score margin
   - Trigger fallback on low confidence
   - Handle fallback failures gracefully

**File Structure:**
```python
# canonicalization/llm_fallback.py

class LLMFallback:
    def __init__(self):
        # Load Llama-3.2-1B
        pass

    def disambiguate(self, query: str, term: str,
                    candidates: List[CandidateSense],
                    top_scores: List[float]) -> int:
        # LLM-based selection
        pass

    def _format_prompt(self, query: str, term: str,
                      candidates: List[CandidateSense]) -> str:
        # Create structured prompt
        pass

    def _parse_choice(self, output: str) -> int:
        # Extract choice from LLM output
        pass
```

**Deliverables:**
- ✅ `llm_fallback.py` created
- ✅ Llama-3.2-1B loaded successfully
- ✅ Prompt engineering tested
- ✅ Fallback logic functional

---

### Phase 4: Integration (Day 8-10)
**Goal:** Wire hybrid scorer into existing pipeline

**Tasks:**

1. **Modify `canonicalization/disambiguator.py`**
   - Import `HybridSenseScorer` and `LLMFallback`
   - Replace `_score_glosses()` with hybrid scorer
   - Add confidence check and fallback trigger
   - Preserve existing `CandidateSense` / `DisambiguatedSense` structure

2. **Update `canonicalization/orchestrator.py`** (if needed)
   - Ensure `_canonicalize_type()` uses updated disambiguator
   - Test full pipeline flow

3. **Add configuration flags**
   ```python
   # Environment variables
   USE_HYBRID_SCORER=1  # Toggle hybrid vs legacy
   HYBRID_CONFIDENCE_THRESHOLD=0.10
   HYBRID_WEIGHTS="0.5,0.35,0.15"  # Transformer, Embedding, Knowledge
   ENABLE_LLM_FALLBACK=1
   ```

**Integration Points:**
```python
# canonicalization/disambiguator.py (BEFORE)

def disambiguate(term: str, context: Optional[str] = None) -> Optional[DisambiguatedSense]:
    candidates = _gather_candidates(term)

    # OLD: Simple embedding scoring
    for candidate in candidates:
        candidate.score = _score_gloss(context, candidate.gloss)

    best = max(candidates, key=lambda c: c.score)
    return best

# canonicalization/disambiguator.py (AFTER)

def disambiguate(term: str, context: Optional[str] = None) -> Optional[DisambiguatedSense]:
    candidates = _gather_candidates(term)

    # NEW: Hybrid ensemble scoring
    from canonicalization.hybrid_scorer import get_hybrid_scorer
    scorer = get_hybrid_scorer()

    scores = scorer.score_candidates(context or term, candidates)

    # Assign scores
    for candidate, score in zip(candidates, scores):
        candidate.score = score

    # Check confidence
    sorted_scores = sorted(scores, reverse=True)
    confidence_margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 1.0

    if confidence_margin < CONFIDENCE_THRESHOLD:
        # Trigger LLM fallback
        from canonicalization.llm_fallback import get_llm_fallback
        fallback = get_llm_fallback()
        best_idx = fallback.disambiguate(context or term, term, candidates, scores)
        return _to_disambiguated_sense(candidates[best_idx])

    # Return best from ensemble
    best_idx = scores.index(max(scores))
    return _to_disambiguated_sense(candidates[best_idx])
```

**Deliverables:**
- ✅ Hybrid scorer integrated into disambiguator
- ✅ Confidence-based fallback functional
- ✅ Configuration flags working
- ✅ Backward compatibility maintained (USE_HYBRID_SCORER=0 uses old logic)

---

### Phase 5: Testing & Validation (Day 11-12)
**Goal:** Verify hybrid system solves failing tests

**Tasks:**

1. **Run E2E canonicalization tests**
   ```bash
   python3 tests/e2e_canonicalization_test.py
   ```

2. **Expected results:**
   - **P2 (laptop vs notebook):** ✅ PASS (transformer sees "portable computer" in both glosses)
   - **S1 (tutoring vs coaching):** ✅ PASS (embedding + LLM fallback resolves)
   - **S2 (plumber vs plumbing):** ✅ PASS (knowledge scorer links via hypernyms)
   - **S3 (cleaning vs housekeeping):** ✅ PASS (ensemble catches fuzzy match)

3. **Benchmark performance**
   - Measure latency per disambiguation
   - Track fallback invocation rate
   - Validate accuracy improvement

4. **Tune ensemble weights**
   - Grid search over weight combinations
   - Optimize on validation set
   - Update default weights if needed

**Deliverables:**
- ✅ All 18 E2E tests passing (14 → 18)
- ✅ Performance benchmarks documented
- ✅ Optimal weights identified

---

### Phase 6: Fine-tuning (Day 13-15) [OPTIONAL - Can defer]
**Goal:** Fine-tune DistilBERT on SemCor for optimal accuracy

**Tasks:**

1. **Prepare SemCor dataset**
   ```python
   from datasets import load_dataset

   # Load SemCor 3.0 (WordNet-annotated)
   dataset = load_dataset("princeton-nlp/semcor")

   # Format as sentence-gloss pairs
   # Positive: (sentence, correct_gloss) → label=1
   # Negative: (sentence, wrong_gloss) → label=0
   ```

2. **Fine-tune DistilBERT**
   ```bash
   # scripts/train_distilbert_wsd.py
   python3 scripts/train_distilbert_wsd.py \
       --model_name distilbert-base-uncased \
       --output_dir models/distilbert-wsd \
       --num_train_epochs 3 \
       --per_device_train_batch_size 16 \
       --learning_rate 2e-5
   ```

3. **Update hybrid scorer to use fine-tuned model**
   ```python
   scorer = HybridSenseScorer(model_path="models/distilbert-wsd")
   ```

**Note:** Can use pre-trained DistilBERT initially and defer fine-tuning to later iteration.

**Deliverables:**
- ✅ Fine-tuned DistilBERT checkpoint (if time permits)
- ✅ Training script documented
- ⏸️ Can defer to post-MVP

---

## File Inventory

### New Files to Create
```
canonicalization/
├── hybrid_scorer.py          # 3-model ensemble scorer
└── llm_fallback.py            # Llama-3.2-1B fallback

tests/
├── test_hybrid_scorer.py      # Unit tests for ensemble
└── test_llm_fallback.py       # Unit tests for LLM

scripts/
└── train_distilbert_wsd.py    # Fine-tuning script (optional)

models/
└── distilbert-wsd/            # Fine-tuned checkpoint (optional)
```

### Files to Modify
```
canonicalization/
├── disambiguator.py           # Replace scoring logic
└── orchestrator.py            # (Verify integration, may not need changes)

requirements.txt               # Add transformers, torch, datasets
```

---

## Dependencies Update

**Add to `requirements.txt`:**
```txt
# Existing (keep)
sentence-transformers>=2.2.0
nltk>=3.8

# New for hybrid scorer
transformers>=4.30.0
torch>=2.0.0
scikit-learn>=1.3.0

# Optional for fine-tuning
datasets>=2.14.0
accelerate>=0.20.0
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_hybrid_scorer.py

def test_transformer_scorer():
    """Test gloss-transformer scoring in isolation."""
    scorer = HybridSenseScorer()
    context = "I need a laptop for coding"
    candidates = [
        CandidateSense(gloss="portable computer", ...),
        CandidateSense(gloss="a notebook for writing", ...)
    ]
    scores = scorer._score_with_transformer(context, candidates)
    assert scores[0] > scores[1]  # "portable computer" should score higher

def test_ensemble_scoring():
    """Test weighted ensemble combination."""
    scorer = HybridSenseScorer()
    # ... test that ensemble combines all 3 scorers correctly
```

### Integration Tests
```python
# tests/test_disambiguator_hybrid.py

def test_laptop_notebook_disambiguation():
    """P2: Verify laptop and notebook resolve to same concept."""
    sense_a = disambiguate("laptop", context="electronics")
    sense_b = disambiguate("notebook", context="electronics")

    # Should resolve to similar/same sense
    assert sense_a.resolved_form in ["laptop", "notebook", "portable computer"]
    assert sense_b.resolved_form in ["laptop", "notebook", "portable computer"]
```

### E2E Tests
```bash
# Run existing E2E suite
python3 tests/e2e_canonicalization_test.py

# Expected improvement: 14/18 → 18/18 passing
```

---

## Rollback Strategy

### Feature Flag
```python
# Environment variable
USE_HYBRID_SCORER=0  # Revert to legacy single-scorer

# In disambiguator.py
if os.environ.get("USE_HYBRID_SCORER", "1") == "1":
    # Use new hybrid scorer
    scorer = get_hybrid_scorer()
else:
    # Use legacy embedding-only scoring
    scorer = get_embedding_model()
```

### Graceful Degradation
```python
# If hybrid scorer fails to load, fallback to legacy
try:
    from canonicalization.hybrid_scorer import get_hybrid_scorer
    scorer = get_hybrid_scorer()
except Exception as e:
    logger.warning(f"Hybrid scorer failed to load: {e}. Using legacy scorer.")
    scorer = get_embedding_model()
```

---

## Success Metrics

### Accuracy
- **Current:** 14/18 E2E tests passing (77.8%)
- **Target:** 18/18 E2E tests passing (100%)
- **Stretch:** 95%+ on full validation set

### Performance
- **Avg latency:** <50ms per disambiguation (90th percentile)
- **Fallback rate:** <15% of queries (indicates high ensemble confidence)

### Coverage
- **Stage 1 (Cache):** 40-50% queries resolved instantly
- **Stage 3 (Ensemble):** 40-45% queries resolved with high confidence
- **Stage 4 (LLM):** 5-10% queries require fallback
- **Unresolved:** <2% queries return original term

---

## Risk Mitigation

### Risk 1: DistilBERT model loading fails
**Mitigation:** Start with pre-trained DistilBERT (no fine-tuning), gracefully degrade to embedding-only scorer

### Risk 2: Llama-3.2-1B too slow on CPU
**Mitigation:** Cache LLM results, increase confidence threshold to reduce fallback rate, use quantized model

### Risk 3: Ensemble weights not optimal
**Mitigation:** Make weights configurable via env vars, provide weight tuning script

### Risk 4: Memory usage too high
**Mitigation:** Lazy-load LLM only when needed, use float16 precision, limit batch size

---

## Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| Phase 1: Foundation | 1-2 days | Dependencies installed |
| Phase 2: Hybrid Scorer | 3 days | 3-model ensemble working |
| Phase 3: LLM Fallback | 2 days | Confidence-based fallback |
| Phase 4: Integration | 3 days | Hybrid scorer in pipeline |
| Phase 5: Testing | 2 days | All E2E tests passing |
| Phase 6: Fine-tuning | 3 days | (Optional - can defer) |
| **Total** | **11-15 days** | **Production-ready hybrid WSD** |

---

## Next Steps

1. **Review and approve this plan**
2. **Start Phase 1: Install dependencies**
3. **Implement Phase 2: Build hybrid scorer**
4. **Iterate through phases 3-5**
5. **Deploy and monitor**

---

## Appendix: Expected Test Results

### Before Hybrid Implementation
```
P2: laptop vs notebook         → FAIL (different concept_ids)
S1: tutoring vs coaching        → FAIL (different sources)
S2: plumber vs plumbing         → FAIL (person vs activity)
S3: cleaning vs housekeeping    → FAIL (off-by-one alias)

Total: 14/18 PASS (77.8%)
```

### After Hybrid Implementation
```
P2: laptop vs notebook         → PASS (transformer sees "portable computer")
S1: tutoring vs coaching        → PASS (LLM fallback resolves context)
S2: plumber vs plumbing         → PASS (knowledge scorer links hypernyms)
S3: cleaning vs housekeeping    → PASS (embedding scorer fuzzy match)

Total: 18/18 PASS (100%)
```

---

**Status:** Ready for implementation
**Last Updated:** 2026-02-13
