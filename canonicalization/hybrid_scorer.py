"""
Hybrid Sense Scorer - Multi-Model Ensemble for WSD

Implements a 3-model ensemble for accurate word sense disambiguation:
1. Gloss-Transformer Scorer (Primary, 50%): DistilBERT fine-tuned on SemCor
2. Embedding Similarity Scorer (Secondary, 35%): all-MiniLM-L6-v2
3. Knowledge-Based Scorer (Tertiary, 15%): WordNet path similarity

Author: Claude (Hybrid WSD Implementation)
Date: 2026-02-13
"""

import os
from typing import List, Optional, Tuple
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Lazy imports for NLTK
_wordnet = None

def _get_wordnet():
    """Lazy load WordNet to avoid startup penalty."""
    global _wordnet
    if _wordnet is None:
        from nltk.corpus import wordnet
        _wordnet = wordnet
    return _wordnet


class CandidateSense:
    """Data class for candidate senses (matches disambiguator.py structure)."""
    def __init__(self, source: str, source_id: str, label: str,
                 gloss: str, all_forms: List[str], hypernyms: List[str], score: float = 0.0):
        self.source = source
        self.source_id = source_id
        self.label = label
        self.gloss = gloss
        self.all_forms = all_forms
        self.hypernyms = hypernyms
        self.score = score


