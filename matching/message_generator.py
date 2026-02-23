"""
VRIDDHI MATCHING SYSTEM - LLM MESSAGE GENERATOR
Smart message generation using DistilGPT2 ONNX int8

Purpose: Generate natural, human-friendly messages for similar matches
using a small local LLM model (~60MB) instead of templates.

Model: DistilGPT2 quantized to ONNX int8 format
Fallback: Template-based messages if model unavailable

Author: Claude
Date: 2026-02-21
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Model configuration
MODEL_NAME = "distilgpt2"
MODEL_DIR = Path(__file__).parent.parent / "models" / "distilgpt2-onnx-int8"
MAX_LENGTH = 80  # Max tokens for generated message
TEMPERATURE = 0.7

# Feature toggle
ENABLE_LLM_MESSAGES = os.environ.get("ENABLE_LLM_MESSAGES", "0").lower() in ("1", "true", "yes")


# ============================================================================
# MODEL LOADER
# ============================================================================

class MessageGenerator:
    """
    Generates smart messages using DistilGPT2 ONNX.

    Falls back to templates if model is unavailable or disabled.
    """

    _instance = None
    _model_loaded = False
    _tokenizer = None
    _session = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._model_loaded = False
            self._tokenizer = None
            self._session = None

    def load_model(self) -> bool:
        """
        Load the ONNX model if available.

        Returns True if model loaded successfully.
        """
        if self._model_loaded:
            return True

        if not ENABLE_LLM_MESSAGES:
            log.info("LLM message generation disabled by config")
            return False

        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            model_path = MODEL_DIR / "model_quantized.onnx"

            if not model_path.exists():
                log.warning(f"ONNX model not found at {model_path}")
                log.info("To enable LLM messages, run: python -m matching.download_model")
                return False

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                str(MODEL_DIR),
                local_files_only=True
            )

            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            # Load ONNX session
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 2

            self._session = ort.InferenceSession(
                str(model_path),
                sess_options,
                providers=['CPUExecutionProvider']
            )

            self._model_loaded = True
            log.info(f"Loaded DistilGPT2 ONNX model from {model_path}")
            return True

        except ImportError as e:
            log.warning(f"ONNX dependencies not installed: {e}")
            log.info("Install with: pip install onnxruntime transformers")
            return False
        except Exception as e:
            log.error(f"Failed to load ONNX model: {e}")
            return False

    def generate_message(
        self,
        unsatisfied_constraints: List[Dict],
        bonus_attributes: Dict[str, Any]
    ) -> str:
        """
        Generate a smart message describing the differences.

        Falls back to templates if model unavailable.
        """
        # Try LLM generation
        if self._model_loaded and self._session is not None:
            try:
                return self._generate_with_llm(unsatisfied_constraints, bonus_attributes)
            except Exception as e:
                log.warning(f"LLM generation failed, using template: {e}")

        # Fallback to template
        return self._generate_with_template(unsatisfied_constraints, bonus_attributes)

    def _generate_with_llm(
        self,
        unsatisfied: List[Dict],
        bonus: Dict[str, Any]
    ) -> str:
        """Generate message using the ONNX model."""
        import numpy as np

        # Build prompt
        prompt = self._build_prompt(unsatisfied, bonus)

        # Tokenize
        inputs = self._tokenizer(
            prompt,
            return_tensors="np",
            padding=True,
            truncation=True,
            max_length=256
        )

        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]

        # Generate tokens autoregressively
        generated = input_ids.copy()

        for _ in range(MAX_LENGTH):
            # Run inference
            outputs = self._session.run(
                None,
                {
                    "input_ids": generated,
                    "attention_mask": np.ones_like(generated)
                }
            )

            logits = outputs[0]
            next_token_logits = logits[:, -1, :]

            # Apply temperature
            next_token_logits = next_token_logits / TEMPERATURE

            # Sample or greedy
            next_token = np.argmax(next_token_logits, axis=-1, keepdims=True)

            # Append
            generated = np.concatenate([generated, next_token], axis=-1)

            # Stop at EOS
            if next_token[0, 0] == self._tokenizer.eos_token_id:
                break

        # Decode
        result = self._tokenizer.decode(
            generated[0, len(input_ids[0]):],
            skip_special_tokens=True
        ).strip()

        # Clean up
        result = result.split("\n")[0].strip()  # Take first line
        if len(result) < 10:
            return self._generate_with_template(unsatisfied, bonus)

        return result

    def _build_prompt(
        self,
        unsatisfied: List[Dict],
        bonus: Dict[str, Any]
    ) -> str:
        """Build prompt for the model."""
        parts = []

        # Describe mismatches
        for c in unsatisfied[:3]:
            field = c.get("field", "")
            required = c.get("required", "")
            actual = c.get("actual", "")
            deviation = c.get("deviation")
            direction = c.get("direction")

            if deviation:
                pct = int(deviation * 100)
                parts.append(f"{field}: seller has {actual}, {pct}% {direction} your {required}")
            elif actual is None:
                parts.append(f"{field}: not specified by seller (you wanted {required})")
            else:
                parts.append(f"{field}: seller has {actual}, you wanted {required}")

        # Add bonus info
        if bonus:
            bonus_items = list(bonus.items())[:2]
            for key, val in bonus_items:
                parts.append(f"bonus: seller also offers {key}={val}")

        context = "; ".join(parts)

        prompt = f"""Generate a friendly one-sentence message for a buyer about a listing that is a close match but has some differences.

