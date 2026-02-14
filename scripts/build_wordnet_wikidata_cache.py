"""
Build WordNet-Wikidata P8814 Mapping Cache

Downloads mappings from Wikidata SPARQL endpoint that link WordNet 3.1 synset IDs
to Wikidata Q-IDs and aliases. This enables offline enrichment of WordNet senses
with Wikidata's richer synonym data.

Output: canonicalization/static_dicts/wordnet_wikidata_map.json
Expected: ~80,000 mappings (70% of WordNet 3.1)

Usage:
    python3 scripts/build_wordnet_wikidata_cache.py

Requires: SPARQLWrapper
    pip install sparqlwrapper
"""

import json
import time
from pathlib import Path
from typing import Dict, List
from SPARQLWrapper import SPARQLWrapper, JSON


def query_wikidata_p8814() -> List[Dict]:
    """
    Query Wikidata for all items with P8814 (WordNet 3.1 synset ID) property.

    Returns list of {wordnet_id, qid, label, aliases} dicts.
    """
    print("🔄 Querying Wikidata SPARQL endpoint...")
    print("   (This may take 30-60 seconds for ~80K results)")

    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setReturnFormat(JSON)

    # SPARQL query to get all P8814 mappings with aliases
    query = """
    SELECT ?item ?itemLabel ?wordnet_id (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
    WHERE {
      ?item wdt:P8814 ?wordnet_id .
      OPTIONAL { ?item skos:altLabel ?alias FILTER(LANG(?alias) = "en") }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    GROUP BY ?item ?itemLabel ?wordnet_id
    """

    sparql.setQuery(query)

    try:
        start_time = time.time()
        results = sparql.query().convert()
        elapsed = time.time() - start_time
        print(f"✅ Query completed in {elapsed:.1f} seconds")

        return results["results"]["bindings"]

    except Exception as e:
        print(f"❌ SPARQL query failed: {e}")
        print("\n⚠️ Trying alternative query (without aliases)...")
        return query_wikidata_p8814_simple()


def query_wikidata_p8814_simple() -> List[Dict]:
    """
    Simplified query without aliases (fallback if full query times out).
    """
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setReturnFormat(JSON)

    query = """
    SELECT ?item ?itemLabel ?wordnet_id
    WHERE {
      ?item wdt:P8814 ?wordnet_id .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 100000
    """

    sparql.setQuery(query)

    try:
        start_time = time.time()
        results = sparql.query().convert()
        elapsed = time.time() - start_time
        print(f"✅ Simplified query completed in {elapsed:.1f} seconds")

        return results["results"]["bindings"]

    except Exception as e:
        print(f"❌ Simplified query also failed: {e}")
        return []


def build_cache(results: List[Dict]) -> Dict[str, Dict]:
    """
    Build cache dict from SPARQL results.

    Format:
        {
            "01758466-a": {  # WordNet synset ID
                "qid": "Q4818134",
                "label": "second-hand good",
                "aliases": ["secondhand", "second-hand", "pre-owned", "used"]
            }
        }
    """
    cache = {}
    skipped = 0

    for result in results:
        try:
            # Extract WordNet synset ID
            wordnet_id = result["wordnet_id"]["value"]

            # Extract Wikidata Q-ID
            item_uri = result["item"]["value"]
            qid = item_uri.split("/")[-1]  # e.g., "http://www.wikidata.org/entity/Q123" → "Q123"

            # Extract label
            label = result.get("itemLabel", {}).get("value", "")

            # Extract aliases (pipe-separated)
            aliases_str = result.get("aliases", {}).get("value", "")
            aliases = []
            if aliases_str:
                aliases = [a.strip() for a in aliases_str.split("|") if a.strip()]

            # Add label to aliases if not already there
            if label and label.lower() not in [a.lower() for a in aliases]:
                aliases.insert(0, label.lower())

            cache[wordnet_id] = {
                "qid": qid,
                "label": label,
                "aliases": aliases
            }

        except Exception as e:
            skipped += 1
            continue

    print(f"✅ Processed {len(cache)} mappings")
    if skipped > 0:
        print(f"⚠️ Skipped {skipped} invalid entries")

    return cache


def save_cache(cache: Dict, output_path: Path):
    """Save cache to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
    print(f"✅ Cache saved to: {output_path}")
    print(f"   File size: {file_size:.1f} MB")


def main():
    """Main execution."""
    print("=" * 60)
    print("BUILDING WORDNET-WIKIDATA P8814 CACHE")
    print("=" * 60)

    # Step 1: Query Wikidata
    results = query_wikidata_p8814()

    if not results:
        print("❌ No results from Wikidata. Check internet connection.")
        return 1

    # Step 2: Build cache
    cache = build_cache(results)

    if not cache:
        print("❌ Failed to build cache.")
        return 1

    # Step 3: Save to file
    output_path = Path(__file__).parent.parent / "canonicalization/static_dicts/wordnet_wikidata_map.json"
    save_cache(cache, output_path)

    # Step 4: Summary
    print("\n" + "=" * 60)
    print("CACHE BUILD COMPLETE")
    print("=" * 60)
    print(f"Total mappings: {len(cache)}")

    # Sample entry
    if cache:
        sample_id = list(cache.keys())[0]
        sample = cache[sample_id]
        print(f"\nSample entry:")
        print(f"  WordNet ID: {sample_id}")
        print(f"  Wikidata Q-ID: {sample['qid']}")
        print(f"  Label: {sample['label']}")
        print(f"  Aliases ({len(sample['aliases'])}): {sample['aliases'][:5]}")

    print("\n✅ Ready for Path A implementation!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
