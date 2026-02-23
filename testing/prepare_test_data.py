"""
VRIDDHI API TESTING FRAMEWORK - Test Data Preparation Script

Purpose: Extract and prepare test pairs from the combined JSONL dataset
for comprehensive API testing.

Test Data:
- 40 Product pairs (40 buy + 40 sell = 80 entries)
- 40 Service pairs (40 seek + 40 provide = 80 entries)
- 100 Mutual pairs (100 connect entries, paired by similarity)

Output:
- test_data/product_pairs.json (buy/sell pairs for matching)
- test_data/service_pairs.json (seek/provide pairs for matching)
- test_data/mutual_pairs.json (connect entries for matching)
- test_data/seed_listings.json (listings to seed via /ingest)
- test_data/test_queries.json (queries to test matching)

Author: Claude
Date: 2025-02-23
"""

import json
import random
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict

# Configuration
JSONL_PATH = Path(__file__).parent.parent / "stage1_stage2_stage3_combined.jsonl"
OUTPUT_DIR = Path(__file__).parent / "test_data"

# Sample sizes
PRODUCT_PAIRS = 40  # 40 buy + 40 sell
SERVICE_PAIRS = 40  # 40 seek + 40 provide
MUTUAL_PAIRS = 100  # 100 connect entries

# Random seed for reproducibility
RANDOM_SEED = 42


@dataclass
class TestEntry:
    """A single test entry with all necessary data."""
    id: str
    query: str
    source: str  # product, service, mutual
    subintent: str  # buy, sell, seek, provide, connect
    stage2: Dict[str, Any]
    stage3: Dict[str, Any]


@dataclass
class TestPair:
    """A pair of entries for matching test."""
    seed_entry: TestEntry  # Entry to seed in DB
    query_entry: TestEntry  # Entry to use as query
    expected_match: bool  # Whether they should match
    pair_type: str  # product, service, mutual
    notes: str  # Description of the test case


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


