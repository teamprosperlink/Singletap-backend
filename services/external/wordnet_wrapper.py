"""
WordNet wrapper for local synonym and hierarchy resolution via NLTK.

WordNet is a lexical database that provides:
- Synsets (synonym sets) for words
- Hypernyms (parent concepts): "dog" -> "canine" -> "animal"
- Hyponyms (child concepts): "animal" -> "dog", "cat"
- Lemmas (synonyms within a synset)

Runs entirely locally via NLTK - no API calls, no rate limits.
"""

import os
from typing import Dict, List, Optional, Tuple

# Lazy-load nltk to avoid import overhead at startup
_wn = None
_nltk_ready = False


def _ensure_nltk():
    """Download WordNet data if not already present."""
    global _wn, _nltk_ready
    if _nltk_ready:
        return _wn

    import nltk
    # Set NLTK data path to a project-local directory to avoid permission issues
    nltk_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "nltk_data")
    nltk_data_dir = os.path.abspath(nltk_data_dir)
    os.makedirs(nltk_data_dir, exist_ok=True)
    if nltk_data_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_data_dir)

    try:
        from nltk.corpus import wordnet
        # Test if data is available
        wordnet.synsets("test")
        _wn = wordnet
    except LookupError:
        nltk.download("wordnet", download_dir=nltk_data_dir, quiet=True)
        nltk.download("omw-1.4", download_dir=nltk_data_dir, quiet=True)
        from nltk.corpus import wordnet
        _wn = wordnet

    _nltk_ready = True
    return _wn


