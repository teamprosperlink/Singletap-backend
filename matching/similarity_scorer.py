"""
VRIDDHI MATCHING SYSTEM - SIMILARITY SCORER
Phase 2.8: Similar Matching Extension

Purpose: Compute similarity scores for near-match detection when strict
boolean matching fails. Identifies listings that are "close but not exact".

Key Concepts:
- Tier 1 fields (MUST match): intent, subintent, domain, item.type
- Tier 2 fields (CAN differ): numeric constraints, categorical, location
- Bonus attributes: Extra features listing has that query didn't ask for

Integrates with:
- listing_matcher_v2.py for boolean matching
- numeric_constraints.py for constraint evaluation

Author: Claude
Date: 2026-02-21
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from .numeric_constraints import (
    Range,
    satisfies_min_constraint,
    satisfies_max_constraint,
    ranges_overlap
)


# ============================================================================
# ENUMS AND DATACLASSES
# ============================================================================

class ConstraintType(Enum):
    """Types of constraints that can be evaluated."""
    MIN = "min"
    MAX = "max"
    RANGE = "range"
    CATEGORICAL = "categorical"
    LOCATION = "location"
    EXCLUSION = "exclusion"
    TYPE = "type"


@dataclass
class ConstraintResult:
    """Result of evaluating a single constraint."""
    passed: bool
    field_name: str
    field_path: str  # e.g., "items[0].range.age" or "location"
    constraint_type: ConstraintType
    required_value: Any
    candidate_value: Any
    deviation: Optional[float] = None  # For numeric: percentage deviation (0.0-1.0+)
    deviation_direction: Optional[str] = None  # "above" or "below"

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "field": self.field_name,
            "path": self.field_path,
            "type": self.constraint_type.value,
            "required": self._serialize_value(self.required_value),
            "actual": self._serialize_value(self.candidate_value),
            "passed": self.passed,
            "deviation": round(self.deviation, 3) if self.deviation is not None else None,
            "direction": self.deviation_direction
        }

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize value for JSON."""
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, dict):
            return value
        return value


@dataclass
class SimilarityResult:
    """Complete similarity analysis result."""
    similarity_score: float  # 0.0 to 1.0
    is_exact_match: bool
    is_similar_match: bool  # True if score >= threshold
    tier1_passed: bool
    satisfied_constraints: List[Dict] = field(default_factory=list)
    unsatisfied_constraints: List[Dict] = field(default_factory=list)
    bonus_attributes: Dict[str, Any] = field(default_factory=dict)
    smart_message: str = ""
    recommendation: str = ""


# ============================================================================
# CONFIGURATION
# ============================================================================

# Weight configuration for different constraint types
CONSTRAINT_WEIGHTS = {
    ConstraintType.CATEGORICAL: 1.0,
    ConstraintType.MIN: 1.0,
    ConstraintType.MAX: 1.0,
    ConstraintType.RANGE: 1.0,
    ConstraintType.LOCATION: 1.5,  # Location slightly more important
    ConstraintType.EXCLUSION: 0.8,  # Exclusions less critical for similarity
    ConstraintType.TYPE: 2.0,  # Type very important
}

