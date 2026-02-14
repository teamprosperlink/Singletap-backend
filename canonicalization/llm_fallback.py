"""
LLM Fallback for Low-Confidence Disambiguation

Uses Llama-3.2-1B-Instruct for final sense selection when ensemble confidence is low.

Author: Claude (Hybrid WSD Implementation)
Date: 2026-02-13
"""

import os
import re
from typing import List, Optional
import torch

# Lazy import for transformers
_pipeline = None
_llm_instance = None


def _get_llm_pipeline():
    """Lazy load LLM pipeline to avoid startup penalty."""
    global _pipeline, _llm_instance

    if _llm_instance is None:
        try:
            from transformers import pipeline

            model_name = os.environ.get("LLM_FALLBACK_MODEL", "meta-llama/Llama-3.2-1B-Instruct")

            print(f"Loading LLM fallback model: {model_name}...")

            _llm_instance = pipeline(
                "text-generation",
                model=model_name,
                device="cpu",  # Run on CPU (1.2B model is CPU-friendly)
                torch_dtype=torch.float16,  # Use half-precision for speed
                max_length=512  # Limit context length
            )

            print("✅ LLM fallback model loaded")

        except Exception as e:
            print(f"⚠️ Warning: Failed to load LLM fallback: {e}")
            print("   LLM fallback will be disabled. Low-confidence cases will use top ensemble score.")
            _llm_instance = None

    return _llm_instance


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


class LLMFallback:
    """
    LLM-based fallback for disambiguation edge cases.

    Uses Llama-3.2-1B-Instruct to select best sense when ensemble confidence is low.
    Invoked only when: (top_score - second_best_score) < threshold
    """

    def __init__(self):
        """Initialize LLM fallback."""
        self.llm = _get_llm_pipeline()
        self.enabled = self.llm is not None

        # Check environment flag
        if os.environ.get("ENABLE_LLM_FALLBACK", "1") == "0":
            print("LLM fallback disabled via ENABLE_LLM_FALLBACK=0")
            self.enabled = False

    def is_available(self) -> bool:
        """Check if LLM fallback is available."""
        return self.enabled and self.llm is not None

    def disambiguate(self,
                    query: str,
                    term: str,
                    candidates: List[CandidateSense],
                    top_scores: List[float],
                    top_k: int = 3) -> int:
        """
        Select best sense using LLM reasoning.

        Args:
            query: Full query context
            term: Ambiguous word
            candidates: All candidate senses
            top_scores: Scores from ensemble (parallel to candidates)
            top_k: Number of top candidates to present to LLM (default 3)

        Returns:
            Index of selected candidate (0-based)
        """
        if not self.is_available():
            # LLM not available, return best from ensemble
            return top_scores.index(max(top_scores))

        try:
            # Get top-k candidates by ensemble score
            top_indices = sorted(
                range(len(top_scores)),
                key=lambda i: top_scores[i],
                reverse=True
            )[:top_k]

            top_candidates = [candidates[i] for i in top_indices]

            # Format prompt
            prompt = self._format_prompt(query, term, top_candidates)

            # Query LLM
            result = self.llm(
                prompt,
                max_new_tokens=10,
                temperature=0.0,  # Deterministic
                do_sample=False,
                pad_token_id=self.llm.tokenizer.eos_token_id  # Prevent padding warning
            )

            # Parse LLM output
            llm_choice = self._parse_choice(result[0]["generated_text"])

            # Map back to original candidate index
            if llm_choice is not None and 0 <= llm_choice < len(top_indices):
                selected_idx = top_indices[llm_choice]
                print(f"  LLM fallback selected candidate {llm_choice+1}/{top_k} "
                      f"(idx={selected_idx}, source={candidates[selected_idx].source})")
                return selected_idx
            else:
                # Parsing failed, return top from ensemble
                print(f"  LLM fallback parsing failed, using top ensemble score")
                return top_indices[0]

        except Exception as e:
            print(f"⚠️ LLM fallback error: {e}")
            # Fall back to top ensemble score
            return top_scores.index(max(top_scores))

    def _format_prompt(self, query: str, term: str, candidates: List[CandidateSense]) -> str:
        """
        Format structured prompt for Llama-3.2-1B.

        Prompt structure:
        - Clear instruction
        - Numbered glosses
        - Explicit output format requirement
        """
        # Build numbered gloss list
        glosses = "\n".join([
            f"{i+1}. {c.gloss}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""Given the sentence: "{query}"

Which definition of "{term}" fits best?

{glosses}

Reply with only the number (1, 2, or 3):"""

        return prompt

    def _parse_choice(self, output: str) -> Optional[int]:
        """
        Extract choice number from LLM output.

        Expects output like "3" or "The answer is 2" or similar.
        Returns 0-based index (output "1" → return 0).
        """
        try:
            # Look for any digit 1-9 in the output
            match = re.search(r'\b([1-9])\b', output)

            if match:
                choice = int(match.group(1))
                # Convert to 0-based index
                return choice - 1
            else:
                return None

        except Exception as e:
            print(f"⚠️ LLM output parsing error: {e}")
            return None


# Singleton instance
_llm_fallback_instance = None


def get_llm_fallback() -> LLMFallback:
    """
    Get singleton instance of LLMFallback.

    Returns:
        LLMFallback instance
    """
    global _llm_fallback_instance

    if _llm_fallback_instance is None:
        _llm_fallback_instance = LLMFallback()

    return _llm_fallback_instance


def should_use_llm_fallback(scores: List[float], threshold: float = None) -> bool:
    """
    Check if LLM fallback should be triggered based on confidence margin.

    Args:
        scores: List of scores from ensemble
        threshold: Confidence threshold (defaults to env var or 0.10)

    Returns:
        True if confidence is too low (should trigger fallback)
    """
    if threshold is None:
        threshold = float(os.environ.get("HYBRID_CONFIDENCE_THRESHOLD", "0.10"))

    if len(scores) < 2:
        return False

    # Sort scores in descending order
    sorted_scores = sorted(scores, reverse=True)

    # Calculate margin between top and second-best
    margin = sorted_scores[0] - sorted_scores[1]

    return margin < threshold
