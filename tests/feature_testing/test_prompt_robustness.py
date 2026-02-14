"""
Prompt Robustness Test Suite
============================
Tests 30 queries across all domains and edge cases to validate prompt determinism.

Test Categories:
- Product Domains (10 queries)
- Service Domains (8 queries)
- Mutual Categories (5 queries)
- Edge Cases (7 queries)
  - Compound type decomposition
  - Polysemy resolution
  - Fuzzy quantities
  - Life-stage nouns
  - Domain format
  - Multiplier expansion
  - Breed vs Brand
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Tuple
import os
import time

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
EXTRACT_URL = f"{BASE_URL}/extract"
REQUEST_DELAY = 2  # seconds between requests to avoid rate limiting
REQUEST_TIMEOUT = 60  # seconds timeout per request

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

# ============================================================================
# TEST QUERIES - 30 COMPREHENSIVE TESTS
# ============================================================================

TEST_QUERIES = [
    # =========================================================================
    # PRODUCT DOMAIN TESTS (10)
    # =========================================================================
    {
        "id": "P01",
        "category": "Product - Technology & Electronics",
        "query": "selling my used MacBook Pro with 16GB RAM and 512GB SSD for 80k",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["technology & electronics"],
            "type": "laptop",
            "categorical_keys": ["brand", "condition"],
            "has_numeric": True
        }
    },
    {
        "id": "P02",
        "category": "Product - Pets & Animals",
        "query": "looking to buy a golden retriever puppy under 25000",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain": ["pets & animals"],
            "type": "puppy",
            "categorical_keys": ["breed"],
            "has_numeric": True
        }
    },
    {
        "id": "P03",
        "category": "Product - Automotive & Vehicles",
        "query": "want to buy a second hand Toyota Fortuner diesel automatic under 20 lakhs",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain": ["automotive & vehicles"],
            "type": "car",
            "categorical_keys": ["brand", "model", "condition", "fuel", "transmission"],
            "has_numeric": True
        }
    },
    {
        "id": "P04",
        "category": "Product - Real Estate & Property",
        "query": "2BHK furnished flat for rent in Koramangala around 30k per month",
        "expected": {
            "intent": "product",
            "subintent": "sell",  # rent = sell in context
            "domain": ["real estate & property"],
            "type": "apartment",
            "categorical_keys": ["furnishing"],
            "has_numeric": True
        }
    },
    {
        "id": "P05",
        "category": "Product - Fashion & Apparel",
        "query": "selling brand new Nike Air Jordan size 10 for 15000",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["fashion & apparel"],
            "type": "shoes",
            "categorical_keys": ["brand", "condition"],
            "has_numeric": True
        }
    },
    {
        "id": "P06",
        "category": "Product - Home & Furniture",
        "query": "need a wooden dining table with 6 chairs budget 50k",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain": ["home & furniture"],
            "type": "dining table",
            "has_numeric": True
        }
    },
    {
        "id": "P07",
        "category": "Product - Healthcare & Wellness",
        "query": "looking for a treadmill with at least 3HP motor",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain_contains": "Healthcare",  # Could be Healthcare or Sports
            "type": "treadmill",
            "has_numeric": True
        }
    },
    {
        "id": "P08",
        "category": "Product - Sports & Outdoors",
        "query": "selling my Trek mountain bike 21 speed gear for 35000",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["sports & outdoors"],
            "type": "bicycle",
            "categorical_keys": ["brand"],
            "has_numeric": True
        }
    },
    {
        "id": "P09",
        "category": "Product - Books, Media & Entertainment",
        "query": "want to buy Harry Potter complete book set under 3000",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain": ["books, media & entertainment"],
            "type": "book",
            "has_numeric": True
        }
    },
    {
        "id": "P10",
        "category": "Product - Beauty & Cosmetics",
        "query": "selling MAC lipstick collection 10 pieces for 5000",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["beauty & cosmetics"],
            "type": "lipstick",
            "categorical_keys": ["brand"],
            "has_numeric": True
        }
    },

    # =========================================================================
    # SERVICE DOMAIN TESTS (8)
    # =========================================================================
    {
        "id": "S01",
        "category": "Service - Construction & Trades",
        "query": "need a Kannada speaking plumber urgently in Jayanagar",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain": ["construction & trades"],
            "type": "plumbing",
            "other_party_language": "kannada"
        }
    },
    {
        "id": "S02",
        "category": "Service - Education & Training",
        "query": "looking for a math tutor for 10th grade CBSE with 5 years experience",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain": ["education & training"],
            "type": "tutoring",
            "has_experience_constraint": True
        }
    },
    {
        "id": "S03",
        "category": "Service - Personal Services",
        "query": "I am a professional makeup artist with 8 years experience available for weddings",
        "expected": {
            "intent": "service",
            "subintent": "provide",
            "domain": ["personal services"],
            "type": "makeup",
            "has_self_attributes": True
        }
    },
    {
        "id": "S04",
        "category": "Service - Finance, Insurance & Legal",
        "query": "need a CA for GST filing and tax consultation",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain": ["finance, insurance & legal"],
            "type_contains": ["accounting", "tax", "consultation"]
        }
    },
    {
        "id": "S05",
        "category": "Service - Repair & Maintenance Services",
        "query": "AC repair needed urgently, Samsung split AC not cooling",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain": ["repair & maintenance services"],
            "type_contains": ["repair", "ac"]
        }
    },
    {
        "id": "S06",
        "category": "Service - Transportation & Logistics",
        "query": "need a driver for daily office commute in Bangalore",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain": ["transportation & logistics"],
            "type": "driver"
        }
    },
    {
        "id": "S07",
        "category": "Service - Marketing, Advertising & Design",
        "query": "I'm a graphic designer with expertise in logo design and branding",
        "expected": {
            "intent": "service",
            "subintent": "provide",
            "domain": ["marketing, advertising & design"],
            "type_contains": ["design", "graphic"]
        }
    },
    {
        "id": "S08",
        "category": "Service - Hospitality, Travel & Accommodation",
        "query": "looking for a caterer for 200 guests wedding reception",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "domain_contains": "Hospitality",
            "type": "catering"
        }
    },

    # =========================================================================
    # MUTUAL CATEGORY TESTS (5)
    # =========================================================================
    {
        "id": "M01",
        "category": "Mutual - Roommates",
        "query": "I am a 25 year old female IT professional looking for a female roommate in Koramangala, non-smoker preferred",
        "expected": {
            "intent": "mutual",
            "subintent": "connect",
            "primary_mutual_category": ["roommates"],
            "has_self_attributes": True,
            "has_other_party_preferences": True
        }
    },
    {
        "id": "M02",
        "category": "Mutual - Fitness",
        "query": "looking for a gym buddy in HSR Layout, morning 6am workout",
        "expected": {
            "intent": "mutual",
            "subintent": "connect",
            "primary_mutual_category": ["fitness"]
        }
    },
    {
        "id": "M03",
        "category": "Mutual - Travel",
        "query": "anyone interested in a Ladakh bike trip next month?",
        "expected": {
            "intent": "mutual",
            "subintent": "connect",
            "primary_mutual_category_contains": ["Travel", "Adventure"]
        }
    },
    {
        "id": "M04",
        "category": "Mutual - Professional",
        "query": "looking for a technical cofounder for my AI startup",
        "expected": {
            "intent": "mutual",
            "subintent": "connect",
            "primary_mutual_category": ["professional"]
        }
    },
    {
        "id": "M05",
        "category": "Mutual - Study",
        "query": "UPSC aspirants study group forming in Rajajinagar",
        "expected": {
            "intent": "mutual",
            "subintent": "connect",
            "primary_mutual_category": ["study"]
        }
    },

    # =========================================================================
    # EDGE CASE TESTS (7)
    # =========================================================================
    {
        "id": "E01",
        "category": "Edge Case - Compound Type Decomposition",
        "query": "selling a Persian cat 6 months old",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "type": "cat",
            "categorical_keys": ["breed"],
            "breed_value": "persian"
        }
    },
    {
        "id": "E02",
        "category": "Edge Case - Polysemy Resolution",
        "query": "need a notebook for coding under 60k",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "domain": ["technology & electronics"],
            "type": "laptop",  # NOT paper notebook
            "has_numeric": True
        }
    },
    {
        "id": "E03",
        "category": "Edge Case - Fuzzy Quantity",
        "query": "looking for a developer with around 5 years experience",
        "expected": {
            "intent": "service",
            "subintent": "seek",
            "has_experience_range": True  # Should be range, not exact
        }
    },
    {
        "id": "E04",
        "category": "Edge Case - Life-Stage Noun",
        "query": "want to adopt a labrador puppy",
        "expected": {
            "intent": "product",
            "subintent": "buy",
            "type": "puppy",  # NOT "dog"
            "categorical_keys": ["breed"],
            "breed_value": "labrador"
        }
    },
    {
        "id": "E05",
        "category": "Edge Case - Multiplier Expansion",
        "query": "selling plot in Whitefield for 1.5 crore",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["real estate & property"],
            "price_value": 15000000  # 1.5 crore = 15,000,000
        }
    },
    {
        "id": "E06",
        "category": "Edge Case - Breed as Standalone",
        "query": "selling a beagle with all vaccinations done",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "type": "dog",  # Beagle implies dog
            "categorical_keys": ["breed"],
            "breed_value": "beagle"
        }
    },
    {
        "id": "E07",
        "category": "Edge Case - Multiple Items",
        "query": "selling iPhone 14 Pro and AirPods Pro together for 90k",
        "expected": {
            "intent": "product",
            "subintent": "sell",
            "domain": ["technology & electronics"],
            "multiple_items": True,
            "has_numeric": True
        }
    }
]


def extract_query(query: str) -> Dict[str, Any]:
    """Call the /extract endpoint."""
    try:
        response = requests.post(EXTRACT_URL, json={"query": query}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def validate_extraction(result: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate extraction result against expected values."""
    issues = []

    if "error" in result:
        return False, [f"API Error: {result['error']}"]

    extracted = result.get("extracted_listing", {})

    # Check intent
    if "intent" in expected:
        if extracted.get("intent") != expected["intent"]:
            issues.append(f"Intent mismatch: got '{extracted.get('intent')}', expected '{expected['intent']}'")

    # Check subintent
    if "subintent" in expected:
        if extracted.get("subintent") != expected["subintent"]:
            issues.append(f"Subintent mismatch: got '{extracted.get('subintent')}', expected '{expected['subintent']}'")

    # Check domain (exact match)
    if "domain" in expected:
        actual_domain = extracted.get("domain", [])
        if actual_domain != expected["domain"]:
            issues.append(f"Domain mismatch: got {actual_domain}, expected {expected['domain']}")

    # Check domain contains
    if "domain_contains" in expected:
        actual_domain = str(extracted.get("domain", []))
        if expected["domain_contains"] not in actual_domain:
            issues.append(f"Domain should contain '{expected['domain_contains']}', got {actual_domain}")

    # Check primary_mutual_category
    if "primary_mutual_category" in expected:
        actual_cat = extracted.get("primary_mutual_category", [])
        if actual_cat != expected["primary_mutual_category"]:
            issues.append(f"Category mismatch: got {actual_cat}, expected {expected['primary_mutual_category']}")

    # Check primary_mutual_category contains
    if "primary_mutual_category_contains" in expected:
        actual_cat = str(extracted.get("primary_mutual_category", []))
        found = any(cat in actual_cat for cat in expected["primary_mutual_category_contains"])
        if not found:
            issues.append(f"Category should contain one of {expected['primary_mutual_category_contains']}, got {actual_cat}")

    # Check item type
    if "type" in expected:
        items = extracted.get("items", [])
        if items:
            actual_type = items[0].get("type", "").lower()
            expected_type = expected["type"].lower()
            if actual_type != expected_type:
                issues.append(f"Type mismatch: got '{actual_type}', expected '{expected_type}'")
        else:
            issues.append(f"No items found, expected type '{expected['type']}'")

    # Check type contains
    if "type_contains" in expected:
        items = extracted.get("items", [])
        if items:
            actual_type = items[0].get("type", "").lower()
            found = any(t in actual_type for t in expected["type_contains"])
            if not found:
                issues.append(f"Type should contain one of {expected['type_contains']}, got '{actual_type}'")

    # Check categorical keys exist
    if "categorical_keys" in expected:
        items = extracted.get("items", [])
        if items:
            categorical = items[0].get("categorical", {})
            for key in expected["categorical_keys"]:
                if key not in categorical:
                    issues.append(f"Missing categorical key: '{key}'")

    # Check breed value
    if "breed_value" in expected:
        items = extracted.get("items", [])
        if items:
            breed = items[0].get("categorical", {}).get("breed", "").lower()
            if breed != expected["breed_value"]:
                issues.append(f"Breed mismatch: got '{breed}', expected '{expected['breed_value']}'")

    # Check has numeric constraints
    if expected.get("has_numeric"):
        items = extracted.get("items", [])
        if items:
            item = items[0]
            has_numeric = bool(item.get("min") or item.get("max") or item.get("range"))
            if not has_numeric:
                issues.append("Expected numeric constraints (min/max/range) but none found")

    # Check has self_attributes
    if expected.get("has_self_attributes"):
        self_attrs = extracted.get("self_attributes", {})
        if not self_attrs or self_attrs == {}:
            issues.append("Expected self_attributes but none found")

    # Check has other_party_preferences
    if expected.get("has_other_party_preferences"):
        other_prefs = extracted.get("other_party_preferences", {})
        if not other_prefs or other_prefs == {}:
            issues.append("Expected other_party_preferences but none found")

    # Check other_party language
    if "other_party_language" in expected:
        other_prefs = extracted.get("other_party_preferences", {})
        # Check in identity array
        identity = other_prefs.get("identity", [])
        found_lang = False
        for item in identity:
            if item.get("type") == "language" and item.get("value", "").lower() == expected["other_party_language"]:
                found_lang = True
                break
        if not found_lang:
            issues.append(f"Expected language '{expected['other_party_language']}' in other_party_preferences")

    # Check experience constraint
    if expected.get("has_experience_constraint"):
        other_prefs = extracted.get("other_party_preferences", {})
        has_exp = bool(other_prefs.get("min") or other_prefs.get("max") or other_prefs.get("range"))
        if not has_exp:
            issues.append("Expected experience constraint in other_party_preferences")

    # Check experience range (fuzzy)
    if expected.get("has_experience_range"):
        other_prefs = extracted.get("other_party_preferences", {})
        range_data = other_prefs.get("range", {})
        has_range = bool(range_data.get("time"))
        if not has_range:
            # Also check min (acceptable for fuzzy)
            has_min = bool(other_prefs.get("min", {}).get("time"))
            if not has_min:
                issues.append("Expected experience range/min in other_party_preferences")

    # Check multiple items
    if expected.get("multiple_items"):
        items = extracted.get("items", [])
        if len(items) < 2:
            issues.append(f"Expected multiple items, found {len(items)}")

    # Check price value
    if "price_value" in expected:
        items = extracted.get("items", [])
        if items:
            item = items[0]
            price_found = False
            for field in ["min", "max", "range"]:
                if field in item:
                    cost = item[field].get("cost", [])
                    for c in cost:
                        val = c.get("value") or c.get("min") or c.get("max")
                        if val and abs(val - expected["price_value"]) < 1000000:  # Allow 10% tolerance
                            price_found = True
                            break
            if not price_found:
                issues.append(f"Price should be ~{expected['price_value']}")

    return len(issues) == 0, issues


