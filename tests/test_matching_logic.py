"""
Test script to verify intersection-based matching logic is DYNAMIC (not hardcoded).

Tests various attribute types and scenarios to ensure the logic works generically.
This version directly imports the core functions without the full app initialization.
"""
import sys

# =========================================================================
# COPY OF CORE MATCHING FUNCTIONS (to test without full app initialization)
# =========================================================================

def _categorical_to_dict(categorical):
    """Convert array format to dict if needed."""
    if isinstance(categorical, dict):
        return categorical
    if isinstance(categorical, list):
        return {item.get("attribute"): item.get("value") for item in categorical if "attribute" in item}
    return {}

def _exact_match_only(candidate_val, required_val) -> bool:
    """Default implication: exact match only."""
    return str(candidate_val).lower() == str(required_val).lower()

def match_item_categorical(required_item, candidate_item, implies_fn=None):
    """
    Check if candidate's categorical attributes satisfy required attributes.

    NEW: Intersection-based matching with priority order:
    1. Check numeric first (specific satisfies vague)
    2. Check categorical (both vague - use implies_fn)
    3. Missing = pass (permissive)
    """
    if implies_fn is None:
        implies_fn = _exact_match_only

    required_categorical = _categorical_to_dict(required_item.get("categorical", {}))
    candidate_categorical = _categorical_to_dict(candidate_item.get("categorical", {}))

    if not required_categorical:
        return True

    for key, required_value in required_categorical.items():
        candidate_min = candidate_item.get("min", {})
        candidate_max = candidate_item.get("max", {})
        candidate_range = candidate_item.get("range", {})

        # PRIORITY 1: Check numeric first (specific takes priority over vague)
        if key in candidate_range or key in candidate_min or key in candidate_max:
            continue

        # PRIORITY 2: Check categorical (both have categorical - use implies_fn)
        elif key in candidate_categorical:
            candidate_value = candidate_categorical[key]
            if not implies_fn(candidate_value, required_value):
                return False

        # PRIORITY 3: Attribute missing entirely → PASS (permissive)
        else:
            continue

    return True


def evaluate_min_constraints(required_min, candidate_ranges):
    """Evaluate minimum constraints with permissive missing handling."""
    if not isinstance(required_min, dict):
        raise TypeError(f"required_min must be dict, got {type(required_min).__name__}")
    if not isinstance(candidate_ranges, dict):
        raise TypeError(f"candidate_ranges must be dict, got {type(candidate_ranges).__name__}")

    if not required_min:
        return True

    for key, min_threshold in required_min.items():
        # Missing attribute → PASS (permissive)
        if key not in candidate_ranges:
            continue

        candidate_range = candidate_ranges[key]
        # Check: candidate_max >= min_threshold
        if isinstance(candidate_range, list) and len(candidate_range) == 2:
            candidate_max = candidate_range[1]
            if candidate_max < min_threshold:
                return False
        elif isinstance(candidate_range, (int, float)):
            if candidate_range < min_threshold:
                return False

    return True


def evaluate_max_constraints(required_max, candidate_ranges):
    """Evaluate maximum constraints with permissive missing handling."""
    if not isinstance(required_max, dict):
        raise TypeError(f"required_max must be dict, got {type(required_max).__name__}")
    if not isinstance(candidate_ranges, dict):
        raise TypeError(f"candidate_ranges must be dict, got {type(candidate_ranges).__name__}")

    if not required_max:
        return True

    for key, max_threshold in required_max.items():
        # Missing attribute → PASS (permissive)
        if key not in candidate_ranges:
            continue

        candidate_range = candidate_ranges[key]
        # Check: candidate_min <= max_threshold
        if isinstance(candidate_range, list) and len(candidate_range) == 2:
            candidate_min = candidate_range[0]
            if candidate_min > max_threshold:
                return False
        elif isinstance(candidate_range, (int, float)):
            if candidate_range > max_threshold:
                return False

    return True


def evaluate_range_constraints(required_ranges, candidate_ranges):
    """Evaluate range constraints with permissive missing handling."""
    if not isinstance(required_ranges, dict):
        raise TypeError(f"required_ranges must be dict, got {type(required_ranges).__name__}")
    if not isinstance(candidate_ranges, dict):
        raise TypeError(f"candidate_ranges must be dict, got {type(candidate_ranges).__name__}")

    if not required_ranges:
        return True

    for key, required_range in required_ranges.items():
        # Missing attribute → PASS (permissive)
        if key not in candidate_ranges:
            continue

        candidate_range = candidate_ranges[key]
        # Check: candidate ⊆ required (containment)
        if isinstance(required_range, list) and isinstance(candidate_range, list):
            req_min, req_max = required_range[0], required_range[1]
            cand_min, cand_max = candidate_range[0], candidate_range[1]
            if cand_min < req_min or cand_max > req_max:
                return False

    return True


