"""
VRIDDHI API TESTING - Smart Test Data Preparation (V2)

Purpose: Create test pairs that are actually likely to match by:
1. Pairing entries with the SAME item type (for products/services)
2. Creating both positive cases (should match) and negative cases (shouldn't match)

Test Data:
- 40 Product pairs: 30 matching type + 10 non-matching type
- 40 Service pairs: 30 matching type + 10 non-matching type
- 100 Mutual pairs: By similar categories

Author: Claude
Date: 2025-02-23
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict

# Configuration
JSONL_PATH = Path(__file__).parent.parent / "stage1_stage2_stage3_combined.jsonl"
OUTPUT_DIR = Path(__file__).parent / "test_data"

# Sample sizes
PRODUCT_MATCHING_PAIRS = 30  # Same item type (likely to match)
PRODUCT_NONMATCHING_PAIRS = 10  # Different item type (unlikely to match)
SERVICE_MATCHING_PAIRS = 30
SERVICE_NONMATCHING_PAIRS = 10
MUTUAL_PAIRS = 100

RANDOM_SEED = 42


def load_jsonl_data() -> List[Dict]:
    """Load all entries from the JSONL file."""
    print(f"Loading data from {JSONL_PATH}...")
    entries = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    print(f"Loaded {len(entries):,} entries")
    return entries


def get_item_type(entry: Dict) -> str:
    """Extract the primary item type from an entry."""
    stage3 = entry.get("stage3", {})
    items = stage3.get("items", [])
    if items and len(items) > 0:
        return items[0].get("type", "").lower().strip()
    return ""


def get_mutual_category(entry: Dict) -> str:
    """Extract the mutual category from an entry."""
    stage3 = entry.get("stage3", {})
    cats = stage3.get("primary_mutual_category", [])
    if cats:
        return cats[0].lower().strip()
    # Fallback to domain
    domains = stage3.get("domain", [])
    if domains:
        return domains[0].lower().strip()
    return ""


def categorize_by_item_type(entries: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Categorize entries by source, subintent, and item type.
    Returns: {source: {subintent: {item_type: [entries]}}}
    """
    categorized = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for entry in entries:
        source = entry.get("source", "unknown")
        stage2 = entry.get("stage2", {})
        subintent = stage2.get("subintent", "unknown")
        item_type = get_item_type(entry)

        if item_type:  # Only include entries with item types
            categorized[source][subintent][item_type].append(entry)

    return categorized