def run_tests() -> Dict[str, Any]:
    """Run all tests and return results."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(TEST_QUERIES),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "test_results": [],
        "summary_by_category": {}
    }

    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}PROMPT ROBUSTNESS TEST SUITE - 30 QUERIES{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

    for test in TEST_QUERIES:
        print(f"{CYAN}[{test['id']}] {test['category']}{RESET}")
        print(f"  Query: \"{test['query'][:60]}...\"" if len(test['query']) > 60 else f"  Query: \"{test['query']}\"")

        # Extract
        result = extract_query(test["query"])

        # Validate
        passed, issues = validate_extraction(result, test["expected"])

        # Record result
        test_result = {
            "id": test["id"],
            "category": test["category"],
            "query": test["query"],
            "expected": test["expected"],
            "actual": result.get("extracted_listing", result),
            "passed": passed,
            "issues": issues
        }
        results["test_results"].append(test_result)

        # Update counters
        if "error" in result:
            results["errors"] += 1
            print(f"  {RED}ERROR: {result['error']}{RESET}")
        elif passed:
            results["passed"] += 1
            print(f"  {GREEN}PASSED{RESET}")
        else:
            results["failed"] += 1
            print(f"  {RED}FAILED{RESET}")
            for issue in issues:
                print(f"    - {issue}")

        # Track by category
        cat_base = test["category"].split(" - ")[0]
        if cat_base not in results["summary_by_category"]:
            results["summary_by_category"][cat_base] = {"passed": 0, "failed": 0, "total": 0}
        results["summary_by_category"][cat_base]["total"] += 1
        if passed:
            results["summary_by_category"][cat_base]["passed"] += 1
        else:
            results["summary_by_category"][cat_base]["failed"] += 1

        print()

        # Add delay between requests to avoid rate limiting
        time.sleep(REQUEST_DELAY)

    return results


def generate_report(results: Dict[str, Any]) -> str:
    """Generate markdown report."""
    report = []
    report.append("# Prompt Robustness Test Report")
    report.append(f"\n**Generated:** {results['timestamp']}")
    report.append(f"\n**Endpoint:** {EXTRACT_URL}")
    report.append("")

    # Summary
    report.append("## Summary")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total Tests | {results['total_tests']} |")
    report.append(f"| Passed | {results['passed']} |")
    report.append(f"| Failed | {results['failed']} |")
    report.append(f"| Errors | {results['errors']} |")
    report.append(f"| Pass Rate | {results['passed']/results['total_tests']*100:.1f}% |")
    report.append("")

    # By Category
    report.append("## Results by Category")
    report.append("")
    report.append("| Category | Passed | Failed | Total | Pass Rate |")
    report.append("|----------|--------|--------|-------|-----------|")
    for cat, stats in results["summary_by_category"].items():
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        report.append(f"| {cat} | {stats['passed']} | {stats['failed']} | {stats['total']} | {rate:.0f}% |")
    report.append("")

    # Detailed Results
    report.append("## Detailed Test Results")
    report.append("")

    for test in results["test_results"]:
        status = "PASS" if test["passed"] else "FAIL"
        emoji = "✅" if test["passed"] else "❌"

        report.append(f"### {emoji} [{test['id']}] {test['category']}")
        report.append("")
        report.append(f"**Query:** `{test['query']}`")
        report.append("")
        report.append(f"**Status:** {status}")
        report.append("")

        if test["issues"]:
            report.append("**Issues:**")
            for issue in test["issues"]:
                report.append(f"- {issue}")
            report.append("")

        # Show extracted data
        report.append("<details>")
        report.append("<summary>Extracted Data</summary>")
        report.append("")
        report.append("```json")
        report.append(json.dumps(test["actual"], indent=2))
        report.append("```")
        report.append("</details>")
        report.append("")

    # Failed Tests Summary
    failed_tests = [t for t in results["test_results"] if not t["passed"]]
    if failed_tests:
        report.append("## Failed Tests Summary")
        report.append("")
        report.append("| ID | Category | Issue Summary |")
        report.append("|----|----------|---------------|")
        for test in failed_tests:
            issue_summary = test["issues"][0] if test["issues"] else "Unknown"
            report.append(f"| {test['id']} | {test['category']} | {issue_summary[:50]}... |")
        report.append("")

    # Recommendations
    report.append("## Recommendations")
    report.append("")
    if results["passed"] == results["total_tests"]:
        report.append("All tests passed! The prompt is handling all test cases correctly.")
    else:
        report.append("Based on failed tests, consider:")
        report.append("")
        for test in failed_tests:
            report.append(f"- **{test['id']}**: Review handling of {test['category'].split(' - ')[1]}")
    report.append("")

    return "\n".join(report)


def main():
    """Main entry point."""
    print(f"{YELLOW}Starting Prompt Robustness Tests...{RESET}")
    print(f"{YELLOW}Testing against: {EXTRACT_URL}{RESET}\n")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"{GREEN}Server is running!{RESET}\n")
    except:
        print(f"{RED}Server not running! Start with: uvicorn main:app --reload{RESET}")
        print(f"{YELLOW}Continuing anyway to generate test structure...{RESET}\n")

    # Run tests
    results = run_tests()

    # Print summary
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

    print(f"Total Tests: {results['total_tests']}")
    print(f"{GREEN}Passed: {results['passed']}{RESET}")
    print(f"{RED}Failed: {results['failed']}{RESET}")
    print(f"{YELLOW}Errors: {results['errors']}{RESET}")
    print(f"Pass Rate: {results['passed']/results['total_tests']*100:.1f}%")

    # Generate report
    report = generate_report(results)

    # Save report
    report_path = os.path.join(os.path.dirname(__file__), "PROMPT_ROBUSTNESS_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{GREEN}Report saved to: {report_path}{RESET}")

    # Save raw results as JSON
    results_path = os.path.join(os.path.dirname(__file__), "prompt_robustness_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"{GREEN}Raw results saved to: {results_path}{RESET}")

    return results


if __name__ == "__main__":
    results = main()
    exit(0 if results["failed"] == 0 and results["errors"] == 0 else 1)