# Deviation brackets for partial credit
DEVIATION_BRACKETS = [
    (0.10, 0.90),   # ≤10% deviation → 90% credit
    (0.25, 0.75),   # 10-25% deviation → 75% credit
    (0.50, 0.50),   # 25-50% deviation → 50% credit
    (1.00, 0.20),   # >50% deviation → 20% credit
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_numeric_range(item: Dict, key: str) -> Optional[Tuple[float, float]]:
    """
    Extract numeric range for a key from item's range/min/max fields.

    Priority: range[key] > min/max combination
    """
    # Check range first
    if "range" in item and key in item["range"]:
        r = item["range"][key]
        if isinstance(r, (list, tuple)) and len(r) == 2:
            return (float(r[0]), float(r[1]))

    # Construct from min/max
    min_val = item.get("min", {}).get(key)
    max_val = item.get("max", {}).get(key)

    if min_val is not None and max_val is not None:
        return (float(min_val), float(max_val))
    elif min_val is not None:
        return (float(min_val), float(min_val))
    elif max_val is not None:
        return (float(max_val), float(max_val))

    return None


def _categorical_to_dict(cat: Union[Dict, List, None]) -> Dict:
    """Convert categorical to dict format."""
    if not cat:
        return {}
    if isinstance(cat, dict):
        return cat
    if isinstance(cat, list):
        result = {}
        for item in cat:
            if isinstance(item, dict):
                k = item.get("attribute", "")
                v = item.get("value", "")
                if k:
                    result[k] = v
        return result
    return {}


def _get_type_value(type_val: Any) -> str:
    """Extract string type value from various formats."""
    if isinstance(type_val, str):
        return type_val.lower().strip()
    if isinstance(type_val, dict):
        return str(type_val.get("concept_id", type_val.get("type", ""))).lower().strip()
    return str(type_val).lower().strip()


def _deviation_to_partial_score(deviation: float) -> float:
    """Convert deviation percentage to partial score (0-1)."""
    for threshold, credit in DEVIATION_BRACKETS:
        if deviation <= threshold:
            return credit
    return 0.1  # Extreme deviation gets minimal credit


def _compute_numeric_deviation(required: float, actual: Tuple[float, float]) -> Tuple[float, str]:
    """
    Compute deviation and direction for numeric mismatch.

    Returns (deviation_fraction, direction)
    """
    actual_val = actual[0] if actual[0] == actual[1] else (actual[0] + actual[1]) / 2

    if required == 0:
        return (1.0, "above" if actual_val > 0 else "below")

    deviation = abs(actual_val - required) / abs(required)
    direction = "above" if actual_val > required else "below"

    return (deviation, direction)


# ============================================================================
# TIER 1 EVALUATION (Must match - no similarity allowed)
# ============================================================================

def _evaluate_tier1(A: Dict, B: Dict) -> Tuple[bool, List[ConstraintResult]]:
    """
    Evaluate Tier 1 constraints (must match).

    Returns (passed, results)
    """
    results = []

    # M-01: Intent equality
    a_intent = A.get("intent", "")
    b_intent = B.get("intent", "")
    intent_match = a_intent == b_intent
    results.append(ConstraintResult(
        passed=intent_match,
        field_name="intent",
        field_path="intent",
        constraint_type=ConstraintType.TYPE,
        required_value=a_intent,
        candidate_value=b_intent
    ))
    if not intent_match:
        return (False, results)

    # M-02/M-03: SubIntent rules
    a_subintent = A.get("subintent", "")
    b_subintent = B.get("subintent", "")
    intent = a_intent

    if intent in ("product", "service"):
        # Subintent must be INVERSE (buyer↔seller, seeker↔provider)
        subintent_match = a_subintent != b_subintent
    elif intent == "mutual":
        # Subintent must be SAME (both "connect")
        subintent_match = a_subintent == b_subintent
    else:
        subintent_match = True

    results.append(ConstraintResult(
        passed=subintent_match,
        field_name="subintent",
        field_path="subintent",
        constraint_type=ConstraintType.TYPE,
        required_value=a_subintent,
        candidate_value=b_subintent
    ))
    if not subintent_match:
        return (False, results)

    # M-05/M-06: Domain/Category intersection
    if intent in ("product", "service"):
        a_domain = set(A.get("domain", []))
        b_domain = set(B.get("domain", []))
        domain_match = bool(a_domain & b_domain) if a_domain else True
        results.append(ConstraintResult(
            passed=domain_match,
            field_name="domain",
            field_path="domain",
            constraint_type=ConstraintType.CATEGORICAL,
            required_value=list(a_domain),
            candidate_value=list(b_domain)
        ))
        if not domain_match:
            return (False, results)
    elif intent == "mutual":
        a_category = set(A.get("category", []))
        b_category = set(B.get("category", []))
        category_match = bool(a_category & b_category) if a_category else True
        results.append(ConstraintResult(
            passed=category_match,
            field_name="category",
            field_path="category",
            constraint_type=ConstraintType.CATEGORICAL,
            required_value=list(a_category),
            candidate_value=list(b_category)
        ))
        if not category_match:
            return (False, results)

    return (True, results)


# ============================================================================
# TIER 2 EVALUATION (Can differ - creates similar match)
# ============================================================================

def _find_matching_item_by_type(
    req_item: Dict,
    candidate_items: List[Dict],
    implies_fn: Optional[Callable] = None
) -> Optional[Dict]:
    """Find candidate item matching required item's type."""
    req_type = _get_type_value(req_item.get("type", ""))
    if not req_type:
        return None

    for cand_item in candidate_items:
        cand_type = _get_type_value(cand_item.get("type", ""))

        # Check exact match or implication
        if cand_type == req_type:
            return cand_item
        if implies_fn and implies_fn(cand_type, req_type):
            return cand_item

    return None


def _evaluate_items_detailed(
    required_items: List[Dict],
    candidate_items: List[Dict],
    implies_fn: Optional[Callable] = None
) -> List[ConstraintResult]:
    """Evaluate all item constraints with detailed results."""
    results = []

    for i, req_item in enumerate(required_items):
        req_type = _get_type_value(req_item.get("type", ""))

        # Find matching candidate by type
        cand_item = _find_matching_item_by_type(req_item, candidate_items, implies_fn)

        if cand_item is None:
            # Type mismatch - this is Tier 1 failure in full matching
            # but we still record it for similarity
            results.append(ConstraintResult(
                passed=False,
                field_name="type",
                field_path=f"items[{i}].type",
                constraint_type=ConstraintType.TYPE,
                required_value=req_type,
                candidate_value=None
            ))
            continue

        cand_type = _get_type_value(cand_item.get("type", ""))
        results.append(ConstraintResult(
            passed=True,
            field_name="type",
            field_path=f"items[{i}].type",
            constraint_type=ConstraintType.TYPE,
            required_value=req_type,
            candidate_value=cand_type
        ))

        # Categorical constraints (M-08)
        req_cat = _categorical_to_dict(req_item.get("categorical", {}))
        cand_cat = _categorical_to_dict(cand_item.get("categorical", {}))

        for key, req_val in req_cat.items():
            cand_val = cand_cat.get(key)

            # Check match
            if cand_val is None:
                passed = False
            elif implies_fn:
                passed = implies_fn(str(cand_val), str(req_val))
            else:
                passed = str(cand_val).lower().strip() == str(req_val).lower().strip()

            results.append(ConstraintResult(
                passed=passed,
                field_name=key,
                field_path=f"items[{i}].categorical.{key}",
                constraint_type=ConstraintType.CATEGORICAL,
                required_value=req_val,
                candidate_value=cand_val
            ))

        # MIN constraints (M-09) - using overlap semantics
        req_min = req_item.get("min", {})
        for key, min_val in req_min.items():
            cand_range = _extract_numeric_range(cand_item, key)

            if cand_range is None:
                passed = False
                deviation = None
                direction = None
            else:
                # Overlap-based: candidate can provide at least min_val
                passed = satisfies_min_constraint(float(min_val), cand_range)
                if not passed:
                    deviation, direction = _compute_numeric_deviation(float(min_val), cand_range)
                else:
                    deviation = None
                    direction = None

            results.append(ConstraintResult(
                passed=passed,
                field_name=key,
                field_path=f"items[{i}].min.{key}",
                constraint_type=ConstraintType.MIN,
                required_value=min_val,
                candidate_value=cand_range,
                deviation=deviation,
                deviation_direction=direction
            ))

        # MAX constraints (M-10) - using overlap semantics
        req_max = req_item.get("max", {})
        for key, max_val in req_max.items():
            cand_range = _extract_numeric_range(cand_item, key)

            if cand_range is None:
                passed = False
                deviation = None
                direction = None
            else:
                passed = satisfies_max_constraint(float(max_val), cand_range)
                if not passed:
                    deviation, direction = _compute_numeric_deviation(float(max_val), cand_range)
                else:
                    deviation = None
                    direction = None

            results.append(ConstraintResult(
                passed=passed,
                field_name=key,
                field_path=f"items[{i}].max.{key}",
                constraint_type=ConstraintType.MAX,
                required_value=max_val,
                candidate_value=cand_range,
                deviation=deviation,
                deviation_direction=direction
            ))

        # RANGE constraints (M-11) - using overlap semantics
        req_ranges = req_item.get("range", {})
        for key, req_range in req_ranges.items():
            if not isinstance(req_range, (list, tuple)) or len(req_range) != 2:
                continue

            cand_range = _extract_numeric_range(cand_item, key)

            if cand_range is None:
                passed = False
                deviation = None
                direction = None
            else:
                passed = ranges_overlap(tuple(req_range), cand_range)
                if not passed:
                    # Calculate deviation from range
                    req_mid = (req_range[0] + req_range[1]) / 2
                    deviation, direction = _compute_numeric_deviation(req_mid, cand_range)
                else:
                    deviation = None
                    direction = None

            results.append(ConstraintResult(
                passed=passed,
                field_name=key,
                field_path=f"items[{i}].range.{key}",
                constraint_type=ConstraintType.RANGE,
                required_value=list(req_range),
                candidate_value=list(cand_range) if cand_range else None,
                deviation=deviation,
                deviation_direction=direction
            ))

        # Exclusion constraints (M-12)
        exclusions = req_item.get("itemexclusions", [])
        if exclusions:
            cand_values = set()
            cand_values.add(_get_type_value(cand_item.get("type", "")))
            for k, v in _categorical_to_dict(cand_item.get("categorical", {})).items():
                cand_values.add(str(v).lower().strip())

            violations = set(str(e).lower().strip() for e in exclusions) & cand_values

            results.append(ConstraintResult(
                passed=len(violations) == 0,
                field_name="itemexclusions",
                field_path=f"items[{i}].itemexclusions",
                constraint_type=ConstraintType.EXCLUSION,
                required_value=exclusions,
                candidate_value=list(violations) if violations else None
            ))

    return results


def _evaluate_other_self_detailed(
    other: Dict,
    self_attrs: Dict,
    implies_fn: Optional[Callable] = None
) -> List[ConstraintResult]:
    """Evaluate other→self constraints with detailed results."""
    results = []

    # Categorical constraints (M-13)
    req_cat = _categorical_to_dict(other.get("categorical", {}))
    cand_cat = _categorical_to_dict(self_attrs.get("categorical", {}))

    for key, req_val in req_cat.items():
        cand_val = cand_cat.get(key)

        if cand_val is None:
            passed = False
        elif implies_fn:
            passed = implies_fn(str(cand_val), str(req_val))
        else:
            passed = str(cand_val).lower().strip() == str(req_val).lower().strip()

        results.append(ConstraintResult(
            passed=passed,
            field_name=key,
            field_path=f"other.categorical.{key}",
            constraint_type=ConstraintType.CATEGORICAL,
            required_value=req_val,
            candidate_value=cand_val
        ))

    # MIN constraints (M-14)
    req_min = other.get("min", {})
    for key, min_val in req_min.items():
        cand_range = _extract_numeric_range(self_attrs, key)

        if cand_range is None:
            passed = False
            deviation = None
            direction = None
        else:
            passed = satisfies_min_constraint(float(min_val), cand_range)
            if not passed:
                deviation, direction = _compute_numeric_deviation(float(min_val), cand_range)
            else:
                deviation = None
                direction = None

        results.append(ConstraintResult(
            passed=passed,
            field_name=key,
            field_path=f"other.min.{key}",
            constraint_type=ConstraintType.MIN,
            required_value=min_val,
            candidate_value=cand_range,
            deviation=deviation,
            deviation_direction=direction
        ))

    # MAX constraints (M-15)
    req_max = other.get("max", {})
    for key, max_val in req_max.items():
        cand_range = _extract_numeric_range(self_attrs, key)

        if cand_range is None:
            passed = False
            deviation = None
            direction = None
        else:
            passed = satisfies_max_constraint(float(max_val), cand_range)
            if not passed:
                deviation, direction = _compute_numeric_deviation(float(max_val), cand_range)
            else:
                deviation = None
                direction = None

        results.append(ConstraintResult(
            passed=passed,
            field_name=key,
            field_path=f"other.max.{key}",
            constraint_type=ConstraintType.MAX,
            required_value=max_val,
            candidate_value=cand_range,
            deviation=deviation,
            deviation_direction=direction
        ))

    # RANGE constraints (M-16)
    req_ranges = other.get("range", {})
    for key, req_range in req_ranges.items():
        if not isinstance(req_range, (list, tuple)) or len(req_range) != 2:
            continue

        cand_range = _extract_numeric_range(self_attrs, key)

        if cand_range is None:
            passed = False
            deviation = None
            direction = None
        else:
            passed = ranges_overlap(tuple(req_range), cand_range)
            if not passed:
                req_mid = (req_range[0] + req_range[1]) / 2
                deviation, direction = _compute_numeric_deviation(req_mid, cand_range)
            else:
                deviation = None
                direction = None

        results.append(ConstraintResult(
            passed=passed,
            field_name=key,
            field_path=f"other.range.{key}",
            constraint_type=ConstraintType.RANGE,
            required_value=list(req_range),
            candidate_value=list(cand_range) if cand_range else None,
            deviation=deviation,
            deviation_direction=direction
        ))

    # Exclusion constraints (M-17)
    exclusions = other.get("otherexclusions", [])
    if exclusions:
        cand_values = set()
        for k, v in _categorical_to_dict(self_attrs.get("categorical", {})).items():
            cand_values.add(str(v).lower().strip())

        violations = set(str(e).lower().strip() for e in exclusions) & cand_values

        results.append(ConstraintResult(
            passed=len(violations) == 0,
            field_name="otherexclusions",
            field_path="other.otherexclusions",
            constraint_type=ConstraintType.EXCLUSION,
            required_value=exclusions,
            candidate_value=list(violations) if violations else None
        ))

    return results


def _evaluate_location_detailed(A: Dict, B: Dict) -> List[ConstraintResult]:
    """Evaluate location constraints with detailed results."""
    results = []

    a_location = A.get("location", "")
    b_location = B.get("location", "")
    a_mode = A.get("locationmode", "near_me")

    # Global mode always matches
    if a_mode == "global":
        results.append(ConstraintResult(
            passed=True,
            field_name="location",
            field_path="location",
            constraint_type=ConstraintType.LOCATION,
            required_value=a_location,
            candidate_value=b_location
        ))
        return results

    # Simple location comparison
    a_loc_str = str(a_location).lower().strip() if a_location else ""
    b_loc_str = str(b_location).lower().strip() if b_location else ""

    # Handle dict locations
    if isinstance(a_location, dict):
        a_loc_str = str(a_location.get("name", a_location.get("canonical_name", ""))).lower().strip()
    if isinstance(b_location, dict):
        b_loc_str = str(b_location.get("name", b_location.get("canonical_name", ""))).lower().strip()

    # Empty locations
    if not a_loc_str:
        passed = True
    elif not b_loc_str:
        passed = False
    else:
        passed = a_loc_str == b_loc_str

    results.append(ConstraintResult(
        passed=passed,
        field_name="location",
        field_path="location",
        constraint_type=ConstraintType.LOCATION,
        required_value=a_location,
        candidate_value=b_location
    ))

    # Location exclusions
    exclusions = A.get("locationexclusions", [])
    if exclusions and b_loc_str:
        violations = [e for e in exclusions if str(e).lower().strip() == b_loc_str]
        results.append(ConstraintResult(
            passed=len(violations) == 0,
            field_name="locationexclusions",
            field_path="locationexclusions",
            constraint_type=ConstraintType.EXCLUSION,
            required_value=exclusions,
            candidate_value=violations if violations else None
        ))

    return results


# ============================================================================
# BONUS ATTRIBUTES
# ============================================================================

def _compute_bonus_attributes(A: Dict, B: Dict) -> Dict[str, Any]:
    """
    Identify bonus attributes: things B has that A didn't ask for.
    """
    bonus = {}

    # Compare items
    a_items = A.get("items", [])
    b_items = B.get("items", [])

    for i, b_item in enumerate(b_items):
        # Find matching A item by type
        b_type = _get_type_value(b_item.get("type", ""))
        a_item = None
        for ai in a_items:
            if _get_type_value(ai.get("type", "")) == b_type:
                a_item = ai
                break

        if a_item is None:
            continue

        # Extra categorical attributes
        a_cat = set(_categorical_to_dict(a_item.get("categorical", {})).keys())
        b_cat = _categorical_to_dict(b_item.get("categorical", {}))

        for key, val in b_cat.items():
            if key not in a_cat:
                bonus[f"items[{i}].{key}"] = val

        # Extra numeric attributes (listing has specific values query didn't ask for)
        a_asked = set(a_item.get("min", {}).keys()) | set(a_item.get("max", {}).keys()) | set(a_item.get("range", {}).keys())

        for key in b_item.get("range", {}).keys():
            if key not in a_asked:
                val = b_item["range"][key]
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    if val[0] == val[1]:
                        bonus[f"items[{i}].{key}"] = val[0]
                    else:
                        bonus[f"items[{i}].{key}"] = f"{val[0]}-{val[1]}"

    return bonus


# ============================================================================
# SMART MESSAGE GENERATION (uses message_generator module)
# ============================================================================

def _generate_smart_message(unsatisfied: List[ConstraintResult], bonus: Dict = None) -> str:
    """Generate human-readable explanation using message_generator."""
    try:
        from .message_generator import generate_smart_message
        # Convert ConstraintResult objects to dicts
        unsatisfied_dicts = [c.to_dict() for c in unsatisfied]
        return generate_smart_message(unsatisfied_dicts, bonus or {})
    except ImportError:
        # Fallback to simple message if message_generator not available
        if not unsatisfied:
            return "This listing matches all your requirements."
        messages = [_format_single_difference(c) for c in unsatisfied[:3]]
        if len(unsatisfied) > 3:
            messages.append(f"and {len(unsatisfied) - 3} other difference(s)")
        return "Close match with differences: " + "; ".join(filter(None, messages))


def _format_single_difference(c: ConstraintResult) -> str:
    """Format a single constraint difference as a message."""
    field = c.field_name
    req = c.required_value
    actual = c.candidate_value

    # Format values
    req_str = _format_display_value(req)
    actual_str = _format_display_value(actual)

    if c.constraint_type == ConstraintType.RANGE:
        if c.deviation is not None:
            pct = int(c.deviation * 100)
            return f"{field} is {actual_str} ({pct}% {c.deviation_direction} your {req_str})"
        return f"{field} is {actual_str} (you wanted {req_str})"

    elif c.constraint_type == ConstraintType.MIN:
        if c.deviation is not None:
            pct = int(c.deviation * 100)
            return f"{field} is {actual_str} ({pct}% below your minimum of {req_str})"
        return f"{field} is below your minimum of {req_str}"

    elif c.constraint_type == ConstraintType.MAX:
        if c.deviation is not None:
            pct = int(c.deviation * 100)
            return f"{field} is {actual_str} ({pct}% above your maximum of {req_str})"
        return f"{field} exceeds your maximum of {req_str}"

    elif c.constraint_type == ConstraintType.LOCATION:
        return f"Location is {actual_str} (you wanted {req_str})"

    elif c.constraint_type == ConstraintType.CATEGORICAL:
        if actual is None:
            return f"{field} not specified (you wanted {req_str})"
        return f"{field} is {actual_str} (you wanted {req_str})"

    elif c.constraint_type == ConstraintType.EXCLUSION:
        return f"Contains excluded: {actual_str}"

    return f"{field} differs from requirement"


def _format_display_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return "not specified"
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], (int, float)):
            if value[0] == value[1]:
                return str(value[0])
            return f"{value[0]}-{value[1]}"
        return ", ".join(str(v) for v in value)
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    if isinstance(value, dict):
        return str(value.get("name", value.get("concept_id", value)))
    return str(value)