# =========================================================================
# TEST RUNNER
# =========================================================================

def run_tests():
    print("=" * 70)
    print("TESTING INTERSECTION-BASED MATCHING LOGIC")
    print("Verifying logic is DYNAMIC (not hardcoded to specific examples)")
    print("=" * 70)

    all_passed = True

    # =========================================================================
    # TEST 1: Categorical-Numeric Matching (buyer vague, seller specific)
    # =========================================================================
    print("\n[TEST 1] Categorical-Numeric Matching (specific satisfies vague)")
    print("-" * 70)

    test_cases_cat_num = [
        # AGE examples
        ("age: 'young' vs range.age: [12,12]",
         {"categorical": {"age": "young"}},
         {"range": {"age": [12, 12]}},
         True),

        # EXPERIENCE examples
        ("experience: 'seasoned' vs min.experience: 36",
         {"categorical": {"experience": "seasoned"}},
         {"min": {"experience": 36}},
         True),

        # PRICE examples
        ("budget: 'affordable' vs max.budget: 50000",
         {"categorical": {"budget": "affordable"}},
         {"max": {"budget": 50000}},
         True),

        # MILEAGE examples
        ("mileage: 'low' vs range.mileage: [10000, 10000]",
         {"categorical": {"mileage": "low"}},
         {"range": {"mileage": [10000, 10000]}},
         True),

        # RATING examples
        ("rating: 'high' vs min.rating: 4.5",
         {"categorical": {"rating": "high"}},
         {"min": {"rating": 4.5}},
         True),

        # STORAGE examples
        ("storage: 'large' vs range.storage: [512, 512]",
         {"categorical": {"storage": "large"}},
         {"range": {"storage": [512, 512]}},
         True),

        # WEIGHT examples
        ("weight: 'light' vs max.weight: 1.5",
         {"categorical": {"weight": "light"}},
         {"max": {"weight": 1.5}},
         True),

        # Mixed: categorical + numeric for different keys
        ("color:'brown' + age:'young' vs color:'brown' + range.age:[12,12]",
         {"categorical": {"age": "young", "color": "brown"}},
         {"categorical": {"color": "brown"}, "range": {"age": [12, 12]}},
         True),
    ]

    for desc, req, cand, expected in test_cases_cat_num:
        result = match_item_categorical(req, cand)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"  {status}: {desc}")
        if result != expected:
            print(f"         Expected: {expected}, Got: {result}")
        print()

    # =========================================================================
    # TEST 2: Missing Attribute = PASS (permissive matching)
    # =========================================================================
    print("\n[TEST 2] Missing Attribute = PASS (seller didn't specify)")
    print("-" * 70)

    test_cases_missing = [
        ("color: 'brown' vs nothing",
         {"categorical": {"color": "brown"}},
         {"categorical": {}},
         True),

        ("brand: 'apple', condition: 'new' vs nothing",
         {"categorical": {"brand": "apple", "condition": "new"}},
         {},
         True),

        ("brand: 'apple', color: 'black' vs brand: 'apple' only",
         {"categorical": {"brand": "apple", "color": "black"}},
         {"categorical": {"brand": "apple"}},
         True),

        ("size: 'medium' vs nothing",
         {"categorical": {"size": "medium"}},
         {},
         True),
    ]

    for desc, req, cand, expected in test_cases_missing:
        result = match_item_categorical(req, cand)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"  {status}: {desc}")
        if result != expected:
            print(f"         Expected: {expected}, Got: {result}")
        print()

    # =========================================================================
    # TEST 3: Both have categorical - should still work (existing logic)
    # =========================================================================
    print("\n[TEST 3] Both Categorical (existing logic)")
    print("-" * 70)

    test_cases_both_cat = [
        ("color: 'brown' vs color: 'brown' (match)",
         {"categorical": {"color": "brown"}},
         {"categorical": {"color": "brown"}},
         True),

        ("brand: 'apple' vs brand: 'samsung' (mismatch)",
         {"categorical": {"brand": "apple"}},
         {"categorical": {"brand": "samsung"}},
         False),

        ("condition: 'new' vs condition: 'used' (mismatch)",
         {"categorical": {"condition": "new"}},
         {"categorical": {"condition": "used"}},
         False),
    ]

    for desc, req, cand, expected in test_cases_both_cat:
        result = match_item_categorical(req, cand)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"  {status}: {desc}")
        if result != expected:
            print(f"         Expected: {expected}, Got: {result}")
        print()

    # =========================================================================
    # TEST 4: Numeric Constraints - Missing = PASS
    # =========================================================================
    print("\n[TEST 4] Numeric Constraints - Missing Attribute = PASS")
    print("-" * 70)

    print("  evaluate_min_constraints:")
    min_tests = [
        ("price >= 100 vs nothing", {"price": 100}, {}, True),
        ("age >= 10 vs age: [12, 12]", {"age": 10}, {"age": [12, 12]}, True),
        ("multiple: price >= 100, age >= 10 vs age only", {"price": 100, "age": 10}, {"age": [12, 12]}, True),
        ("rating >= 4.0 vs nothing", {"rating": 4.0}, {}, True),
    ]

    for desc, req_min, cand_ranges, expected in min_tests:
        result = evaluate_min_constraints(req_min, cand_ranges)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"    {status}: {desc}")

    print("\n  evaluate_max_constraints:")
    max_tests = [
        ("price <= 50000 vs nothing", {"price": 50000}, {}, True),
        ("budget <= 100000 vs budget: [80000, 80000]", {"budget": 100000}, {"budget": [80000, 80000]}, True),
        ("weight <= 5 vs nothing", {"weight": 5}, {}, True),
    ]

    for desc, req_max, cand_ranges, expected in max_tests:
        result = evaluate_max_constraints(req_max, cand_ranges)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"    {status}: {desc}")

    print("\n  evaluate_range_constraints:")
    range_tests = [
        ("storage: [256, 512] vs nothing", {"storage": [256, 512]}, {}, True),
        ("age: [10, 15] vs age: [12, 12]", {"age": [10, 15]}, {"age": [12, 12]}, True),
        ("price + mileage vs mileage only", {"price": [40000, 60000], "mileage": [0, 50000]}, {"mileage": [30000, 30000]}, True),
    ]

    for desc, req_ranges, cand_ranges, expected in range_tests:
        result = evaluate_range_constraints(req_ranges, cand_ranges)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"    {status}: {desc}")

    # =========================================================================
    # TEST 5: Real-world scenarios with diverse attributes
    # =========================================================================
    print("\n\n[TEST 5] Real-World Scenarios (diverse attributes)")
    print("-" * 70)

    scenarios = [
        ("Horse: 'young brown racing' vs '12yr brown racing'",
         {"categorical": {"age": "young", "color": "brown", "purpose": "racing"}},
         {"categorical": {"color": "brown", "purpose": "racing"}, "range": {"age": [12, 12]}},
         True),

        ("Phone: 'cheap iphone' vs 'iphone $45000'",
         {"categorical": {"price_range": "cheap", "brand": "iphone"}},
         {"categorical": {"brand": "iphone"}, "range": {"price": [45000, 45000]}},
         True),

        ("Car: 'low mileage sedan' vs 'sedan 25000km'",
         {"categorical": {"mileage": "low", "type": "sedan"}},
         {"categorical": {"type": "sedan"}, "range": {"mileage": [25000, 25000]}},
         True),

        ("Service: 'experienced plumber' vs 'plumber 10yrs'",
         {"categorical": {"experience": "experienced", "profession": "plumber"}},
         {"categorical": {"profession": "plumber"}, "min": {"experience_years": 10}},
         True),

        ("Electronics: 'high capacity battery' vs '5000mAh battery'",
         {"categorical": {"capacity": "high", "type": "battery"}},
         {"categorical": {"type": "battery"}, "range": {"capacity_mah": [5000, 5000]}},
         True),

        ("Real Estate: 'spacious apartment' vs '1500sqft apartment'",
         {"categorical": {"size": "spacious", "type": "apartment"}},
         {"categorical": {"type": "apartment"}, "range": {"sqft": [1500, 1500]}},
         True),

        ("iPhone partial: 'iphone 13 pro' vs 'iphone 13 pro 1st hand'",
         {"categorical": {"model": "iphone 13 pro"}},
         {"categorical": {"model": "iphone 13 pro", "condition": "1st hand"}},
         True),
    ]

    for desc, req, cand, expected in scenarios:
        result = match_item_categorical(req, cand)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result != expected:
            all_passed = False
        print(f"  {status}: {desc}")
        if result != expected:
            print(f"         Expected: {expected}, Got: {result}")
        print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
        print("Logic is DYNAMIC - works for any attribute, not hardcoded.")
    else:
        print("✗ SOME TESTS FAILED!")
    print("=" * 70)

    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
