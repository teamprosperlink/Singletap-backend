"""
GPC (Global Product Classification) Taxonomy Loader.

Loads GPC hierarchy from Excel file into memory for fast lookups.
Hierarchy: Segment → Family → Class → Brick → Attributes → Values
"""

import pandas as pd
from typing import Dict, List, Optional, Set
from pathlib import Path


class GPCLoader:
    """
    Load and query GPC taxonomy.

    The GPC provides a hierarchical product classification system:
    - Segment (e.g., "Arts/Crafts/Needlework")
    - Family (e.g., "Arts/Crafts/Needlework Supplies")
    - Class (e.g., "Artists Painting/Drawing Supplies")
    - Brick (e.g., "Artists Brushes/Applicators")
    - Attributes (e.g., "Type of Artists Brush/Applicator")
    - Attribute Values (e.g., "ARTISTS FLAT BRUSH")
    """

    def __init__(self, file_path: str):
        """
        Initialize GPC loader and load taxonomy.

        Args:
            file_path: Path to GPC Excel file
        """
        self.file_path = Path(file_path)
        self.df: Optional[pd.DataFrame] = None
        self.segment_index: Dict[str, Set[str]] = {}
        self.family_index: Dict[str, Set[str]] = {}
        self.class_index: Dict[str, Set[str]] = {}
        self.brick_index: Dict[str, Set[str]] = {}
        self._loaded = False

    def load(self):
        """Load GPC taxonomy from Excel file and build indices."""
        if self._loaded:
            print("⚠️  GPC already loaded, skipping...")
            return

        print(f"📖 Loading GPC taxonomy from {self.file_path}...")
        self.df = pd.read_excel(self.file_path)

        # Clean column names
        print(f"✅ Loaded {len(self.df)} rows")
        print(f"📊 Columns: {list(self.df.columns)}")

        # Build indices for fast lookup
        self._build_indices()
        self._loaded = True
        print("✅ GPC taxonomy loaded successfully")

    def _build_indices(self):
        """Build lookup indices for each hierarchy level."""
        print("🔨 Building GPC indices...")

        # Index by segment title → brick titles
        for _, row in self.df.iterrows():
            segment = str(row['SegmentTitle']).lower()
            family = str(row['FamilyTitle']).lower()
            class_title = str(row['ClassTitle']).lower()
            brick = str(row['BrickTitle']).lower()

            if segment not in self.segment_index:
                self.segment_index[segment] = set()
            self.segment_index[segment].add(brick)

            if family not in self.family_index:
                self.family_index[family] = set()
            self.family_index[family].add(brick)

            if class_title not in self.class_index:
                self.class_index[class_title] = set()
            self.class_index[class_title].add(brick)

            if brick not in self.brick_index:
                self.brick_index[brick] = set()
            self.brick_index[brick].add(brick)

        print(f"✅ Indexed {len(self.segment_index)} segments, "
              f"{len(self.family_index)} families, "
              f"{len(self.class_index)} classes, "
              f"{len(self.brick_index)} bricks")

    def find_brick_by_term(self, term: str) -> Optional[Dict]:
        """
        Find brick information by search term.

        Args:
            term: Search term (e.g., "laptop", "artist brush")

        Returns:
            Dict with brick information or None
        """
        if not self._loaded:
            self.load()

        term_lower = term.lower()

        # Search in brick titles first (most specific)
        matches = self.df[self.df['BrickTitle'].str.lower().str.contains(term_lower, na=False)]

        if not matches.empty:
            row = matches.iloc[0]
            return {
                "segment": row['SegmentTitle'],
                "family": row['FamilyTitle'],
                "class": row['ClassTitle'],
                "brick": row['BrickTitle'],
                "segment_code": row['SegmentCode'],
                "family_code": row['FamilyCode'],
                "class_code": row['ClassCode'],
                "brick_code": row['BrickCode'],
            }

        # Fallback: search in class titles
        matches = self.df[self.df['ClassTitle'].str.lower().str.contains(term_lower, na=False)]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "segment": row['SegmentTitle'],
                "family": row['FamilyTitle'],
                "class": row['ClassTitle'],
                "brick": row['BrickTitle'],
                "segment_code": row['SegmentCode'],
                "family_code": row['FamilyCode'],
                "class_code": row['ClassCode'],
                "brick_code": row['BrickCode'],
            }

        return None

    def get_hierarchy(self, brick_title: str) -> Optional[Dict]:
        """
        Get full hierarchy for a brick.

        Args:
            brick_title: Brick title (e.g., "Artists Brushes/Applicators")

        Returns:
            Dict with full hierarchy path
        """
        if not self._loaded:
            self.load()

        matches = self.df[self.df['BrickTitle'].str.lower() == brick_title.lower()]
        if matches.empty:
            return None

        row = matches.iloc[0]
        return {
            "segment": row['SegmentTitle'],
            "family": row['FamilyTitle'],
            "class": row['ClassTitle'],
            "brick": row['BrickTitle'],
            "path": [
                row['SegmentTitle'],
                row['FamilyTitle'],
                row['ClassTitle'],
                row['BrickTitle']
            ]
        }

    def get_attributes_for_brick(self, brick_title: str) -> List[Dict]:
        """
        Get all attributes and their values for a brick.

        Args:
            brick_title: Brick title

        Returns:
            List of dicts with attribute info
        """
        if not self._loaded:
            self.load()

        matches = self.df[self.df['BrickTitle'].str.lower() == brick_title.lower()]

        attributes = []
        for _, row in matches.iterrows():
            if pd.notna(row.get('AttributeTitle')):
                attributes.append({
                    "attribute_code": row.get('AttributeCode'),
                    "attribute_title": row.get('AttributeTitle'),
                    "attribute_value_code": row.get('AttributeValueCode'),
                    "attribute_value_title": row.get('AttributeValueTitle'),
                })

        return attributes


# Global singleton instance
_gpc_loader: Optional[GPCLoader] = None


def get_gpc_loader(file_path: Optional[str] = None) -> GPCLoader:
    """
    Get singleton GPC loader instance.

    Args:
        file_path: Path to GPC Excel file (required on first call)

    Returns:
        GPCLoader instance
    """
    global _gpc_loader

    if _gpc_loader is None:
        if file_path is None:
            raise ValueError("file_path required for first initialization")
        _gpc_loader = GPCLoader(file_path)
        _gpc_loader.load()

    return _gpc_loader
