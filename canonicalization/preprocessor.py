"""
Phase 0: Text normalization (Preprocess).

Static, deterministic, local processing - no API calls.
Uses hardcoded dictionaries for all transformations.

Pipeline: lowercase -> strip -> expand abbreviations -> reduce MWEs ->
          normalize spelling -> normalize demonyms -> lemmatize
"""

import os
import re
from typing import Optional

# Static dict imports
from canonicalization.static_dicts.abbreviations import ABBREVIATIONS
from canonicalization.static_dicts.mwe_reductions import GENERAL_MWE, ATTRIBUTE_MWE
from canonicalization.static_dicts.spelling_variants import UK_TO_US
from canonicalization.static_dicts.demonyms import DEMONYMS

# Attributes where demonym -> country resolution is appropriate
_DEMONYM_ATTRIBUTES = frozenset({
    "nationality", "origin", "ethnicity", "country", "region",
    "state", "homeland", "citizenship", "place_of_origin",
    "country_of_origin", "made_in", "manufactured_in",
})

# Lazy-loaded components
_lemmatizer = None
_nltk_ready = False


def _ensure_lemmatizer():
    """Lazy-load NLTK WordNetLemmatizer."""
    global _lemmatizer, _nltk_ready
    if _nltk_ready:
        return _lemmatizer

    try:
        import nltk

        nltk_data_dir = os.path.join(os.path.dirname(__file__), "..", "nltk_data")
        nltk_data_dir = os.path.abspath(nltk_data_dir)
        os.makedirs(nltk_data_dir, exist_ok=True)
        if nltk_data_dir not in nltk.data.path:
            nltk.data.path.insert(0, nltk_data_dir)

        try:
            from nltk.stem import WordNetLemmatizer
            _lemmatizer = WordNetLemmatizer()
            # Test that wordnet data is available
            _lemmatizer.lemmatize("test")
        except LookupError:
            nltk.download("wordnet", download_dir=nltk_data_dir, quiet=True)
            nltk.download("omw-1.4", download_dir=nltk_data_dir, quiet=True)
            from nltk.stem import WordNetLemmatizer
            _lemmatizer = WordNetLemmatizer()

        _nltk_ready = True
    except Exception as e:
        print(f"Preprocessor: could not load lemmatizer: {e}")
        _nltk_ready = True  # Don't retry

    return _lemmatizer


def preprocess(value: str, attribute_key: Optional[str] = None) -> str:
    """
    Phase 0: All static, deterministic, no API calls.

    Pipeline: lowercase -> strip -> expand abbreviations -> reduce MWEs ->
              normalize spelling -> normalize demonyms -> lemmatize

    Args:
        value: The raw string to normalize.
        attribute_key: Optional attribute context (e.g., "condition", "fuel").

    Returns:
        Preprocessed string ready for disambiguation.
    """
    if not value or not isinstance(value, str):
        return value or ""

    # 1. Lowercase + strip + normalize whitespace
    text = value.lower().strip()
    text = re.sub(r"\s+", " ", text)

    # 2. Expand abbreviations (full-string first, then word-level)
    expanded = ABBREVIATIONS.get(text)
    if expanded:
        text = expanded
    else:
        words = text.split()
        expanded_words = []
        for w in words:
            expanded_words.append(ABBREVIATIONS.get(w, w))
        text = " ".join(expanded_words)

    # 3. Reduce MWEs (attribute-specific first, then general)
    if attribute_key:
        attr_key = attribute_key.lower()
        attr_mwe = ATTRIBUTE_MWE.get(attr_key, {})
        if text in attr_mwe:
            text = attr_mwe[text]
    if text in GENERAL_MWE:
        text = GENERAL_MWE[text]

    # 4. Normalize UK -> US spelling (word-level)
    words = text.split()
    normalized_words = [UK_TO_US.get(w, w) for w in words]
    text = " ".join(normalized_words)

    # 5. Normalize demonyms (only for nationality/origin/country attributes)
    if attribute_key and attribute_key.lower() in _DEMONYM_ATTRIBUTES:
        demonym_result = DEMONYMS.get(text)
        if demonym_result:
            text = demonym_result

    # 6. Lemmatize single-word terms
    words = text.split()
    if len(words) == 1:
        lemmatizer = _ensure_lemmatizer()
        if lemmatizer:
            try:
                lemma = lemmatizer.lemmatize(words[0])
                if lemma and len(lemma) > 1:
                    text = lemma
            except Exception:
                pass

    return text.strip()


def normalize_for_registry_lookup(text: str) -> str:
    """
    Strip spaces/hyphens/underscores for compound matching.

    "second hand" / "second-hand" / "secondhand" -> "secondhand"
    """
    if not text:
        return text
    return re.sub(r"[\s\-_]+", "", text.lower().strip())