class HybridSenseScorer:
    """
    Multi-model ensemble scorer for WSD.

    Combines three specialized scorers:
    - Gloss-Transformer: Deep contextual matching (DistilBERT)
    - Embedding Similarity: Efficient semantic alignment (MiniLM)
    - Knowledge-Based: Symbolic relational scoring (WordNet)

    Ensemble weights: 0.5 (transformer) + 0.35 (embedding) + 0.15 (knowledge)
    """

    def __init__(self, model_path: Optional[str] = None, weights: Optional[Tuple[float, float, float]] = None):
        """
        Initialize hybrid scorer.

        Args:
            model_path: Path to fine-tuned DistilBERT model (or None for base)
            weights: Tuple of (transformer_weight, embedding_weight, knowledge_weight)
                    Defaults to (0.5, 0.35, 0.15)
        """
        # Parse weights from env var or use defaults
        # Default: Disable transformer (not fine-tuned), use embedding + knowledge
        # Once transformer is properly fine-tuned, change to "0.5,0.35,0.15"
        if weights is None:
            weights_str = os.environ.get("HYBRID_WEIGHTS", "0.0,0.7,0.3")
            weights = tuple(map(float, weights_str.split(",")))

        self.transformer_weight, self.embedding_weight, self.knowledge_weight = weights

        # Normalize weights to sum to 1.0
        total = sum(weights)
        self.transformer_weight /= total
        self.embedding_weight /= total
        self.knowledge_weight /= total

        print(f"Hybrid scorer weights: T={self.transformer_weight:.2f}, "
              f"E={self.embedding_weight:.2f}, K={self.knowledge_weight:.2f}")

        # Load models
        # Skip transformer if weight is 0 (saves memory and startup time)
        if self.transformer_weight > 0:
            self._load_transformer_model(model_path)
        else:
            print("Transformer weight is 0 - skipping transformer model (using embedding + knowledge only)")
            self.transformer_model = None
            self.tokenizer = None

        self._load_embedding_model()

    def _load_transformer_model(self, model_path: Optional[str]):
        """Load GlossBERT/DistilBERT for gloss-context scoring."""
        try:
            # Priority order:
            # 1. Custom fine-tuned model (if path provided)
            # 2. GlossBERT (pre-trained on SemCor) - LOCAL
            # 3. GlossBERT (download from HuggingFace)
            # 4. Base DistilBERT (fallback)

            if model_path and os.path.exists(model_path):
                # Use custom fine-tuned model if available
                print(f"Loading fine-tuned transformer model from {model_path}...")
                self.transformer_model = AutoModelForSequenceClassification.from_pretrained(model_path)
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)

            elif os.path.exists("models/glossbert"):
                # Use local GlossBERT (pre-trained on SemCor)
                print("Loading GlossBERT model (fine-tuned on SemCor 3.0)...")
                self.transformer_model = AutoModelForSequenceClassification.from_pretrained(
                    "models/glossbert",
                    num_labels=2
                )
                self.tokenizer = AutoTokenizer.from_pretrained("models/glossbert")

            else:
                # Try to download GlossBERT from HuggingFace
                print("Downloading GlossBERT from HuggingFace (first time)...")
                self.transformer_model = AutoModelForSequenceClassification.from_pretrained(
                    "kanishka/GlossBERT",
                    num_labels=2
                )
                self.tokenizer = AutoTokenizer.from_pretrained("kanishka/GlossBERT")
                print("   (Saving to models/glossbert for future use)")
                os.makedirs("models/glossbert", exist_ok=True)
                self.transformer_model.save_pretrained("models/glossbert")
                self.tokenizer.save_pretrained("models/glossbert")

            self.transformer_model.eval()  # Set to evaluation mode
            print("✅ Transformer model loaded")

        except Exception as e:
            print(f"⚠️ Warning: Failed to load transformer model: {e}")
            print("   Transformer scoring will be disabled.")
            self.transformer_model = None
            self.tokenizer = None

    def _load_embedding_model(self):
        """Load SentenceTransformer for embedding similarity."""
        try:
            from embedding.model_provider import get_embedding_model
            self.embedding_model = get_embedding_model()
            print("✅ Embedding model loaded (reusing all-MiniLM-L6-v2)")
        except Exception as e:
            print(f"⚠️ Warning: Failed to load embedding model: {e}")
            print("   Embedding scoring will be disabled.")
            self.embedding_model = None

    def score_candidates(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        """
        Score all candidate senses using hybrid ensemble.

        Args:
            context: Query sentence or context string
            candidates: List of CandidateSense objects

        Returns:
            List of ensemble scores (one per candidate), range [0, 1]
        """
        if not candidates:
            return []

        # Score with each model
        transformer_scores = self._score_with_transformer(context, candidates)
        embedding_scores = self._score_with_embeddings(context, candidates)
        knowledge_scores = self._score_with_knowledge(context, candidates)

        # Normalize each scorer's output to [0, 1]
        transformer_scores = self._normalize_scores(transformer_scores)
        embedding_scores = self._normalize_scores(embedding_scores)
        knowledge_scores = self._normalize_scores(knowledge_scores)

        # Weighted ensemble
        ensemble_scores = [
            self.transformer_weight * t +
            self.embedding_weight * e +
            self.knowledge_weight * k
            for t, e, k in zip(transformer_scores, embedding_scores, knowledge_scores)
        ]

        return ensemble_scores

    def _score_with_transformer(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        """
        Score candidates using DistilBERT gloss-context matching.

        Input format: [CLS] context [SEP] gloss [SEP]
        Output: Relevance score from classification head
        """
        if self.transformer_model is None or self.tokenizer is None:
            # Transformer disabled, return neutral scores
            return [0.5] * len(candidates)

        scores = []

        try:
            with torch.no_grad():
                for candidate in candidates:
                    # Format as sentence pair: (context, gloss)
                    inputs = self.tokenizer(
                        context,
                        candidate.gloss,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=128
                    )

                    # Forward pass
                    outputs = self.transformer_model(**inputs)

                    # Get probability for "relevant" class (index 1)
                    logits = outputs.logits[0]
                    probs = torch.softmax(logits, dim=0)
                    score = probs[1].item()  # P(relevant)

                    scores.append(score)

        except Exception as e:
            print(f"⚠️ Transformer scoring error: {e}")
            scores = [0.5] * len(candidates)

        return scores

    def _score_with_embeddings(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        """
        Score candidates using cosine similarity between context and gloss embeddings.

        Uses existing all-MiniLM-L6-v2 model.
        """
        if self.embedding_model is None:
            # Embedding model disabled, return neutral scores
            return [0.5] * len(candidates)

        try:
            # Encode context
            context_emb = self.embedding_model.encode(context, convert_to_numpy=True)

            # Encode all glosses in batch
            glosses = [c.gloss for c in candidates]
            gloss_embs = self.embedding_model.encode(glosses, convert_to_numpy=True)

            # Compute cosine similarity
            similarities = cosine_similarity([context_emb], gloss_embs)[0]

            # Convert to list and ensure non-negative (cosine can be negative)
            scores = [max(0.0, float(sim)) for sim in similarities]

            return scores

        except Exception as e:
            print(f"⚠️ Embedding scoring error: {e}")
            return [0.5] * len(candidates)

    def _score_with_knowledge(self, context: str, candidates: List[CandidateSense]) -> List[float]:
        """
        Score candidates using WordNet path similarity.

        Computes structural similarity between candidate synsets and context words.
        """
        try:
            wordnet = _get_wordnet()
        except Exception as e:
            print(f"⚠️ WordNet not available: {e}")
            return [0.0] * len(candidates)

        scores = []

        try:
            # Extract meaningful words from context (nouns, verbs)
            context_tokens = [w.lower() for w in context.split() if len(w) > 3]

            # Get synsets for context words
            context_synsets = []
            for token in context_tokens[:5]:  # Limit to first 5 meaningful words
                context_synsets.extend(wordnet.synsets(token)[:3])  # Top 3 synsets per word

            if not context_synsets:
                # No context synsets found, return neutral scores
                return [0.0] * len(candidates)

            # Score each candidate
            for candidate in candidates:
                max_similarity = 0.0

                # Only compute for WordNet candidates with synset IDs
                if candidate.source == "wordnet" and candidate.source_id:
                    try:
                        # Get candidate synset
                        candidate_synset = wordnet.synset(candidate.source_id)

                        # Compute max path similarity with any context synset
                        for ctx_synset in context_synsets:
                            similarity = candidate_synset.path_similarity(ctx_synset)
                            if similarity and similarity > max_similarity:
                                max_similarity = similarity

                    except Exception:
                        # Invalid synset ID or computation error
                        pass

                scores.append(max_similarity)

        except Exception as e:
            print(f"⚠️ Knowledge scoring error: {e}")
            scores = [0.0] * len(candidates)

        return scores

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """
        Normalize scores to [0, 1] range using min-max scaling.

        If all scores are equal, returns uniform distribution.
        """
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        # Check for uniform scores
        if max_score == min_score:
            return [0.5] * len(scores)

        # Min-max normalization
        normalized = [
            (score - min_score) / (max_score - min_score)
            for score in scores
        ]

        return normalized


# Singleton instance
_hybrid_scorer_instance = None


def get_hybrid_scorer(model_path: Optional[str] = None,
                     weights: Optional[Tuple[float, float, float]] = None) -> HybridSenseScorer:
    """
    Get singleton instance of HybridSenseScorer.

    Args:
        model_path: Path to fine-tuned model (only used on first call)
        weights: Ensemble weights (only used on first call)

    Returns:
        HybridSenseScorer instance
    """
    global _hybrid_scorer_instance

    if _hybrid_scorer_instance is None:
        # Check environment for model path
        if model_path is None:
            model_path = os.environ.get("DISTILBERT_WSD_MODEL_PATH")

        _hybrid_scorer_instance = HybridSenseScorer(model_path=model_path, weights=weights)

    return _hybrid_scorer_instance