class WordNetClient:
    """
    Client for querying WordNet via NLTK.

    Provides synonym, hypernym, and hyponym lookups entirely locally.
    Thread-safe (NLTK corpus readers are read-only after load).
    """

    def __init__(self):
        self._wn = None

    def _get_wn(self):
        """Lazy-load wordnet module."""
        if self._wn is None:
            self._wn = _ensure_nltk()
        return self._wn

    def get_synsets(self, term: str, pos=None) -> list:
        """Get all synsets for a term."""
        wn = self._get_wn()
        if wn is None:
            return []
        # Replace spaces with underscores for multi-word terms
        lemma = term.lower().replace(" ", "_")
        return wn.synsets(lemma, pos=pos)

    def get_synonyms(self, term: str) -> List[str]:
        """
        Get all synonyms for a term across all synsets.

        Returns deduplicated list of synonym strings (lowercased).
        """
        synsets = self.get_synsets(term)
        synonyms = set()

        for ss in synsets:
            for lemma in ss.lemmas():
                name = lemma.name().replace("_", " ").lower()
                synonyms.add(name)

        # Remove the original term itself
        synonyms.discard(term.lower().replace("_", " "))
        return sorted(synonyms)

    def get_synonyms_from_best_synset(self, term: str) -> Tuple[List[str], Optional[str]]:
        """
        Get synonyms from the most relevant synset (first match).

        Returns (synonyms, synset_name) tuple.
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return [], None

        best = synsets[0]
        synonyms = set()
        for lemma in best.lemmas():
            name = lemma.name().replace("_", " ").lower()
            synonyms.add(name)

        return sorted(synonyms), best.name()

    def get_hypernyms(self, term: str, depth: int = 1) -> List[str]:
        """
        Get hypernyms (parent concepts) for a term.

        Args:
            term: The word to look up
            depth: How many levels up to traverse (1 = direct parents only)
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return []

        hypernyms = set()
        to_visit = [(synsets[0], 0)]
        visited = set()

        while to_visit:
            ss, d = to_visit.pop(0)
            if ss in visited or d >= depth:
                continue
            visited.add(ss)

            for hyper in ss.hypernyms():
                for lemma in hyper.lemmas():
                    name = lemma.name().replace("_", " ").lower()
                    hypernyms.add(name)
                if d + 1 < depth:
                    to_visit.append((hyper, d + 1))

        return sorted(hypernyms)

    def get_hyponyms(self, term: str) -> List[str]:
        """Get hyponyms (child concepts) for a term."""
        synsets = self.get_synsets(term)
        if not synsets:
            return []

        hyponyms = set()
        for hypo in synsets[0].hyponyms():
            for lemma in hypo.lemmas():
                name = lemma.name().replace("_", " ").lower()
                hyponyms.add(name)

        return sorted(hyponyms)

    def get_hierarchy(self, term: str) -> Optional[Dict]:
        """
        Get full hierarchy information for a term.

        Returns dict with parents, children, related (synonyms).
        Compatible with the interface ConceptNet used to provide.
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return None

        parents = self.get_hypernyms(term, depth=1)
        children = self.get_hyponyms(term)
        synonyms = self.get_synonyms(term)

        if not parents and not children and not synonyms:
            return None

        return {
            "term": term,
            "parents": parents,
            "children": children,
            "related": synonyms,
        }

    def get_glosses_per_synset(self, term: str) -> List[Dict]:
        """
        Get glosses and lemmas for each synset of a term.

        Returns per-synset data so the disambiguator can score each sense
        against context (fixes the old blind first-synset selection).

        Returns:
            [
                {
                    "synset_name": "car.n.01",
                    "gloss": "a motor vehicle with four wheels...",
                    "lemmas": ["car", "auto", "automobile", "machine"],
                    "hypernyms": ["motor vehicle"]
                },
                ...
            ]
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return []

        results = []
        for ss in synsets:
            lemmas = []
            for lemma in ss.lemmas():
                name = lemma.name().replace("_", " ").lower()
                lemmas.append(name)

            hypernyms = []
            for hyper in ss.hypernyms():
                for hl in hyper.lemmas():
                    hypernyms.append(hl.name().replace("_", " ").lower())
                    break  # Just first lemma per hypernym synset

            results.append({
                "synset_name": ss.name(),
                "gloss": ss.definition() or "",
                "lemmas": lemmas,
                "hypernyms": hypernyms,
            })

        return results

    def find_path_to_root(self, term: str, max_depth: int = 5) -> List[List[str]]:
        """
        Find path(s) from term to root concept via hypernym chains.

        Compatible with the interface ConceptNet's find_path_to_root provided.
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return []

        paths = []
        best = synsets[0]

        for path in best.hypernym_paths():
            # WordNet returns paths from root to leaf, we want leaf to root
            labels = []
            for ss in reversed(path):
                name = ss.lemmas()[0].name().replace("_", " ").lower()
                labels.append(name)
            if len(labels) <= max_depth:
                paths.append(labels)

        return paths

    def get_synset_offset_id(self, synset) -> str:
        """
        Extract WordNet synset offset ID in standard format.

        Format: 8-digit offset + hyphen + POS character
        Example: car.n.01 → "02958343-n"

        Args:
            synset: NLTK synset object

        Returns:
            Synset ID string (e.g., "02958343-n")
        """
        offset = str(synset.offset()).zfill(8)
        pos_char = synset.pos()  # n, v, a, r, s
        return f"{offset}-{pos_char}"

    def disambiguate_synsets(self, synsets: list, context: str):
        """
        Disambiguate synsets using gloss-context embedding similarity.

        Uses shared SentenceTransformer from embedding/model_provider.py

        Args:
            synsets: List of NLTK synset objects
            context: Context string for disambiguation (e.g., "condition", "electronics")

        Returns:
            Best synset based on gloss-context similarity
        """
        if not synsets or not context:
            return synsets[0] if synsets else None

        if len(synsets) == 1:
            return synsets[0]

        try:
            from embedding.model_provider import get_embedding_model
            import numpy as np

            model = get_embedding_model()
            context_emb = model.encode(context)

            best_synset = synsets[0]
            best_score = -1.0

            for synset in synsets:
                gloss = synset.definition()
                if not gloss:
                    continue

                gloss_emb = model.encode(gloss)
                score = np.dot(context_emb, gloss_emb) / (
                    np.linalg.norm(context_emb) * np.linalg.norm(gloss_emb)
                )

                if score > best_score:
                    best_score = score
                    best_synset = synset

            return best_synset

        except Exception as e:
            print(f"WordNet disambiguation error: {e}")
            return synsets[0]

    def get_canonical(self, term: str, context: Optional[str] = None) -> Optional[Dict]:
        """
        Get canonical form with WordNet synset ID as concept_id.

        This is the NEW method for Path A that returns synset IDs instead of labels.

        Args:
            term: Word/phrase to canonicalize
            context: Attribute key for disambiguation (e.g., "condition", "electronics")

        Returns:
            {
                "canonical_id": "02958343-n",  # Synset offset ID
                "canonical_label": "car",      # Preferred lemma
                "all_forms": ["car", "auto", "automobile", "machine"],
                "hypernyms": ["motor vehicle"],
                "gloss": "a motor vehicle with four wheels...",
                "source": "wordnet"
            }

            Returns None if term not found in WordNet.
        """
        synsets = self.get_synsets(term)
        if not synsets:
            return None

        # GENERIC: Always prefer noun/adjective synsets over verbs/adverbs
        # This works for ANY domain (not hardcoded contexts)
        # Rationale: Item types, attributes, categories are almost always nouns/adjectives
        noun_adj_synsets = [s for s in synsets if s.pos() in ['n', 'a', 's']]
        if noun_adj_synsets:
            synsets = noun_adj_synsets

        # Disambiguation if context provided
        if context and len(synsets) > 1:
            best_synset = self.disambiguate_synsets(synsets, context)
        else:
            best_synset = synsets[0]

        # Extract synset ID (offset format: 8 digits + POS char)
        synset_id = self.get_synset_offset_id(best_synset)

        # Extract all lemmas (synonyms)
        all_forms = []
        for lemma in best_synset.lemmas():
            name = lemma.name().replace("_", " ").lower()
            all_forms.append(name)

        # Extract hypernyms
        hypernyms = []
        for hyper in best_synset.hypernyms():
            for hl in hyper.lemmas():
                hypernyms.append(hl.name().replace("_", " ").lower())
                break  # Just first lemma per hypernym

        # Extract gloss
        gloss = best_synset.definition() or ""

        return {
            "canonical_id": synset_id,
            "canonical_label": all_forms[0] if all_forms else term.lower(),
            "all_forms": all_forms,
            "hypernyms": hypernyms,
            "gloss": gloss,
            "source": "wordnet"
        }


# Global singleton instance
_wordnet_client: Optional[WordNetClient] = None


def get_wordnet_client() -> WordNetClient:
    """Get singleton WordNet client instance."""
    global _wordnet_client

    if _wordnet_client is None:
        _wordnet_client = WordNetClient()

    return _wordnet_client