def find_matching_product_pairs(categorized: Dict) -> Tuple[List[Dict], List[Dict]]:
    """
    Find product pairs where buy and sell have the SAME item type.
    Returns (matching_pairs, non_matching_pairs)
    """
    print("\n=== Finding Product Pairs ===")

    buy_by_type = categorized.get("product", {}).get("buy", {})
    sell_by_type = categorized.get("product", {}).get("sell", {})

    # Find common item types
    common_types = set(buy_by_type.keys()) & set(sell_by_type.keys())
    print(f"  Common item types: {len(common_types)}")

    # Sample some common types for inspection
    sample_types = list(common_types)[:10]
    print(f"  Sample types: {sample_types}")

    matching_pairs = []
    non_matching_pairs = []

    # Create matching pairs (same item type)
    for item_type in common_types:
        buys = buy_by_type[item_type]
        sells = sell_by_type[item_type]

        # Pair up
        for i in range(min(len(buys), len(sells))):
            if len(matching_pairs) >= PRODUCT_MATCHING_PAIRS:
                break

            matching_pairs.append({
                "seed_entry": {
                    "id": sells[i]["id"],
                    "query": sells[i]["query"],
                    "source": "product",
                    "subintent": "sell",
                    "stage2": sells[i].get("stage2", {}),
                    "stage3": sells[i].get("stage3", {})
                },
                "query_entry": {
                    "id": buys[i]["id"],
                    "query": buys[i]["query"],
                    "source": "product",
                    "subintent": "buy",
                    "stage2": buys[i].get("stage2", {}),
                    "stage3": buys[i].get("stage3", {})
                },
                "expected_match": True,  # Same item type - likely to match
                "pair_type": "product",
                "item_type": item_type,
                "notes": f"Same item type: {item_type} - likely to match"
            })

        if len(matching_pairs) >= PRODUCT_MATCHING_PAIRS:
            break

    print(f"  Matching pairs found: {len(matching_pairs)}")

    # Create non-matching pairs (different item types)
    all_buys = []
    all_sells = []
    for item_type, entries in buy_by_type.items():
        for e in entries:
            e["_item_type"] = item_type
            all_buys.append(e)
    for item_type, entries in sell_by_type.items():
        for e in entries:
            e["_item_type"] = item_type
            all_sells.append(e)

    random.shuffle(all_buys)
    random.shuffle(all_sells)

    for buy in all_buys:
        if len(non_matching_pairs) >= PRODUCT_NONMATCHING_PAIRS:
            break

        # Find a sell with DIFFERENT item type
        for sell in all_sells:
            if sell["_item_type"] != buy["_item_type"]:
                non_matching_pairs.append({
                    "seed_entry": {
                        "id": sell["id"],
                        "query": sell["query"],
                        "source": "product",
                        "subintent": "sell",
                        "stage2": sell.get("stage2", {}),
                        "stage3": sell.get("stage3", {})
                    },
                    "query_entry": {
                        "id": buy["id"],
                        "query": buy["query"],
                        "source": "product",
                        "subintent": "buy",
                        "stage2": buy.get("stage2", {}),
                        "stage3": buy.get("stage3", {})
                    },
                    "expected_match": False,  # Different item type - won't match
                    "pair_type": "product",
                    "item_type": f"{buy['_item_type']} vs {sell['_item_type']}",
                    "notes": f"Different types: {buy['_item_type']} vs {sell['_item_type']} - won't match"
                })
                all_sells.remove(sell)
                break

    print(f"  Non-matching pairs found: {len(non_matching_pairs)}")

    return matching_pairs, non_matching_pairs


def find_matching_service_pairs(categorized: Dict) -> Tuple[List[Dict], List[Dict]]:
    """
    Find service pairs where seek and provide have the SAME service type.
    """
    print("\n=== Finding Service Pairs ===")

    seek_by_type = categorized.get("service", {}).get("seek", {})
    provide_by_type = categorized.get("service", {}).get("provide", {})

    common_types = set(seek_by_type.keys()) & set(provide_by_type.keys())
    print(f"  Common service types: {len(common_types)}")
    print(f"  Sample types: {list(common_types)[:10]}")

    matching_pairs = []
    non_matching_pairs = []

    # Create matching pairs
    for svc_type in common_types:
        seeks = seek_by_type[svc_type]
        provides = provide_by_type[svc_type]

        for i in range(min(len(seeks), len(provides))):
            if len(matching_pairs) >= SERVICE_MATCHING_PAIRS:
                break

            matching_pairs.append({
                "seed_entry": {
                    "id": provides[i]["id"],
                    "query": provides[i]["query"],
                    "source": "service",
                    "subintent": "provide",
                    "stage2": provides[i].get("stage2", {}),
                    "stage3": provides[i].get("stage3", {})
                },
                "query_entry": {
                    "id": seeks[i]["id"],
                    "query": seeks[i]["query"],
                    "source": "service",
                    "subintent": "seek",
                    "stage2": seeks[i].get("stage2", {}),
                    "stage3": seeks[i].get("stage3", {})
                },
                "expected_match": True,
                "pair_type": "service",
                "item_type": svc_type,
                "notes": f"Same service: {svc_type} - likely to match"
            })

        if len(matching_pairs) >= SERVICE_MATCHING_PAIRS:
            break

    print(f"  Matching pairs found: {len(matching_pairs)}")

    # Create non-matching pairs
    all_seeks = []
    all_provides = []
    for svc_type, entries in seek_by_type.items():
        for e in entries:
            e["_item_type"] = svc_type
            all_seeks.append(e)
    for svc_type, entries in provide_by_type.items():
        for e in entries:
            e["_item_type"] = svc_type
            all_provides.append(e)

    random.shuffle(all_seeks)
    random.shuffle(all_provides)

    for seek in all_seeks:
        if len(non_matching_pairs) >= SERVICE_NONMATCHING_PAIRS:
            break

        for provide in all_provides:
            if provide["_item_type"] != seek["_item_type"]:
                non_matching_pairs.append({
                    "seed_entry": {
                        "id": provide["id"],
                        "query": provide["query"],
                        "source": "service",
                        "subintent": "provide",
                        "stage2": provide.get("stage2", {}),
                        "stage3": provide.get("stage3", {})
                    },
                    "query_entry": {
                        "id": seek["id"],
                        "query": seek["query"],
                        "source": "service",
                        "subintent": "seek",
                        "stage2": seek.get("stage2", {}),
                        "stage3": seek.get("stage3", {})
                    },
                    "expected_match": False,
                    "pair_type": "service",
                    "item_type": f"{seek['_item_type']} vs {provide['_item_type']}",
                    "notes": f"Different services: won't match"
                })
                all_provides.remove(provide)
                break

    print(f"  Non-matching pairs found: {len(non_matching_pairs)}")

    return matching_pairs, non_matching_pairs


