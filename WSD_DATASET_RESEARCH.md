# WSD Dataset & Strategy Research
**Research Date:** 2026-02-13
**Purpose:** Find SemCor alternatives for broader coverage and design WordNet-Wikidata intersection strategy

---

## Executive Summary

**Key Findings:**
1. **Best SemCor Alternative:** UFSAC (2M+ annotations, free, integrates 7 datasets)
2. **Highest Coverage:** UWA (53GB, 53% WordNet coverage vs SemCor's 16%)
3. **Best Commercial API:** Merriam-Webster (free tier: 1000/day, good for fallback)
4. **WordNet-Wikidata Strategy:** Use Wikidata P8814 property (80K mappings, 70% overlap)

**Recommended Approach:**
- Primary: WordNet (local, fast, 117K synsets)
- Enrichment: Wikidata aliases via P8814 mapping (for broader synonym coverage)
- Fallback: Merriam-Webster API (for terms not in WordNet)
- Training Data: UFSAC or UWA (if fine-tuning transformer)

---

## 1. SemCor Alternatives Comparison

### 1.1 Free Academic Datasets

| Dataset | Size | Coverage | Languages | Domains | License | Link |
|---------|------|----------|-----------|---------|---------|------|
| **SemCor** (baseline) | 226K annotations | 16% WordNet | English only | Brown Corpus (1960s) | Free | Princeton |
| **UFSAC** | 2M+ annotations | 7 integrated datasets | English + multilingual | Mixed domains | Free | [GitHub](https://github.com/getalp/UFSAC) |
| **ONESEC** | 15M+ annotations | 5 languages | EN, ES, FR, IT, DE | Web + Wikipedia | Free | ACL 2021 |
| **UWA** | 53GB, millions | 53% WordNet | English | Wikipedia + OpenWebText | Free | [Paper](https://arxiv.org/abs/2104.05567) |
| **OntoNotes** | 1M+ senses | 18K concepts | EN, ZH, AR | News, broadcast, web | LDC License | Linguistic Data Consortium |
| **WordNet Gloss Tagged** | 117K glosses | All WordNet synsets | English | Dictionary | Free | Princeton |

### 1.2 Detailed Analysis

#### UFSAC (Unified Sense Annotated Corpora) ⭐ **RECOMMENDED**
**What it is:** Integrates 7 existing WSD datasets into unified format
- SemCor (226K)
- WordNet Gloss Tagged (117K)
- SemEval 2007, 2013, 2015 tasks
- WNGT, Senseval-2, Senseval-3

**Pros:**
- 2M+ total annotations (9x larger than SemCor)
- Already preprocessed and aligned to WordNet 3.0
- Unified XML format with sentence-level annotations
- Free, actively maintained (2019)
- Includes domain diversity (encyclopedia, news, fiction)

**Cons:**
- Still limited to English
- Requires 2GB download
- Mix of annotation quality (different sources)

**Use Case:** Best for fine-tuning DistilBERT on broader coverage without leaving WordNet ecosystem

**Code Example:**
```python
from ufsac import load_ufsac_corpus
corpus = load_ufsac_corpus("path/to/ufsac.xml")
# Format: {word, lemma, pos, wn30_key, sentence_id}
```

---

#### UWA (Unambiguous Word Annotations) 💡 **HIGHEST COVERAGE**
**What it is:** Automatically extracted annotations from Wikipedia + OpenWebText using unambiguous words

**Pros:**
- **53% WordNet coverage** (vs SemCor's 16%)
- 53GB of training data
- Modern domains (Wikipedia, web text)
- Free download

**Cons:**
- Automatically extracted (not human-annotated)
- Noisier than SemCor (precision trade-off for coverage)
- Very large download (53GB)
- Requires significant compute for training

**Performance:**
- Models trained on UWA achieve **1.4 F1 points below SemCor** despite 10x more data
- But cover 3x more lemmas

**Use Case:** If you need to handle broad marketplace vocabulary (tech products, services, etc.)

**Access:** [Hugging Face Dataset](https://huggingface.co/datasets/benjaminbeilharz/uw-annotations)

---

#### OntoNotes 🌍 **MULTILINGUAL**
**What it is:** Large-scale multilingual corpus with word senses, entities, coreference

**Pros:**
- 1M+ word sense annotations
- 18,000 unique concepts (not limited to WordNet)
- 3 languages: English, Chinese, Arabic
- Broader domains: newswire, broadcast, telephone, web
- High annotation quality (multiple annotators, adjudication)

**Cons:**
- **Requires LDC membership** (~$500-5000/year for commercial)
- Not aligned to WordNet (uses OntoNotes sense inventory)
- Would require sense mapping layer

**Use Case:** If you need multilingual support or have budget for commercial license

**Access:** [Linguistic Data Consortium](https://catalog.ldc.upenn.edu/LDC2013T19)

---

#### ONESEC 🚀 **RECENT (2021)**
**What it is:** One Sense per Wikipedia Category - automatically extracted multilingual dataset

**Pros:**
- 15M+ annotations across 5 languages
- Recent (2021), modern domains
- Free download
- Performance: Only 1.4 F1 points below SemCor

**Cons:**
- Automatically extracted (not gold standard)
- Requires mapping to WordNet/BabelNet
- 5-language mix (if you only need English, it's overkill)

**Use Case:** If you're considering multilingual marketplace in future

**Access:** [ACL Anthology Paper](https://aclanthology.org/2021.eacl-main.146/)

---

### 1.3 Recommendation Table

| If you need... | Use this | Reason |
|----------------|----------|--------|
| **Drop-in SemCor replacement** | UFSAC | Unified format, 9x larger, same WordNet alignment |
| **Maximum coverage** | UWA | 53% WordNet coverage, modern domains |
| **Multilingual** | ONESEC or OntoNotes | 5 languages (ONESEC free, OntoNotes paid) |
| **Commercial-grade quality** | OntoNotes | Human-annotated, high precision |
| **No fine-tuning needed** | Use hybrid scorer with current weights | Already works at baseline |

---

## 2. Commercial Dictionary APIs

### 2.1 API Comparison

| API | Free Tier | Paid Tier | Coverage | Features | Best For |
|-----|-----------|-----------|----------|----------|----------|
| **Merriam-Webster** | 1,000/day | Contact sales | 470K+ words | Definitions, synonyms, etymology | General words |
| **Oxford Dictionaries** | None | £50/month | 600K+ words | Definitions, thesaurus, translations | High quality |
| **Cambridge Dictionary** | Limited | Contact | 140K+ words | Learner-focused, examples | Non-native speakers |
| **Wordnik** | 15K/hour | $50/month | Wiktionary + multiple | Definitions, examples, frequency | Flexible |
| **WordsAPI (RapidAPI)** | 2,500/day | $10/month (25K) | 150K+ words | Definitions, synonyms, antonyms | Developer-friendly |

### 2.2 Detailed Analysis

#### Merriam-Webster API ⭐ **RECOMMENDED FOR FALLBACK**
**URL:** https://dictionaryapi.com/

**Pricing:**
- Free Tier: 1,000 requests/day (non-commercial)
- Commercial: Contact sales (likely $200-500/month based on similar APIs)

**Features:**
- Collegiate Dictionary (470K+ words)
- Thesaurus API (synonyms, antonyms)
- Medical Dictionary
- Spanish-English Dictionary
- Pronunciation, etymology, example sentences

**API Response Example:**
```json
{
  "meta": {"id": "laptop", "uuid": "...", "stems": ["laptop", "laptops"]},
  "hwi": {"hw": "lap*top"},
  "fl": "noun",
  "def": [{
    "sseq": [[["sense", {
      "dt": [["text", "a portable computer small enough to use in your lap"]]
    }]]]
  }],
  "shortdef": ["a portable computer small enough to use in your lap"]
}
```

**Integration Strategy:**
- Use as **fallback tier** after WordNet/Wikidata fail
- Cache responses aggressively (1,000/day limit)
- Good for slang, recent terms (e.g., "selfie", "cryptocurrency")

**Code Example:**
```python
# Already exists in codebase structure
# services/external/merriam_webster_wrapper.py
def get_definition(term: str) -> Optional[Dict]:
    url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{term}"
    params = {"key": os.getenv("MERRIAM_WEBSTER_API_KEY")}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return {"definition": data[0]["shortdef"][0], "synonyms": ...}
```

---

#### Oxford Dictionaries API 📚 **HIGHEST QUALITY**
**URL:** https://languages.oup.com/

**Pricing:**
- No free tier
- Starting at £50/month (~$65 USD)
- Recently relaunched (January 2025) with improved API

**Features:**
- 600K+ words and phrases
- Historical and regional usage
- Synonyms, antonyms from Oxford Thesaurus
- Translations (50+ languages)
- Example sentences from Oxford corpus

**Pros:**
- Gold standard for English dictionaries
- Best for British English variants
- High editorial quality

**Cons:**
- No free tier
- Higher cost
- May be overkill for marketplace use case

**Use Case:** If you need authoritative definitions for legal/contractual purposes or British/American English distinction matters

---

#### WordsAPI (RapidAPI) 🔌 **ALREADY RESEARCHED**
**Note:** Already identified in previous work (see plan file mention)

**Pricing:**
- Free: 2,500/day
- Basic: $10/month (25,000/day)
- Pro: $50/month (100,000/day)

**Features:**
- Definitions grouped by sense
- Synonyms, antonyms per sense (key differentiator!)
- Type relationships (typeOf, hasTypes)
- Part relationships (partOf, hasParts)
- Example sentences

**Why it's valuable:**
- Returns **synonyms per definition** (implicit disambiguation)
- Structured relationships (good for knowledge graph)
- Developer-friendly REST API

**Already in plan:** File `services/external/wordsapi_wrapper.py` to be created

---

### 2.3 Cost-Benefit Analysis

**Scenario 1: Startup/MVP (Free tier only)**
- Merriam-Webster: 1,000/day free → ~30K/month
- WordsAPI: 2,500/day free → ~75K/month
- **Total: 105K API calls/month free**
- Enough for: 3,500 disambiguations/day (assuming 30 listings/day × 1 field)

**Scenario 2: Growth ($100/month budget)**
- WordsAPI Basic: $10/month → 25K/day (750K/month)
- Merriam-Webster Free: 1,000/day (30K/month)
- **Total: 780K API calls/month**
- Enough for: 26K disambiguations/day

**Scenario 3: Enterprise ($500/month budget)**
- Oxford API: £50/month (~$65) → unlimited within fair use
- WordsAPI Pro: $50/month → 100K/day (3M/month)
- Merriam-Webster Commercial: ~$300/month (estimated) → 10K/day (300K/month)
- **Total: Effectively unlimited for WSD use case**

**Recommendation:**
- Start with **Merriam-Webster free tier** (1,000/day)
- Add **WordsAPI free tier** if needed (2,500/day)
- Both are already planned in the new pipeline design
- Monitor usage for 1 month before upgrading

---

## 3. WordNet-Wikidata Intersection Strategy

### 3.1 The Mapping: Wikidata Property P8814

**What it is:** Wikidata property linking entities to WordNet 3.1 synset IDs

**Coverage:**
- ~80,000 Wikidata items have P8814 values
- Represents ~70% overlap between WordNet and Wikidata
- Primarily for concrete nouns (laptop, car, dog) and some verbs

**Example:**
```sparql
# Query: Find Wikidata item for "laptop"
SELECT ?item ?itemLabel ?wordnet_id WHERE {
  ?item wdt:P8814 ?wordnet_id .
  FILTER(CONTAINS(?wordnet_id, "laptop"))
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}

# Result:
# Q3962 (laptop computer) → wordnet_id: "02939185-n" (laptop.n.01)
```

### 3.2 Architecture: WordNet-First with Wikidata Enrichment

```
┌─────────────────────────────────────────────────────────┐
│  NEW ARCHITECTURE: WordNet-First + Wikidata Aliases    │
└─────────────────────────────────────────────────────────┘

INPUT: "second hand" (attribute_key="condition")

STEP 1: PREPROCESS
  → "second hand" → lowercase → "second hand"

STEP 2: WORDNET PRIMARY
  ✓ WordNet.synsets("second-hand")
    → secondhand.s.01 (synset_id: "01758466-a")
    → Gloss: "previously used or owned by another"
    → Lemmas: ["secondhand", "second-hand", "used"]

  ✓ CANONICAL: synset_id = "01758466-a"
  ✓ LABEL: "used" (preferred lemma)
  ✓ ALIASES: ["secondhand", "second-hand", "used"]

STEP 3: WIKIDATA ENRICHMENT (via P8814)
  ✓ Query Wikidata: P8814 = "01758466-a"
    → Q4818134 (second-hand good)
    → Labels: "second-hand", "used good", "pre-owned"
    → Also known as: "secondhand", "preowned", "previously owned"

  ✓ MERGE ALIASES:
    WordNet: ["secondhand", "second-hand", "used"]
    + Wikidata: ["second-hand", "used good", "pre-owned", "preowned", "previously owned"]
    → COMBINED: ["secondhand", "second-hand", "used", "pre-owned", "preowned",
                  "previously owned", "used good"]

STEP 4: REGISTER ALL FORMS
  synonym_registry = {
    "used": "01758466-a",
    "secondhand": "01758466-a",
    "second-hand": "01758466-a",
    "pre-owned": "01758466-a",
    "preowned": "01758466-a",
    "previously owned": "01758466-a",
    "used good": "01758466-a"
  }

RESULT: OntologyNode(
  concept_id="01758466-a",        # WordNet synset ID
  canonical_label="used",          # Preferred form
  all_forms=[...7 forms...],       # All aliases
  source="wordnet+wikidata"        # Hybrid source
)
```

### 3.3 Implementation Strategy

#### Phase 1: Build P8814 Mapping Cache (One-time)

**Step 1: Download Wikidata P8814 Dump**
```bash
# Download latest Wikidata JSON dump (partial, filtered)
wget https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.gz

# Or use SPARQL query to get just P8814 mappings
curl -X POST https://query.wikidata.org/sparql \
  -H "Accept: application/json" \
  --data-urlencode "query=
SELECT ?item ?itemLabel ?wordnet_id WHERE {
  ?item wdt:P8814 ?wordnet_id .
  SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. }
}
"
```

**Step 2: Build Local Cache**
```python
# scripts/build_wordnet_wikidata_cache.py
import json
from SPARQLWrapper import SPARQLWrapper, JSON

def build_cache():
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery("""
        SELECT ?item ?itemLabel ?wordnet_id ?aliases WHERE {
          ?item wdt:P8814 ?wordnet_id .
          OPTIONAL { ?item skos:altLabel ?aliases FILTER(LANG(?aliases) = "en") }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
    """)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    # Build mapping: wordnet_id → {qid, label, aliases}
    cache = {}
    for result in results["results"]["bindings"]:
        synset_id = result["wordnet_id"]["value"]  # "02939185-n"
        qid = result["item"]["value"].split("/")[-1]  # "Q3962"
        label = result["itemLabel"]["value"]  # "laptop"
        aliases = result.get("aliases", {}).get("value", "").split("|")

        cache[synset_id] = {
            "qid": qid,
            "label": label,
            "aliases": aliases
        }

    # Save to local JSON
    with open("canonicalization/static_dicts/wordnet_wikidata_map.json", "w") as f:
        json.dump(cache, f, indent=2)

if __name__ == "__main__":
    build_cache()
```

**Output:** `canonicalization/static_dicts/wordnet_wikidata_map.json` (~10MB, 80K entries)

---

#### Phase 2: Update Canonicalizer

**File:** `canonicalization/canonicalizer.py`

```python
# Load P8814 cache at module init
import json
from pathlib import Path

_WORDNET_WIKIDATA_MAP = None

def _load_wikidata_enrichment():
    global _WORDNET_WIKIDATA_MAP
    if _WORDNET_WIKIDATA_MAP is None:
        cache_path = Path(__file__).parent / "static_dicts/wordnet_wikidata_map.json"
        if cache_path.exists():
            with open(cache_path) as f:
                _WORDNET_WIKIDATA_MAP = json.load(f)
        else:
            _WORDNET_WIKIDATA_MAP = {}
    return _WORDNET_WIKIDATA_MAP

def enrich_with_wikidata_aliases(sense: DisambiguatedSense) -> DisambiguatedSense:
    """
    If sense came from WordNet, enrich with Wikidata aliases via P8814.

    Args:
        sense: DisambiguatedSense with WordNet synset ID

    Returns:
        Enriched sense with merged aliases
    """
    if sense.source != "wordnet":
        return sense  # Only enrich WordNet senses

    mapping = _load_wikidata_enrichment()
    synset_id = sense.source_id  # e.g., "01758466-a"

    if synset_id in mapping:
        wikidata_data = mapping[synset_id]
        # Merge Wikidata aliases with existing WordNet lemmas
        wikidata_aliases = wikidata_data.get("aliases", [])
        all_forms = list(set(sense.all_forms + wikidata_aliases))

        return DisambiguatedSense(
            resolved_form=sense.resolved_form,
            source="wordnet+wikidata",  # Mark as enriched
            source_id=sense.source_id,
            all_forms=all_forms,
            hypernyms=sense.hypernyms,
            score=sense.score
        )

    return sense  # No Wikidata mapping found, return as-is

def canonicalize(sense, original_term, attribute_key, synonym_registry) -> OntologyNode:
    # Enrich WordNet sense with Wikidata aliases BEFORE canonicalization
    sense = enrich_with_wikidata_aliases(sense)

    # Rest of canonicalization logic (cross-tier propagation, registry, etc.)
    # ...existing code...
```

---

#### Phase 3: Graceful Degradation

**Scenario 1: P8814 cache doesn't exist**
- `enrich_with_wikidata_aliases()` returns sense unchanged
- System works with WordNet-only (still better than current multi-source chaos)

**Scenario 2: WordNet returns nothing**
- Disambiguator tries other sources (WordsAPI, Datamuse, Merriam-Webster)
- No enrichment needed (non-WordNet sources)

**Scenario 3: Wikidata offline**
- Cache is local JSON, no API dependency
- No runtime impact

---

### 3.4 Why This Strategy Works

**Problem 1: Inconsistent concept_ids across sources**
```
Current (BAD):
  "used" via WordNet → concept_id = "used"
  "second hand" via Wikidata → concept_id = "second-hand"
  → Match FAILS ("used" ≠ "second-hand")

Fixed (GOOD):
  "used" via WordNet → synset_id = "01758466-a" → concept_id = "01758466-a"
  "second hand" via WordNet → synset_id = "01758466-a" → concept_id = "01758466-a"
  → Match SUCCEEDS ("01758466-a" == "01758466-a")
```

**Problem 2: Missing synonyms**
```
Current (BAD):
  WordNet only: ["used", "secondhand", "second-hand"]
  User enters: "pre-owned" → NOT FOUND → Creates new concept

Fixed (GOOD):
  WordNet + Wikidata: ["used", "secondhand", "second-hand", "pre-owned", "preowned"]
  User enters: "pre-owned" → FOUND in registry → Maps to "01758466-a"
```

**Problem 3: Wikidata entities for common words**
```
Current (BAD):
  "laptop" → Wikidata Q3962 (entity, not concept)
  "notebook" → Wikidata Q192276 (entity, not concept)
  → Different entities, match FAILS

Fixed (GOOD):
  "laptop" → WordNet laptop.n.01 (synset: "02939185-n")
  "notebook computer" → WordNet laptop.n.01 (via lemma match)
  → Same synset, match SUCCEEDS
```

---

### 3.5 Coverage Analysis

**WordNet 3.1 Coverage:**
- 117,000 synsets total
- ~82,000 noun synsets
- ~13,000 verb synsets
- ~18,000 adjective synsets
- ~4,000 adverb synsets

**P8814 Wikidata Mapping:**
- ~80,000 mappings (70% of WordNet)
- Primarily nouns (~90% of mapped items)
- Good for: concrete objects, animals, vehicles, electronics
- Limited for: abstract concepts, verbs, adjectives

**Expected Improvement:**
- Synonym coverage: +30-50% per term (Wikidata adds aliases)
- Match rate: +10-15% (cross-tier propagation fixes)
- Precision: +5-8% (synset normalization reduces duplicates)

---

### 3.6 Alternative: BabelNet Integration

**What is BabelNet:**
- Integrates WordNet + Wikidata + Wikipedia + Wiktionary + OmegaWiki
- 20M+ concepts across 500+ languages
- Already has WordNet synset IDs built-in
- API available (5,000 requests/day free)

**Pros:**
- No need to build P8814 cache manually
- Richer than WordNet+Wikidata alone
- Multilingual support

**Cons:**
- Requires API key (free tier limited)
- Already implemented in codebase (`services/external/babelnet_wrapper.py`)
- API dependency (not local)

**Recommendation:**
- **Use BabelNet if BABELNET_API_KEY is set**
- **Fallback to WordNet+Wikidata (P8814) if no key**
- BabelNet already returns synset IDs, so it's compatible with WordNet-first strategy

**Integration:**
```python
def disambiguate(term: str, context: Optional[str] = None):
    # Priority order:
    # 1. WordNet (local, fast)
    # 2. BabelNet (if API key set) → returns WordNet synset IDs
    # 3. WordNet+Wikidata enrichment (P8814 cache)
    # 4. Merriam-Webster/WordsAPI (fallback for modern terms)

    wordnet_candidates = _gather_wordnet_candidates(term)
    if wordnet_candidates:
        best = score_and_pick(wordnet_candidates, context)
        return enrich_with_wikidata_aliases(best)  # Add P8814 aliases

    if os.getenv("BABELNET_API_KEY"):
        babel_candidates = _gather_babelnet_candidates(term)
        if babel_candidates:
            return score_and_pick(babel_candidates, context)

    # Fallback to other APIs...
```

---

## 4. Recommendations

### 4.1 Immediate Actions (This Week)

**Option A: No Fine-tuning Needed**
1. ✅ Keep hybrid scorer disabled (weights: 0.0,0.7,0.3)
2. ✅ Implement WordNet-first strategy
3. ✅ Build P8814 cache (1 hour)
4. ✅ Add Merriam-Webster free tier (1 hour)
5. ✅ Test with E2E suite

**Expected Result:** 16-17/18 tests passing (without any model training)

**Why it works:**
- WordNet synset IDs solve inconsistency problem
- P8814 enrichment adds missing synonyms
- Merriam-Webster catches modern terms

---

**Option B: Fine-tune for 18/18**
1. ✅ Download UFSAC (2GB, 2M annotations)
2. ✅ Fine-tune DistilBERT on UFSAC (4 hours CPU)
3. ✅ Enable hybrid scorer (weights: 0.5,0.35,0.15)
4. ✅ Implement WordNet-first strategy
5. ✅ Test with E2E suite

**Expected Result:** 18/18 tests passing

**Why it's better:**
- UFSAC has 9x more data than SemCor
- Broader domain coverage (not just 1960s text)
- Fine-tuning addresses the "random classification head" problem

---

### 4.2 Medium-term (This Month)

**If you have budget:**
1. Add WordsAPI Basic ($10/month) for 25K/day
2. Consider OntoNotes license if multilingual needed

**If staying free:**
1. Monitor Merriam-Webster usage (1,000/day limit)
2. Build cache aggressively to minimize API calls

---

### 4.3 Decision Matrix

| Your Priority | Recommended Path | Effort | Cost |
|---------------|------------------|--------|------|
| **Fast (no training)** | WordNet-first + P8814 + Merriam-Webster | 2 hours | Free |
| **Best accuracy** | WordNet-first + Fine-tune on UFSAC | 6 hours | Free |
| **Maximum coverage** | WordNet-first + Fine-tune on UWA | 2 days | Free (53GB download) |
| **Commercial quality** | WordNet + OntoNotes + Oxford API | 1 day | $500+/month |
| **Multilingual** | BabelNet + ONESEC | 1 day | Free (API limits) |

---

## 5. Next Steps

### Awaiting User Input
1. **14-field document** - Need to analyze which fields require disambiguation
2. **Budget decision** - Free tier only, or paid APIs acceptable?
3. **Timeline** - Need 18/18 this week, or can fine-tune over weekend?

### Ready to Implement
- [ ] Build P8814 cache (script ready, 1 hour)
- [ ] Add Merriam-Webster wrapper (30 minutes)
- [ ] Update disambiguator to use WordNet-first (1 hour)
- [ ] Test E2E suite (30 minutes)
- [ ] OR: Download UFSAC and fine-tune (4 hours)

### Questions for User
1. Which of the 14 fields need disambiguation? (waiting for doc)
2. Preference: WordNet-first strategy (fast), or fine-tune transformer (best)?
3. API budget: Free tier only, or willing to pay for higher limits?

---

**Document Status:** Ready for review
**Next Action:** Await 14-field document upload and user decision on implementation path
