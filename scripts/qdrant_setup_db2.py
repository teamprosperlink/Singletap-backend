"""
QDRANT DB2 SETUP SCRIPT

Creates collections on the NEW Qdrant cluster (DB2) without affecting the existing cluster.
Uses QDRANT_ENDPOINT_2 and QDRANT_API_KEY_2 from .env

Collections:
- product_vectors (384D, COSINE)
- service_vectors (384D, COSINE)
- mutual_vectors (384D, COSINE)

Author: Migration Script
Date: 2026-02-14
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    OptimizersConfigDiff,
    HnswConfigDiff
)
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION - DB2 (New Qdrant Cluster)
# ============================================================================

QDRANT_ENDPOINT_2 = os.getenv("QDRANT_ENDPOINT_2")
QDRANT_API_KEY_2 = os.getenv("QDRANT_API_KEY_2")

# Vector configuration - matches BAAI/bge-small-en-v1.5
VECTOR_SIZE = 384
DISTANCE_METRIC = Distance.COSINE

COLLECTIONS = [
    "product_vectors",
    "service_vectors",
    "mutual_vectors"
]


def create_collections(client: QdrantClient) -> None:
    """
    Create Qdrant collections with proper vector configuration.
    """
    print("=" * 70)
    print("STEP 1: COLLECTION CREATION")
    print("=" * 70)
    print()

    vector_config = VectorParams(
        size=VECTOR_SIZE,
        distance=DISTANCE_METRIC
    )

    # Optimizers configuration for production use
    optimizers_config = OptimizersConfigDiff(
        indexing_threshold=20000,
        memmap_threshold=50000
    )

    # HNSW index configuration
    hnsw_config = HnswConfigDiff(
        m=16,
        ef_construct=100,
        full_scan_threshold=10000
    )

    for collection_name in COLLECTIONS:
        print(f"Creating collection: {collection_name}")

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vector_config,
            optimizers_config=optimizers_config,
            hnsw_config=hnsw_config
        )

        print(f"  Created: {collection_name}")
        print(f"  - Vector size: {VECTOR_SIZE}D")
        print(f"  - Distance metric: {DISTANCE_METRIC}")
        print()


def create_payload_indexes(client: QdrantClient) -> None:
    """
    Create payload indexes for efficient filtering.
    """
    print("=" * 70)
    print("STEP 2: PAYLOAD INDEX CREATION")
    print("=" * 70)
    print()

    # Product and Service collections: index by domain
    product_service_indexes = [
        ("listing_id", "keyword"),
        ("intent", "keyword"),
        ("domain", "keyword"),
        ("created_at", "integer")
    ]

    # Mutual collection: index by category
    mutual_indexes = [
        ("listing_id", "keyword"),
        ("intent", "keyword"),
        ("category", "keyword"),
        ("created_at", "integer")
    ]

    # Create indexes for product and service collections
    for collection_name in ["product_vectors", "service_vectors"]:
        print(f"Creating payload indexes for: {collection_name}")

        for field_name, field_type in product_service_indexes:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  Indexed: {field_name} ({field_type})")

        print()

    # Create indexes for mutual collection
    print("Creating payload indexes for: mutual_vectors")

    for field_name, field_type in mutual_indexes:
        client.create_payload_index(
            collection_name="mutual_vectors",
            field_name=field_name,
            field_schema=field_type
        )
        print(f"  Indexed: {field_name} ({field_type})")

    print()


def verify_setup(client: QdrantClient) -> bool:
    """
    Verify that all collections were created correctly.
    """
    print("=" * 70)
    print("STEP 3: VERIFICATION")
    print("=" * 70)
    print()

    all_valid = True

    for collection_name in COLLECTIONS:
        try:
            info = client.get_collection(collection_name)

            print(f"Collection: {collection_name}")
            print(f"  - Vectors count: {info.vectors_count}")
            print(f"  - Points count: {info.points_count}")
            print(f"  - Status: {info.status}")
            print(f"  - Vector size: {info.config.params.vectors.size}D")
            print(f"  - Distance: {info.config.params.vectors.distance}")

            if info.config.params.vectors.size != VECTOR_SIZE:
                print(f"  ERROR: Vector size mismatch (expected {VECTOR_SIZE})")
                all_valid = False
            else:
                print(f"  Configuration valid")

            print()

        except Exception as e:
            print(f"ERROR: Collection {collection_name} not found")
            print(f"  Error: {e}")
            all_valid = False

    return all_valid


def main():
    """
    Execute Qdrant DB2 setup.
    """
    print()
    print("=" * 70)
    print("QDRANT DB2 SETUP - NEW CLUSTER")
    print("=" * 70)
    print()

    # Validate environment variables
    if not QDRANT_ENDPOINT_2:
        print("ERROR: QDRANT_ENDPOINT_2 not set in .env")
        sys.exit(1)
    if not QDRANT_API_KEY_2:
        print("ERROR: QDRANT_API_KEY_2 not set in .env")
        sys.exit(1)

    print(f"Target: {QDRANT_ENDPOINT_2}")
    print()

    # Connect to Qdrant DB2
    try:
        print("Connecting to Qdrant DB2...")
        client = QdrantClient(
            url=QDRANT_ENDPOINT_2,
            api_key=QDRANT_API_KEY_2
        )

        # Test connection
        collections = client.get_collections()
        print(f"Connected! Existing collections: {[c.name for c in collections.collections]}")
        print()
    except Exception as e:
        print(f"ERROR: Failed to connect to Qdrant DB2")
        print(f"  Error: {e}")
        sys.exit(1)

    # Execute setup steps
    create_collections(client)
    create_payload_indexes(client)

    # Verify setup
    if verify_setup(client):
        print("=" * 70)
        print("QDRANT DB2 SETUP COMPLETE")
        print("=" * 70)
    else:
        print("=" * 70)
        print("SETUP COMPLETED WITH ERRORS")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
