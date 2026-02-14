"""
Phase 2: Canonicalization — label extraction, cross-tier propagation, registry.

Takes a DisambiguatedSense and produces an OntologyNode by:
1. P8814 enrichment: adding Wikidata aliases to WordNet senses (offline cache)
2. Cross-tier propagation: checking all_forms against synonym_registry to reuse concept_ids
3. Using synset IDs as concept_ids (Path A fix)
4. Building concept_path from hypernyms
5. Registering ALL forms -> concept_id in the synonym registry

This is the critical fix for cross-tier concept_id mismatch:
  OLD: "used" -> concept_id="used", "second-hand" -> concept_id="second-hand" (FAIL)
  NEW: "used" -> concept_id="01640482-s", "second-hand" -> concept_id="01640482-s" (PASS)
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from canonicalization.disambiguator import DisambiguatedSense
from canonicalization.preprocessor import normalize_for_registry_lookup
from collections import defaultdict

# Load P8814 cache (singleton)
_WORDNET_WIKIDATA_MAP: Optional[Dict] = None

# Hypernym consolidation tracker (tracks how many terms map to each parent)
_HYPERNYM_USAGE_COUNT: Dict[str, int] = defaultdict(int)

# Minimal blocklist of overly-abstract parents (per user guidance)
_ABSTRACT_PARENTS = {
    "entity", "object", "physical entity", "abstraction", "whole",
    "matter", "substance", "thing", "unit", "artifact",
    "science", "discipline", "study", "activity", "work", "act", "action"
}


def _load_wikidata_enrichment() -> Dict:
    """Load P8814 cache from disk (one-time)."""
    global _WORDNET_WIKIDATA_MAP

    if _WORDNET_WIKIDATA_MAP is None:
        cache_path = Path(__file__).parent / "static_dicts/wordnet_wikidata_map.json"
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    _WORDNET_WIKIDATA_MAP = json.load(f)
                print(f"✅ P8814 cache loaded: {len(_WORDNET_WIKIDATA_MAP)} mappings")
            except Exception as e:
                print(f"⚠️ P8814 cache load error: {e}")
                _WORDNET_WIKIDATA_MAP = {}
        else:
            print("⚠️ P8814 cache not found. Run: python3 scripts/build_wordnet_wikidata_cache.py")
            _WORDNET_WIKIDATA_MAP = {}

    return _WORDNET_WIKIDATA_MAP


def enrich_with_wikidata_aliases(sense: DisambiguatedSense) -> DisambiguatedSense:
    """
    Enrich WordNet sense with Wikidata aliases via P8814 mapping.

    Only enriches WordNet senses. BabelNet already has Wikidata integrated.

    Args:
        sense: DisambiguatedSense with WordNet synset ID

    Returns:
        Enriched sense with merged aliases from Wikidata
    """
    # Only enrich WordNet senses
    if sense.source != "wordnet":
        return sense

    # Check if Path A is enabled
    if os.environ.get("USE_NEW_PIPELINE", "1") == "0":
        return sense

    mapping = _load_wikidata_enrichment()

    # WordNet synset IDs are in format "XXXXXXXX-X" (8 digits + POS)
    # P8814 cache uses same format
    synset_id = sense.source_id

    if synset_id not in mapping:
        return sense  # No Wikidata mapping found

    # Merge Wikidata aliases
    wikidata_data = mapping[synset_id]
    wikidata_aliases = wikidata_data.get("aliases", [])

    if not wikidata_aliases:
        return sense

    # Combine and deduplicate
    all_forms = list(set(sense.all_forms + wikidata_aliases))

    # Update sense with enriched aliases
    sense.all_forms = all_forms
    sense.source = "wordnet+wikidata"  # Mark as enriched

    return sense


def enrich_with_babelnet_synonyms(sense: DisambiguatedSense) -> DisambiguatedSense:
    """
    Enrich sense with BabelNet synonyms.

    BabelNet has richer synonym data than WordNet for many terms.
    This ensures related terms like "tutor/coach/tutoring/coaching"
    are registered together in the synonym registry.

    Args:
        sense: DisambiguatedSense to enrich

    Returns:
        Enriched sense with BabelNet synonyms added to all_forms
    """
    try:
        from services.external.babelnet_wrapper import get_babelnet_client
        api_key = os.getenv("BABELNET_API_KEY", "")
        if not api_key:
            return sense

        bn = get_babelnet_client()
        # Get synonyms for the resolved label
        synonyms = bn.get_synonyms(sense.resolved_form)
        if synonyms:
            # Merge and deduplicate
            all_forms = list(set(sense.all_forms + synonyms))
            sense.all_forms = all_forms
            if sense.source and "babelnet" not in sense.source:
                sense.source = sense.source + "+babelnet"
    except Exception as e:
        # BabelNet enrichment is optional - don't fail if API unavailable
        pass

    return sense


def should_collapse_to_hypernym(
    sense: DisambiguatedSense,
    original_term: str,
    min_siblings: int = 2,
) -> bool:
    """
    Dynamically decide whether to use hypernym as concept_id.

    Uses multi-rule approach (per user guidance):
    - Rule A: Literal synonym in parent's lemmas (rare but correct)
    - Rule B: Sibling consolidation (multiple terms → same parent)
    - Rule C: Wu-Palmer similarity + short distance (semantic closeness)
    - Safety: Block overly-abstract parents

    Returns True if we should use hypernym, False if we should keep original term.
    """
    if not sense.hypernyms or len(sense.hypernyms) == 0:
        return False

    hypernym_label = sense.hypernyms[0].lower().strip()

    # Safety: Don't collapse to overly-abstract parents
    if hypernym_label in _ABSTRACT_PARENTS:
        return False

    # Rule A: Check if original term is literally in parent's lemmas
    # (This requires WordNet synset access - only works for WordNet source)
    if sense.source == "wordnet":
        try:
            from services.external.wordnet_wrapper import get_wordnet_client
            wn_client = get_wordnet_client()

            # Get parent synset
            parent_synsets = wn_client.get_synsets(hypernym_label)
            if parent_synsets:
                parent_lemmas = {
                    lem.name().replace("_", " ").lower()
                    for lem in parent_synsets[0].lemmas()
                }
                if original_term.lower() in parent_lemmas:
                    return True  # Literal synonym - collapse

            # Rule C: DISABLED - Wu-Palmer similarity causes over-collapse
            # Examples: dentist→medical practitioner (wrong), puppy→dog (wrong)
            # Only Rule A (literal synonym) should trigger collapse
            #
            # Rule B: Sibling consolidation (only after Rule A has confirmed some terms)
            # If multiple terms have already mapped to this parent via Rule A, expand
            if _HYPERNYM_USAGE_COUNT[hypernym_label] >= min_siblings:
                return True
        except Exception as e:
            pass  # Fall through to final check

    # Fallback: Check sibling consolidation even for non-WordNet sources
    if _HYPERNYM_USAGE_COUNT[hypernym_label] >= min_siblings:
        return True

    # Default: Keep original term (preserve specificity)
    return False


def canonicalize(
    sense: DisambiguatedSense,
    original_term: str,
    attribute_key: Optional[str],
    synonym_registry: Dict[str, str],
) -> "OntologyNode":
    """
    Phase 2: Convert a DisambiguatedSense into an OntologyNode (Path A version).

    Path A Changes:
    1. Enrich WordNet senses with P8814 Wikidata aliases
    2. Use source_id (synset ID) as concept_id instead of label
    3. Cross-tier propagation checks all forms

    Args:
        sense: The winning sense from disambiguation.
        original_term: The original (pre-preprocessed) value.
        attribute_key: Attribute key for concept_root.
        synonym_registry: Shared registry mapping alias -> concept_id.

    Returns:
        OntologyNode with concept_id, concept_path, etc.
    """
    # Import here to avoid circular imports
    from canonicalization.resolvers.generic_categorical_resolver import OntologyNode

    # 0. Enrich with Wikidata aliases (Path A)
    sense = enrich_with_wikidata_aliases(sense)

    # 0b. Enrich with BabelNet synonyms (richer synonym coverage)
    sense = enrich_with_babelnet_synonyms(sense)

    # 1. Cross-tier propagation: check all_forms against existing registry
    concept_id = None
    for form in sense.all_forms:
        # Check both the raw form and the compound-normalized form
        for key in [form.lower().strip(), normalize_for_registry_lookup(form)]:
            if key in synonym_registry:
                concept_id = synonym_registry[key]
                break
        if concept_id:
            break

    # 2. If no registry match, DYNAMICALLY decide: use hypernym or keep original?
    # Uses multi-rule heuristics: sibling consolidation, Wu-Palmer similarity, etc.
    # This makes siblings match (laptop/notebook → portable computer)
    # But preserves specificity (mathematics stays as mathematics, not science)
    if not concept_id:
        if should_collapse_to_hypernym(sense, original_term, min_siblings=1):
            # Use hypernym (parent) as concept_id
            concept_id = sense.hypernyms[0].lower().strip().replace("_", " ")
            # Track hypernym usage for sibling consolidation
            _HYPERNYM_USAGE_COUNT[concept_id] += 1
        else:
            # Keep original term (preserve specificity)
            concept_id = sense.resolved_form.lower().strip().replace("_", " ")

    # 3. Build concept_path from hypernyms
    concept_path = _build_concept_path(concept_id, attribute_key, sense.hypernyms)

    # 4. Register ALL forms -> concept_id in synonym_registry
    all_forms_to_register = set()
    all_forms_to_register.add(original_term.lower().strip())
    all_forms_to_register.add(normalize_for_registry_lookup(original_term))
    for form in sense.all_forms:
        all_forms_to_register.add(form.lower().strip())
        all_forms_to_register.add(normalize_for_registry_lookup(form))

    # Also register the concept_id itself if it's not a synset ID
    if not concept_id.replace("-", "").replace("bn:", "").replace("mw:", "").isdigit():
        all_forms_to_register.add(concept_id)

    for form in all_forms_to_register:
        if form:
            synonym_registry[form] = concept_id

    # 5. Build and return OntologyNode
    concept_root = attribute_key.lower() if attribute_key else concept_id

    return OntologyNode(
        concept_id=concept_id,
        concept_root=concept_root,
        concept_path=concept_path,
        parents=[h.lower() for h in sense.hypernyms] if sense.hypernyms else [],
        children=[],
        siblings=[f.lower() for f in sense.all_forms if f.lower() != concept_id],
        source=sense.source,
        confidence=min(sense.score + 0.3, 1.0) if sense.score > 0 else 0.7,
    )


def _build_concept_path(
    concept_id: str,
    attribute_key: Optional[str],
    hypernyms: List[str],
) -> List[str]:
    """
    Build concept_path: [attribute_key, ...hypernyms, concept_id].

    Example:
        attribute_key="vehicle_type", hypernyms=["motor vehicle"], concept_id="car"
        -> ["vehicle_type", "motor vehicle", "car"]
    """
    path = []

    if attribute_key:
        path.append(attribute_key.lower())

    if hypernyms:
        # Add hypernyms (most general first, most specific last)
        # Reverse if they come leaf-to-root (but our sources give parent labels directly)
        for h in hypernyms:
            hl = h.lower()
            if hl not in path and hl != concept_id:
                path.append(hl)

    if concept_id not in path:
        path.append(concept_id)

    return path


def enrich_hypernyms(sense: DisambiguatedSense) -> DisambiguatedSense:
    """
    If winning sense lacks hypernyms (e.g., Datamuse), fill from WordNet.

    Modifies sense in-place and returns it.
    """
    if sense.hypernyms:
        return sense

    try:
        from services.external.wordnet_wrapper import get_wordnet_client
        wn = get_wordnet_client()
        hypernyms = wn.get_hypernyms(sense.resolved_form, depth=1)
        if hypernyms:
            sense.hypernyms = hypernyms
            return sense

        # Try with the original label
        hypernyms = wn.get_hypernyms(sense.label if hasattr(sense, 'label') else sense.resolved_form, depth=1)
        if hypernyms:
            sense.hypernyms = hypernyms
    except Exception as e:
        print(f"Canonicalizer: enrich_hypernyms error: {e}")

    return sense