def find_mutual_pairs(entries: List[Dict]) -> List[Dict]:
    """
    Find mutual pairs by grouping connect entries by category.
    """
    print("\n=== Finding Mutual Pairs ===")

    # Filter to mutual/connect entries
    connect_entries = [
        e for e in entries
        if e.get("source") == "mutual" and e.get("stage2", {}).get("subintent") == "connect"
    ]

    print(f"  Total connect entries: {len(connect_entries)}")

    # Group by category
    by_category = defaultdict(list)
    for entry in connect_entries:
        cat = get_mutual_category(entry)
        if cat:
            by_category[cat].append(entry)

    print(f"  Categories found: {len(by_category)}")
    print(f"  Sample categories: {list(by_category.keys())[:10]}")

    pairs = []

    # Create pairs within same category
    for cat, cat_entries in by_category.items():
        if len(cat_entries) >= 2:
            for i in range(0, len(cat_entries) - 1, 2):
                if len(pairs) >= MUTUAL_PAIRS:
                    break

                entry_a = cat_entries[i]
                entry_b = cat_entries[i + 1]

                pairs.append({
                    "seed_entry": {
                        "id": entry_a["id"],
                        "query": entry_a["query"],
                        "source": "mutual",
                        "subintent": "connect",
                        "stage2": entry_a.get("stage2", {}),
                        "stage3": entry_a.get("stage3", {})
                    },
                    "query_entry": {
                        "id": entry_b["id"],
                        "query": entry_b["query"],
                        "source": "mutual",
                        "subintent": "connect",
                        "stage2": entry_b.get("stage2", {}),
                        "stage3": entry_b.get("stage3", {})
                    },
                    "expected_match": True,  # Same category - likely to match
                    "pair_type": "mutual",
                    "item_type": cat,
                    "notes": f"Same category: {cat}"
                })

        if len(pairs) >= MUTUAL_PAIRS:
            break

    print(f"  Pairs found: {len(pairs)}")

    return pairs