Differences: {context}

Message:"""

        return prompt

    def _generate_with_template(
        self,
        unsatisfied: List[Dict],
        bonus: Dict[str, Any]
    ) -> str:
        """Generate natural, human-friendly messages."""
        if not unsatisfied:
            if bonus:
                bonus_parts = self._format_bonus_natural(bonus)
                return f"Perfect match! {bonus_parts}"
            return "This listing matches all your requirements perfectly!"

        # Generate natural language for differences
        diff_parts = []
        for c in unsatisfied[:3]:
            msg = self._format_constraint_natural(c)
            if msg:
                diff_parts.append(msg)

        # Generate bonus message
        bonus_msg = ""
        if bonus:
            bonus_msg = " " + self._format_bonus_natural(bonus)

        # Combine into natural sentence
        if len(diff_parts) == 1:
            return f"Close match: {diff_parts[0]}.{bonus_msg}"
        elif len(diff_parts) == 2:
            return f"Close match: {diff_parts[0]}, and {diff_parts[1]}.{bonus_msg}"
        else:
            main = ", ".join(diff_parts[:-1])
            return f"Close match: {main}, and {diff_parts[-1]}.{bonus_msg}"

    def _format_constraint_natural(self, c: Dict) -> str:
        """Format constraint as natural, human-friendly text."""
        field = c.get("field", "unknown")
        required = c.get("required")
        actual = c.get("actual")
        deviation = c.get("deviation")
        direction = c.get("direction")
        ctype = c.get("type", "")

        # Format values
        req_str = self._format_value(required)
        actual_str = self._format_value(actual)

        # Calculate absolute difference for more natural phrasing
        abs_diff = None
        if isinstance(required, (int, float)) and isinstance(actual, (int, float)):
            abs_diff = abs(actual - required)
        elif isinstance(required, (list, tuple)) and isinstance(actual, (list, tuple)):
            if len(required) >= 1 and len(actual) >= 1:
                req_val = required[0] if required[0] == required[-1] else (required[0] + required[-1]) / 2
                act_val = actual[0] if actual[0] == actual[-1] else (actual[0] + actual[-1]) / 2
                abs_diff = abs(act_val - req_val)

        if ctype == "range":
            if abs_diff is not None and abs_diff <= 5:
                # Small difference - use absolute terms
                diff_word = "more" if direction == "above" else "less"
                unit_diff = self._infer_unit(field, abs_diff)
                # Format actual value as integer if it's a whole number
                actual_display = int(float(actual_str)) if actual_str.replace('.', '').replace('-', '').isdigit() else actual_str
                unit_actual = self._infer_unit(field, float(actual_str) if str(actual_str).replace('.', '').replace('-', '').isdigit() else 1)
                return f"the {field} is {actual_display}{unit_actual} — just {int(abs_diff)}{unit_diff} {diff_word} than you specified ({req_str})"
            elif deviation is not None:
                pct = int(deviation * 100)
                diff_word = "higher" if direction == "above" else "lower"
                return f"the {field} is {actual_str} — {pct}% {diff_word} than your {req_str}"
            return f"the {field} is {actual_str} instead of {req_str}"

        elif ctype == "min":
            if abs_diff is not None and abs_diff <= 5:
                unit = self._infer_unit(field, abs_diff)
                return f"the {field} is {actual_str}{unit} — {int(abs_diff)}{unit} below your minimum of {req_str}"
            elif deviation is not None:
                pct = int(deviation * 100)
                return f"the {field} is {actual_str} — {pct}% below your minimum of {req_str}"
            return f"the {field} ({actual_str}) is below your minimum of {req_str}"

        elif ctype == "max":
            if abs_diff is not None and abs_diff <= 5:
                unit = self._infer_unit(field, abs_diff)
                return f"the {field} is {actual_str}{unit} — {int(abs_diff)}{unit} above your maximum of {req_str}"
            elif deviation is not None:
                pct = int(deviation * 100)
                return f"the {field} is {actual_str} — {pct}% above your maximum of {req_str}"
            return f"the {field} ({actual_str}) exceeds your maximum of {req_str}"

        elif ctype == "location":
            if actual and required:
                return f"located in {actual_str} instead of {req_str}"
            return f"location is {actual_str} (you wanted {req_str})"

        elif ctype == "categorical":
            if actual is None:
                return f"{field} is not specified (you wanted {req_str})"
            return f"the {field} is {actual_str} instead of {req_str}"

        elif ctype == "exclusion":
            return f"contains {actual_str} which you wanted to exclude"

        return f"the {field} differs from your requirement"

    def _format_bonus_natural(self, bonus: Dict[str, Any]) -> str:
        """Format bonus attributes as natural text."""
        if not bonus:
            return ""

        parts = []
        for key, val in list(bonus.items())[:2]:
            # Clean up the key for display
            clean_key = key.split(".")[-1] if "." in key else key
            parts.append(f"{clean_key}: {val}")

        if len(parts) == 1:
            return f"Bonus: this listing also offers {parts[0]}!"
        else:
            return f"Bonus: this listing also offers {parts[0]} and {parts[1]}!"

    def _infer_unit(self, field: str, value: float) -> str:
        """Infer unit suffix based on field name."""
        field_lower = field.lower()
        if "age" in field_lower or "year" in field_lower:
            return " years" if value != 1 else " year"
        if "month" in field_lower:
            return " months" if value != 1 else " month"
        if "experience" in field_lower:
            return " months" if value != 1 else " month"
        if "price" in field_lower or "salary" in field_lower or "cost" in field_lower:
            return ""
        if "distance" in field_lower or "km" in field_lower:
            return " km"
        return ""

    def _format_constraint(self, c: Dict) -> str:
        """Legacy format - redirects to natural format."""
        return self._format_constraint_natural(c)

    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if value is None:
            return "not specified"
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and isinstance(value[0], (int, float)):
                v0 = int(value[0]) if isinstance(value[0], float) and value[0] == int(value[0]) else value[0]
                v1 = int(value[1]) if isinstance(value[1], float) and value[1] == int(value[1]) else value[1]
                if v0 == v1:
                    return str(v0)
                return f"{v0}-{v1}"
            return ", ".join(str(v) for v in value)
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            return f"{value:.2f}"
        if isinstance(value, dict):
            return str(value.get("name", value.get("concept_id", value)))
        return str(value)


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_generator: Optional[MessageGenerator] = None


def get_message_generator() -> MessageGenerator:
    """Get the singleton message generator instance."""
    global _generator
    if _generator is None:
        _generator = MessageGenerator()
    return _generator


def generate_smart_message(
    unsatisfied_constraints: List[Dict],
    bonus_attributes: Dict[str, Any] = None
) -> str:
    """
    Generate a smart message for similar match differences.

    Uses LLM if available, falls back to templates.
    """
    generator = get_message_generator()
    return generator.generate_message(
        unsatisfied_constraints,
        bonus_attributes or {}
    )


def init_message_generator() -> bool:
    """
    Initialize the message generator and load model if enabled.

    Call this at startup to preload the model.
    """
    generator = get_message_generator()
    return generator.load_model()