def categorize_entries(entries: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
    """Categorize entries by source and subintent."""
    categorized = defaultdict(lambda: defaultdict(list))

    for entry in entries:
        source = entry.get("source", "unknown")
        stage2 = entry.get("stage2", {})
        subintent = stage2.get("subintent", "unknown")

        categorized[source][subintent].append(entry)

    # Print distribution
    print("\n=== Data Distribution ===")
    for source in sorted(categorized.keys()):
        print(f"\n{source.upper()}:")
        for subintent, items in sorted(categorized[source].items()):
            print(f"  {subintent}: {len(items):,}")

    return categorized


def get_opposite_subintent(subintent: str) -> str:
    """Get the matching opposite subintent."""
    opposites = {
        "buy": "sell",
        "sell": "buy",
        "seek": "provide",
        "provide": "seek",
        "connect": "connect"
    }
    return opposites.get(subintent, subintent)


def extract_category(entry: Dict) -> str:
    """Extract the main category from stage3 data."""
    stage3 = entry.get("stage3", {})

    # Try different category fields
    if "product_category" in stage3:
        return stage3["product_category"]
    if "service_category" in stage3:
        return stage3["service_category"]
    if "connection_type" in stage3:
        return stage3["connection_type"]
    if "category" in stage3:
        return stage3["category"]

    return "general"


def find_matching_pairs(
    entries_a: List[Dict],
    entries_b: List[Dict],
    count: int
) -> List[Tuple[Dict, Dict]]:
    """Find pairs with matching categories for better test cases."""
    # Group by category
    by_category_a = defaultdict(list)
    by_category_b = defaultdict(list)

    for entry in entries_a:
        cat = extract_category(entry)
        by_category_a[cat].append(entry)

    for entry in entries_b:
        cat = extract_category(entry)
        by_category_b[cat].append(entry)

    # Find common categories
    common_cats = set(by_category_a.keys()) & set(by_category_b.keys())
    print(f"  Found {len(common_cats)} common categories")

    pairs = []

    # First, pick from common categories
    for cat in common_cats:
        available_a = by_category_a[cat]
        available_b = by_category_b[cat]

        # Pick min of what's available in both
        pick_count = min(len(available_a), len(available_b), max(1, count // len(common_cats)))

        for i in range(pick_count):
            if len(pairs) >= count:
                break
            pairs.append((available_a[i], available_b[i]))

        if len(pairs) >= count:
            break

    # If still need more, pick randomly
    remaining = count - len(pairs)
    if remaining > 0:
        # Get entries not yet used
        used_ids = {e["id"] for pair in pairs for e in pair}
        unused_a = [e for e in entries_a if e["id"] not in used_ids]
        unused_b = [e for e in entries_b if e["id"] not in used_ids]

        random.shuffle(unused_a)
        random.shuffle(unused_b)

        for i in range(min(remaining, len(unused_a), len(unused_b))):
            pairs.append((unused_a[i], unused_b[i]))

    return pairs[:count]


def select_product_pairs(categorized: Dict) -> List[TestPair]:
    """Select 40 product pairs (buy/sell)."""
    print("\n=== Selecting Product Pairs ===")

    buy_entries = categorized.get("product", {}).get("buy", [])
    sell_entries = categorized.get("product", {}).get("sell", [])

    print(f"  Available: {len(buy_entries)} buy, {len(sell_entries)} sell")

    random.shuffle(buy_entries)
    random.shuffle(sell_entries)

    # Find matching pairs by category
    pairs = find_matching_pairs(sell_entries, buy_entries, PRODUCT_PAIRS)

    test_pairs = []
    for sell_entry, buy_entry in pairs:
        sell_test = TestEntry(
            id=sell_entry["id"],
            query=sell_entry["query"],
            source="product",
            subintent="sell",
            stage2=sell_entry.get("stage2", {}),
            stage3=sell_entry.get("stage3", {})
        )
        buy_test = TestEntry(
            id=buy_entry["id"],
            query=buy_entry["query"],
            source="product",
            subintent="buy",
            stage2=buy_entry.get("stage2", {}),
            stage3=buy_entry.get("stage3", {})
        )

        test_pairs.append(TestPair(
            seed_entry=sell_test,  # Seed seller listing
            query_entry=buy_test,  # Query as buyer
            expected_match=True,  # May or may not match (category-based pairing)
            pair_type="product",
            notes=f"Product pair: {extract_category(sell_entry)}"
        ))

    print(f"  Selected {len(test_pairs)} product pairs")
    return test_pairs


def select_service_pairs(categorized: Dict) -> List[TestPair]:
    """Select 40 service pairs (seek/provide)."""
    print("\n=== Selecting Service Pairs ===")

    seek_entries = categorized.get("service", {}).get("seek", [])
    provide_entries = categorized.get("service", {}).get("provide", [])

    print(f"  Available: {len(seek_entries)} seek, {len(provide_entries)} provide")

    random.shuffle(seek_entries)
    random.shuffle(provide_entries)

    # Find matching pairs by category
    pairs = find_matching_pairs(provide_entries, seek_entries, SERVICE_PAIRS)

    test_pairs = []
    for provide_entry, seek_entry in pairs:
        provide_test = TestEntry(
            id=provide_entry["id"],
            query=provide_entry["query"],
            source="service",
            subintent="provide",
            stage2=provide_entry.get("stage2", {}),
            stage3=provide_entry.get("stage3", {})
        )
        seek_test = TestEntry(
            id=seek_entry["id"],
            query=seek_entry["query"],
            source="service",
            subintent="seek",
            stage2=seek_entry.get("stage2", {}),
            stage3=seek_entry.get("stage3", {})
        )

        test_pairs.append(TestPair(
            seed_entry=provide_test,  # Seed provider listing
            query_entry=seek_test,    # Query as seeker
            expected_match=True,
            pair_type="service",
            notes=f"Service pair: {extract_category(provide_entry)}"
        ))

    print(f"  Selected {len(test_pairs)} service pairs")
    return test_pairs


def select_mutual_pairs(categorized: Dict) -> List[TestPair]:
    """Select 100 mutual pairs (connect/connect)."""
    print("\n=== Selecting Mutual Pairs ===")

    connect_entries = categorized.get("mutual", {}).get("connect", [])

    print(f"  Available: {len(connect_entries)} connect entries")

    random.shuffle(connect_entries)

    # For mutual, we need 100 pairs = 200 entries
    # But they should be grouped by category for potential matches
    by_category = defaultdict(list)
    for entry in connect_entries:
        cat = extract_category(entry)
        by_category[cat].append(entry)

    test_pairs = []

    # Pick pairs from same category
    for cat, entries in by_category.items():
        if len(entries) >= 2:
            for i in range(0, len(entries) - 1, 2):
                if len(test_pairs) >= MUTUAL_PAIRS:
                    break

                entry_a = entries[i]
                entry_b = entries[i + 1]

                test_a = TestEntry(
                    id=entry_a["id"],
                    query=entry_a["query"],
                    source="mutual",
                    subintent="connect",
                    stage2=entry_a.get("stage2", {}),
                    stage3=entry_a.get("stage3", {})
                )
                test_b = TestEntry(
                    id=entry_b["id"],
                    query=entry_b["query"],
                    source="mutual",
                    subintent="connect",
                    stage2=entry_b.get("stage2", {}),
                    stage3=entry_b.get("stage3", {})
                )

                test_pairs.append(TestPair(
                    seed_entry=test_a,
                    query_entry=test_b,
                    expected_match=True,
                    pair_type="mutual",
                    notes=f"Mutual pair: {cat}"
                ))

        if len(test_pairs) >= MUTUAL_PAIRS:
            break

    print(f"  Selected {len(test_pairs)} mutual pairs")
    return test_pairs


def create_seed_listings(test_pairs: List[TestPair]) -> List[Dict]:
    """Create listings to seed via /ingest endpoint."""
    seed_listings = []

    for i, pair in enumerate(test_pairs):
        entry = pair.seed_entry

        # Create listing in format expected by /ingest
        listing = {
            "test_id": f"test_{pair.pair_type}_{i+1:03d}",
            "original_id": entry.id,
            "query": entry.query,
            "source": entry.source,
            "subintent": entry.subintent,
            "normalized_query": entry.stage3,  # Stage 3 is the normalized form
            "notes": pair.notes
        }
        seed_listings.append(listing)

    return seed_listings


def create_test_queries(test_pairs: List[TestPair]) -> List[Dict]:
    """Create queries for testing matching."""
    test_queries = []

    for i, pair in enumerate(test_pairs):
        entry = pair.query_entry

        query = {
            "test_id": f"test_{pair.pair_type}_{i+1:03d}",
            "original_id": entry.id,
            "query": entry.query,
            "source": entry.source,
            "subintent": entry.subintent,
            "stage2": entry.stage2,
            "stage3": entry.stage3,
            "expected_to_match_seed": pair.seed_entry.id,
            "pair_type": pair.pair_type,
            "notes": pair.notes
        }
        test_queries.append(query)

    return test_queries


def save_test_data(
    product_pairs: List[TestPair],
    service_pairs: List[TestPair],
    mutual_pairs: List[TestPair]
):
    """Save all test data to JSON files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Convert TestPair objects to dicts
    def pairs_to_dict(pairs: List[TestPair]) -> List[Dict]:
        result = []
        for pair in pairs:
            result.append({
                "seed_entry": asdict(pair.seed_entry),
                "query_entry": asdict(pair.query_entry),
                "expected_match": pair.expected_match,
                "pair_type": pair.pair_type,
                "notes": pair.notes
            })
        return result

    # Save individual pair files
    with open(OUTPUT_DIR / "product_pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs_to_dict(product_pairs), f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "service_pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs_to_dict(service_pairs), f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "mutual_pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs_to_dict(mutual_pairs), f, indent=2, ensure_ascii=False)

    # Combine all pairs
    all_pairs = product_pairs + service_pairs + mutual_pairs

    # Create seed listings
    seed_listings = create_seed_listings(all_pairs)
    with open(OUTPUT_DIR / "seed_listings.json", "w", encoding="utf-8") as f:
        json.dump(seed_listings, f, indent=2, ensure_ascii=False)

    # Create test queries
    test_queries = create_test_queries(all_pairs)
    with open(OUTPUT_DIR / "test_queries.json", "w", encoding="utf-8") as f:
        json.dump(test_queries, f, indent=2, ensure_ascii=False)

    # Create summary
    summary = {
        "total_pairs": len(all_pairs),
        "product_pairs": len(product_pairs),
        "service_pairs": len(service_pairs),
        "mutual_pairs": len(mutual_pairs),
        "total_seed_listings": len(seed_listings),
        "total_test_queries": len(test_queries),
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
    print(f"Total pairs: {len(all_pairs)}")
    print(f"  - Product pairs: {len(product_pairs)}")
    print(f"  - Service pairs: {len(service_pairs)}")
    print(f"  - Mutual pairs: {len(mutual_pairs)}")
    print(f"Seed listings: {len(seed_listings)}")
    print(f"Test queries: {len(test_queries)}")


def main():
    """Main entry point."""
    random.seed(RANDOM_SEED)

    print("=" * 60)
    print("VRIDDHI API TESTING - Test Data Preparation")
    print("=" * 60)

    # Load data
    entries = load_jsonl_data()

    # Categorize
    categorized = categorize_entries(entries)

    # Select pairs
    product_pairs = select_product_pairs(categorized)
    service_pairs = select_service_pairs(categorized)
    mutual_pairs = select_mutual_pairs(categorized)

    # Save
    save_test_data(product_pairs, service_pairs, mutual_pairs)

    print("\n" + "=" * 60)
    print("Test data preparation complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run the test runner: python -m testing.run_tests --seed")
    print("2. Run matching tests: python -m testing.run_tests --match")
    print("3. Generate report: python -m testing.run_tests --report")


if __name__ == "__main__":
    main()