def save_test_data(
    product_matching: List[Dict],
    product_nonmatching: List[Dict],
    service_matching: List[Dict],
    service_nonmatching: List[Dict],
    mutual_pairs: List[Dict]
):
    """Save all test data to JSON files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Combine product pairs
    all_product = product_matching + product_nonmatching
    random.shuffle(all_product)

    # Combine service pairs
    all_service = service_matching + service_nonmatching
    random.shuffle(all_service)

    # Save
    with open(OUTPUT_DIR / "product_pairs.json", "w", encoding="utf-8") as f:
        json.dump(all_product, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "service_pairs.json", "w", encoding="utf-8") as f:
        json.dump(all_service, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "mutual_pairs.json", "w", encoding="utf-8") as f:
        json.dump(mutual_pairs, f, indent=2, ensure_ascii=False)

    # Create seed listings and test queries
    all_pairs = all_product + all_service + mutual_pairs

    seed_listings = []
    test_queries = []

    for i, pair in enumerate(all_pairs):
        seed = pair["seed_entry"]
        query = pair["query_entry"]

        seed_listings.append({
            "test_id": f"test_{pair['pair_type']}_{i+1:03d}",
            "original_id": seed["id"],
            "query": seed["query"],
            "source": seed["source"],
            "subintent": seed["subintent"],
            "normalized_query": seed["stage3"],
            "notes": pair.get("notes", "")
        })

        test_queries.append({
            "test_id": f"test_{pair['pair_type']}_{i+1:03d}",
            "original_id": query["id"],
            "query": query["query"],
            "source": query["source"],
            "subintent": query["subintent"],
            "stage2": query["stage2"],
            "stage3": query["stage3"],
            "expected_to_match_seed": seed["id"],
            "expected_match": pair["expected_match"],
            "pair_type": pair["pair_type"],
            "notes": pair.get("notes", "")
        })

    with open(OUTPUT_DIR / "seed_listings.json", "w", encoding="utf-8") as f:
        json.dump(seed_listings, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "test_queries.json", "w", encoding="utf-8") as f:
        json.dump(test_queries, f, indent=2, ensure_ascii=False)

    # Summary
    expected_matches = sum(1 for p in all_pairs if p["expected_match"])
    expected_non_matches = sum(1 for p in all_pairs if not p["expected_match"])

    summary = {
        "total_pairs": len(all_pairs),
        "product_pairs": len(all_product),
        "product_expected_match": sum(1 for p in all_product if p["expected_match"]),
        "product_expected_no_match": sum(1 for p in all_product if not p["expected_match"]),
        "service_pairs": len(all_service),
        "service_expected_match": sum(1 for p in all_service if p["expected_match"]),
        "service_expected_no_match": sum(1 for p in all_service if not p["expected_match"]),
        "mutual_pairs": len(mutual_pairs),
        "total_expected_matches": expected_matches,
        "total_expected_non_matches": expected_non_matches,
        "files": [
            "product_pairs.json",
            "service_pairs.json",
            "mutual_pairs.json",
            "seed_listings.json",
            "test_queries.json"
        ]
    }

    with open(OUTPUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Test Data Saved ===")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"\nTotal pairs: {len(all_pairs)}")
    print(f"  - Product: {len(all_product)} ({sum(1 for p in all_product if p['expected_match'])} match, {sum(1 for p in all_product if not p['expected_match'])} no-match)")
    print(f"  - Service: {len(all_service)} ({sum(1 for p in all_service if p['expected_match'])} match, {sum(1 for p in all_service if not p['expected_match'])} no-match)")
    print(f"  - Mutual: {len(mutual_pairs)} (all expected to match)")
    print(f"\nExpected outcomes:")
    print(f"  - Should match: {expected_matches}")
    print(f"  - Should NOT match: {expected_non_matches}")


def main():
    random.seed(RANDOM_SEED)

    print("=" * 60)
    print("VRIDDHI API TESTING - Smart Test Data Preparation V2")
    print("=" * 60)

    # Load data
    entries = load_jsonl_data()

    # Categorize by item type
    categorized = categorize_by_item_type(entries)

    # Find pairs
    product_matching, product_nonmatching = find_matching_product_pairs(categorized)
    service_matching, service_nonmatching = find_matching_service_pairs(categorized)
    mutual_pairs = find_mutual_pairs(entries)

    # Save
    save_test_data(
        product_matching, product_nonmatching,
        service_matching, service_nonmatching,
        mutual_pairs
    )

    print("\n" + "=" * 60)
    print("Smart test data preparation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