def _generate_recommendation(score: float, unsatisfied: List[ConstraintResult]) -> str:
    """Generate recommendation based on similarity score."""
    if score >= 0.95:
        return "Highly recommended — very close to your requirements"
    elif score >= 0.85:
        return "Good match — consider if the differences are acceptable"
    elif score >= 0.75:
        return "Moderate match — review the differences carefully"
    elif score >= 0.70:
        return "Partial match — has significant differences from requirements"
    else:
        return "Weak match — many differences from your requirements"


# ============================================================================
# MAIN SIMILARITY EVALUATION
# ============================================================================

def evaluate_similarity(
    A: Dict[str, Any],
    B: Dict[str, Any],
    implies_fn: Optional[Callable] = None,
    min_score: float = 0.70
) -> SimilarityResult:
    """
    Evaluate similarity between two listings.

    This is the main entry point for similarity scoring.

    Args:
        A: Required listing (query) - normalized to OLD format
        B: Candidate listing - normalized to OLD format
        implies_fn: Optional term implication function
        min_score: Minimum score for similar match (default 0.70)

    Returns:
        SimilarityResult with score, constraints, and messages
    """
    # Evaluate Tier 1 (must match)
    tier1_passed, tier1_results = _evaluate_tier1(A, B)

    if not tier1_passed:
        # Tier 1 failed - not even similar
        return SimilarityResult(
            similarity_score=0.0,
            is_exact_match=False,
            is_similar_match=False,
            tier1_passed=False,
            satisfied_constraints=[r.to_dict() for r in tier1_results if r.passed],
            unsatisfied_constraints=[r.to_dict() for r in tier1_results if not r.passed],
            bonus_attributes={},
            smart_message="Not a match: fundamental criteria differ (intent, domain, or type).",
            recommendation="Consider different listings."
        )

    # Evaluate Tier 2 constraints
    tier2_results = []

    # Items matching
    intent = A.get("intent", "")
    if intent in ("product", "service"):
        tier2_results.extend(_evaluate_items_detailed(
            A.get("items", []),
            B.get("items", []),
            implies_fn
        ))

    # Other→Self matching
    tier2_results.extend(_evaluate_other_self_detailed(
        A.get("other", {}),
        B.get("self", {}),
        implies_fn
    ))

    # Location matching
    tier2_results.extend(_evaluate_location_detailed(A, B))

    # Partition results
    satisfied = [r for r in tier2_results if r.passed]
    unsatisfied = [r for r in tier2_results if not r.passed]

    # Compute bonus attributes
    bonus = _compute_bonus_attributes(A, B)

    # Check if exact match (all Tier 2 passed)
    if len(unsatisfied) == 0:
        return SimilarityResult(
            similarity_score=1.0,
            is_exact_match=True,
            is_similar_match=True,
            tier1_passed=True,
            satisfied_constraints=[r.to_dict() for r in satisfied],
            unsatisfied_constraints=[],
            bonus_attributes=bonus,
            smart_message="Perfect match! All your requirements are satisfied.",
            recommendation="This listing meets all your criteria."
        )

    # Calculate similarity score
    score = _compute_similarity_score(tier2_results)

    is_similar = score >= min_score

    return SimilarityResult(
        similarity_score=round(score, 3),
        is_exact_match=False,
        is_similar_match=is_similar,
        tier1_passed=True,
        satisfied_constraints=[r.to_dict() for r in satisfied],
        unsatisfied_constraints=[r.to_dict() for r in unsatisfied],
        bonus_attributes=bonus,
        smart_message=_generate_smart_message(unsatisfied, bonus),
        recommendation=_generate_recommendation(score, unsatisfied)
    )


def _compute_similarity_score(results: List[ConstraintResult]) -> float:
    """
    Compute weighted similarity score from constraint results.

    Algorithm:
    1. Weight each constraint by type
    2. Passed constraints get full weight
    3. Failed constraints with deviation get partial credit
    4. Score = weighted_sum / total_weight
    """
    if not results:
        return 1.0  # No constraints = perfect match

    total_weight = 0.0
    achieved_weight = 0.0

    for r in results:
        weight = CONSTRAINT_WEIGHTS.get(r.constraint_type, 1.0)
        total_weight += weight

        if r.passed:
            achieved_weight += weight
        elif r.deviation is not None:
            # Partial credit for close misses
            partial = _deviation_to_partial_score(r.deviation)
            achieved_weight += weight * partial
        # else: no credit for complete miss

    if total_weight == 0:
        return 1.0

    return achieved_weight / total_weight
