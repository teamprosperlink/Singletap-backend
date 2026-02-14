"""
Phase 1: Disambiguation — gather candidates from ALL sources, score, pick best.

Gathers candidate senses from 5 sources simultaneously:
  1. WordNet (local)
  2. WordsAPI (API, if RAPIDAPI_KEY set)
  3. Datamuse (API, free, no key)
  4. Wikidata (API)
  5. BabelNet (API, if BABELNET_API_KEY set)

Scores ALL glosses/definitions against context via:
  - LEGACY MODE (USE_HYBRID_SCORER=0): Simple embedding similarity
  - HYBRID MODE (USE_HYBRID_SCORER=1, default): 3-model ensemble
    1. Gloss-Transformer Scorer (50%): DistilBERT context-gloss matching
    2. Embedding Similarity Scorer (35%): all-MiniLM-L6-v2 cosine similarity
    3. Knowledge-Based Scorer (15%): WordNet path similarity
    With LLM fallback (Llama-3.2-1B) for low-confidence cases.

Returns the best candidate above a threshold.

Key difference from old cascade: no short-circuiting. All sources contribute candidates
before scoring, so the best sense wins regardless of source.
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

# Minimum cosine similarity for a candidate to be accepted (legacy mode)
DISAMBIGUATION_THRESHOLD = 0.15

# Hybrid scorer mode flag
USE_HYBRID_SCORER = os.environ.get("USE_HYBRID_SCORER", "1") == "1"


@dataclass
class CandidateSense:
    """A candidate sense from any source."""
    source: str          # "wordnet", "wordsapi", "datamuse", "wikidata", "babelnet"
    source_id: str       # synset name, Q-ID, BabelNet ID, etc.
    label: str           # primary label
    gloss: str           # definition text for scoring
    all_forms: List[str] = field(default_factory=list)  # all synonyms/aliases
    hypernyms: List[str] = field(default_factory=list)  # parent concepts
    score: float = 0.0


@dataclass
class DisambiguatedSense:
    """The winning sense after disambiguation."""
    resolved_form: str
    source: str
    source_id: str
    all_forms: List[str]
    hypernyms: List[str]
    score: float


def _get_embedding_model():
    """Get shared embedding model for scoring."""
    from embedding.model_provider import get_embedding_model
    return get_embedding_model()


def _cosine_similarity(vec_a, vec_b) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def _gather_wordnet_candidates(term: str, context: Optional[str] = None) -> List[CandidateSense]:
    """
    Gather one CandidateSense per WordNet synset.

    When USE_HYBRID_SCORER=0 (Path A), uses new get_canonical() method
    which returns synset offset IDs and does disambiguation internally.

    When USE_HYBRID_SCORER=1, uses get_glosses_per_synset() to return
    all synsets for ensemble scoring.
    """
    try:
        from services.external.wordnet_wrapper import get_wordnet_client
        wn = get_wordnet_client()

        # Path A mode: Use new get_canonical() method
        if not USE_HYBRID_SCORER:
            result = wn.get_canonical(term, context)
            if not result:
                return []

            return [CandidateSense(
                source="wordnet",
                source_id=result["canonical_id"],  # Synset offset ID (e.g., "01640482-s")
                label=result["canonical_label"],
                gloss=result["gloss"],
                all_forms=result["all_forms"],
                hypernyms=result["hypernyms"],
            )]

        # Hybrid mode: Gather all synsets for scoring
        glosses = wn.get_glosses_per_synset(term)

        candidates = []
        for entry in glosses:
            candidates.append(CandidateSense(
                source="wordnet",
                source_id=entry["synset_name"],
                label=entry["lemmas"][0] if entry["lemmas"] else term.lower(),
                gloss=entry["gloss"],
                all_forms=entry["lemmas"],
                hypernyms=entry["hypernyms"],
            ))
        return candidates
    except Exception as e:
        print(f"Disambiguator: WordNet gather error for '{term}': {e}")
        return []


def _gather_wordsapi_candidates(term: str) -> List[CandidateSense]:
    """Gather one CandidateSense per WordsAPI definition."""
    try:
        from services.external.wordsapi_wrapper import get_wordsapi_client
        client = get_wordsapi_client()
        if not client.is_available():
            return []

        definitions = client.get_definitions_with_synonyms(term)

        candidates = []
        for i, defn in enumerate(definitions):
            definition_text = defn.get("definition", "")
            synonyms = [s.lower() for s in defn.get("synonyms", [])]
            type_of = [t.lower() for t in defn.get("type_of", [])]
            all_forms = list(set([term.lower()] + synonyms))

            candidates.append(CandidateSense(
                source="wordsapi",
                source_id=f"wordsapi:{term}:{i}",
                label=synonyms[0] if synonyms else term.lower(),
                gloss=definition_text,
                all_forms=all_forms,
                hypernyms=type_of,
            ))
        return candidates
    except Exception as e:
        print(f"Disambiguator: WordsAPI gather error for '{term}': {e}")
        return []


def _gather_datamuse_candidates(term: str, context: Optional[str] = None) -> List[CandidateSense]:
    """
    Gather a pseudo-candidate from Datamuse synonym cluster.

    Datamuse doesn't provide definitions per se, so we build a pseudo-gloss
    from the synonym list (the cluster itself carries meaning).
    """
    try:
        from services.external.datamuse_wrapper import get_datamuse_client
        client = get_datamuse_client()

        synonyms_raw = client.get_synonyms(term, topic=context)
        if not synonyms_raw:
            return []

        synonym_words = [s["word"].lower() for s in synonyms_raw if "word" in s]
        if not synonym_words:
            return []

        # Build pseudo-gloss from synonyms + means-like results
        means_like = client.get_means_like(term, topic=context)
        ml_words = [m["word"].lower() for m in means_like[:5] if "word" in m]

        # Also try to get a real definition
        defs = client.get_definitions(term)
        def_text = ""
        if defs:
            for d in defs:
                if "defs" in d and d["defs"]:
                    def_text = d["defs"][0]  # First definition
                    break

        pseudo_gloss = def_text if def_text else f"synonyms: {', '.join(synonym_words[:10])}"

        all_forms = list(set([term.lower()] + synonym_words))

        return [CandidateSense(
            source="datamuse",
            source_id=f"datamuse:{term}",
            label=synonym_words[0] if synonym_words else term.lower(),
            gloss=pseudo_gloss,
            all_forms=all_forms,
            hypernyms=[],  # Datamuse doesn't provide hierarchy
        )]
    except Exception as e:
        print(f"Disambiguator: Datamuse gather error for '{term}': {e}")
        return []


def _gather_wikidata_candidates(term: str) -> List[CandidateSense]:
    """Gather one CandidateSense per Wikidata search result (raw, no pre-scoring)."""
    try:
        from services.external.wikidata_wrapper import get_wikidata_client
        wikidata = get_wikidata_client()

        # Use raw search_entity, NOT search_disambiguated_entity
        # All scoring is centralized in this module
        search_results = wikidata.search_entity(term, limit=5)
        if not search_results:
            return []

        candidates = []
        for result in search_results:
            entity_id = result.get("id", "")
            label = result.get("label", "").lower()
            description = result.get("description", "")
            aliases = [a.lower() for a in result.get("aliases", [])]

            # Get full details for more aliases
            details = wikidata.get_entity_details(entity_id)
            if details:
                for a in details.get("aliases", []):
                    al = a.lower()
                    if al not in aliases:
                        aliases.append(al)

            all_forms = list(set([label] + aliases + [term.lower()]))

            candidates.append(CandidateSense(
                source="wikidata",
                source_id=entity_id,
                label=label,
                gloss=description,
                all_forms=all_forms,
                hypernyms=[],  # Filled by enrich_hypernyms later if needed
            ))
        return candidates
    except Exception as e:
        print(f"Disambiguator: Wikidata gather error for '{term}': {e}")
        return []


def _gather_babelnet_candidates(term: str) -> List[CandidateSense]:
    """Gather one CandidateSense per BabelNet synset."""
    try:
        import os
        if not os.getenv("BABELNET_API_KEY"):
            return []

        from services.external.babelnet_wrapper import get_babelnet_client
        bn = get_babelnet_client()

        senses = bn.get_senses(term, language="EN")
        if not senses:
            return []

        # Collect unique synset IDs
        synset_ids = []
        seen = set()
        for sense in senses:
            props = sense.get("properties", sense)
            sid = props.get("synsetID", {}).get("id", "")
            if sid and sid not in seen:
                seen.add(sid)
                synset_ids.append(sid)

        candidates = []
        for sid in synset_ids[:5]:  # Limit to conserve API calls
            synset = bn.get_synset(sid, language="EN")
            if not synset:
                continue

            # Extract glosses
            glosses = []
            for g in synset.get("glosses", []):
                if g.get("language") == "EN":
                    gloss_text = g.get("gloss", "")
                    if gloss_text:
                        glosses.append(gloss_text)

            # Extract senses/synonyms
            synonyms = []
            for sense in synset.get("senses", []):
                props = sense.get("properties", sense)
                if props.get("language") == "EN":
                    lemma = props.get("simpleLemma") or props.get("fullLemma", "")
                    if lemma:
                        synonyms.append(lemma.replace("_", " ").lower())

            gloss_text = glosses[0] if glosses else ""
            label = synonyms[0] if synonyms else term.lower()
            all_forms = list(set([term.lower()] + synonyms))

            candidates.append(CandidateSense(
                source="babelnet",
                source_id=sid,
                label=label,
                gloss=gloss_text,
                all_forms=all_forms,
                hypernyms=[],  # Could be enriched later
            ))
        return candidates
    except Exception as e:
        print(f"Disambiguator: BabelNet gather error for '{term}': {e}")
        return []


def disambiguate(term: str, context: Optional[str] = None) -> Optional[DisambiguatedSense]:
    """
    Phase 1: Gather candidates from all sources, score against context, pick best.

    Args:
        term: The preprocessed term to disambiguate.
        context: Attribute key or context string (e.g., "condition", "fuel_type").

    Returns:
        DisambiguatedSense with the best scoring candidate, or None.
    """
    # 1. Gather candidates from ALL sources
    all_candidates: List[CandidateSense] = []

    # Each wrapped in try/except so one failure doesn't block others
    all_candidates.extend(_gather_wordnet_candidates(term, context))

    # Path A mode: Skip WordsAPI, Datamuse, Wikidata (use WordNet + BabelNet only)
    if USE_HYBRID_SCORER:
        all_candidates.extend(_gather_wordsapi_candidates(term))
        all_candidates.extend(_gather_datamuse_candidates(term, context))
        all_candidates.extend(_gather_wikidata_candidates(term))

    all_candidates.extend(_gather_babelnet_candidates(term))

    if not all_candidates:
        return None

    # 2. Score candidates against context
    if USE_HYBRID_SCORER and context:
        # NEW: Use hybrid ensemble scorer
        best_idx = _score_with_hybrid_ensemble(term, context, all_candidates)
        best = all_candidates[best_idx]
    else:
        # LEGACY: Use simple embedding scoring
        best = _score_with_legacy_embeddings(term, context, all_candidates)

    return DisambiguatedSense(
        resolved_form=best.label,
        source=best.source,
        source_id=best.source_id,
        all_forms=best.all_forms,
        hypernyms=best.hypernyms,
        score=best.score,
    )


def _score_with_hybrid_ensemble(term: str, context: str, candidates: List[CandidateSense]) -> int:
    """
    Score candidates using hybrid 3-model ensemble with LLM fallback.

    Returns:
        Index of best candidate
    """
    try:
        from canonicalization.hybrid_scorer import get_hybrid_scorer
        from canonicalization.llm_fallback import get_llm_fallback, should_use_llm_fallback

        # Get hybrid scorer
        scorer = get_hybrid_scorer()

        # Score all candidates
        scores = scorer.score_candidates(context, candidates)

        # Assign scores to candidates
        for candidate, score in zip(candidates, scores):
            candidate.score = score

        # Check confidence
        if should_use_llm_fallback(scores):
            # Low confidence margin - trigger LLM fallback
            print(f"  Low confidence (margin < threshold) - triggering LLM fallback for '{term}'")
            fallback = get_llm_fallback()

            if fallback.is_available():
                best_idx = fallback.disambiguate(
                    query=context,
                    term=term,
                    candidates=candidates,
                    top_scores=scores
                )
                return best_idx

        # High confidence or LLM unavailable - use top ensemble score
        best_idx = scores.index(max(scores))
        return best_idx

    except Exception as e:
        print(f"Hybrid scorer error: {e}. Falling back to legacy scoring.")
        # Fall back to legacy scoring
        best = _score_with_legacy_embeddings(term, context, candidates)
        return candidates.index(best)


def _score_with_legacy_embeddings(term: str, context: Optional[str],
                                  candidates: List[CandidateSense]) -> CandidateSense:
    """
    Legacy scoring: Simple embedding similarity.

    Returns:
        Best candidate
    """
    if context:
        try:
            model = _get_embedding_model()
            context_emb = model.encode(context)

            for candidate in candidates:
                if candidate.gloss:
                    gloss_emb = model.encode(candidate.gloss)
                    candidate.score = max(_cosine_similarity(context_emb, gloss_emb), 0.0)

                    # Label match bonus (if term matches label exactly)
                    if candidate.label == term.lower():
                        candidate.score += 0.1
                else:
                    candidate.score = 0.0
        except Exception as e:
            print(f"Disambiguator: scoring error: {e}")
            # Fall through to no-context path

    # Pick best candidate
    if context:
        # Sort by score descending
        scored = [c for c in candidates if c.score >= DISAMBIGUATION_THRESHOLD]
        if scored:
            return max(scored, key=lambda c: c.score)
        else:
            # No candidate above threshold; return first WordNet candidate (backward compat)
            wn_candidates = [c for c in candidates if c.source == "wordnet"]
            if wn_candidates:
                return wn_candidates[0]
            elif candidates:
                return candidates[0]
            else:
                return None
    else:
        # No context: return first WordNet candidate (backward compatible)
        wn_candidates = [c for c in candidates if c.source == "wordnet"]
        if wn_candidates:
            return wn_candidates[0]
        else:
            return candidates[0]
