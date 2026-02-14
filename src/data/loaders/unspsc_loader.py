"""
UNSPSC (United Nations Standard Products and Services Code) Taxonomy Loader.

Loads UNSPSC hierarchy from Excel file into memory for fast lookups.
Hierarchy: Segment → Family → Class → Commodity
"""

import pandas as pd
from typing import Dict, List, Optional, Set
from pathlib import Path


class UNSPSCLoader:
    """
    Load and query UNSPSC taxonomy.

    The UNSPSC provides a 4-level hierarchical classification:
    - Segment (2 digits, e.g., "10000000" - Live Plant and Animal Material)
    - Family (4 digits, e.g., "10100000" - Live animals)
    - Class (6 digits, e.g., "10101500" - Livestock)
    - Commodity (8 digits, e.g., "10101501" - Cats)
    """

    def __init__(self, file_path: str):
        """
        Initialize UNSPSC loader.

        Args:
            file_path: Path to UNSPSC Excel file
        """
        self.file_path = Path(file_path)
        self.df: Optional[pd.DataFrame] = None
        self.segment_index: Dict[str, Set[str]] = {}
        self.family_index: Dict[str, Set[str]] = {}
        self.class_index: Dict[str, Set[str]] = {}
        self.commodity_index: Dict[str, str] = {}
        self._loaded = False

    def load(self):
        """Load UNSPSC taxonomy from Excel file and build indices."""
        if self._loaded:
            print("⚠️  UNSPSC already loaded, skipping...")
            return

        print(f"📖 Loading UNSPSC taxonomy from {self.file_path}...")

        # Read file - row 11 contains column labels as data
        df_raw = pd.read_excel(self.file_path, header=11)

        # Use first row as column names, then drop it
        df_raw.columns = df_raw.iloc[0]
        self.df = df_raw[1:].reset_index(drop=True)

        # Clean up: remove rows where Commodity is NaN (main identifier)
        self.df = self.df.dropna(subset=['Commodity'])

        print(f"✅ Loaded {len(self.df)} UNSPSC commodities")

        # Build indices for fast lookup
        self._build_indices()
        self._loaded = True
        print("✅ UNSPSC taxonomy loaded successfully")

    def _build_indices(self):
        """Build lookup indices for each hierarchy level."""
        print("🔨 Building UNSPSC indices...")

        for _, row in self.df.iterrows():
            segment = str(row['Segment Title']).lower() if pd.notna(row.get('Segment Title')) else ""
            family = str(row['Family Title']).lower() if pd.notna(row.get('Family Title')) else ""
            class_title = str(row['Class Title']).lower() if pd.notna(row.get('Class Title')) else ""
            commodity = str(row['Commodity Title']).lower() if pd.notna(row.get('Commodity Title')) else ""
            commodity_code = str(row['Commodity']) if pd.notna(row.get('Commodity')) else ""

            # Index by segment → commodities
            if segment and segment != "nan":
                if segment not in self.segment_index:
                    self.segment_index[segment] = set()
                if commodity:
                    self.segment_index[segment].add(commodity)

            # Index by family → commodities
            if family and family != "nan":
                if family not in self.family_index:
                    self.family_index[family] = set()
                if commodity:
                    self.family_index[family].add(commodity)

            # Index by class → commodities
            if class_title and class_title != "nan":
                if class_title not in self.class_index:
                    self.class_index[class_title] = set()
                if commodity:
                    self.class_index[class_title].add(commodity)

            # Index by commodity code → commodity title
            if commodity_code and commodity:
                self.commodity_index[commodity_code] = commodity

        print(f"✅ Indexed {len(self.segment_index)} segments, "
              f"{len(self.family_index)} families, "
              f"{len(self.class_index)} classes, "
              f"{len(self.commodity_index)} commodities")

    def find_commodity_by_term(self, term: str) -> Optional[Dict]:
        """
        Find commodity information by search term.

        Args:
            term: Search term (e.g., "laptop", "dog", "plumbing")

        Returns:
            Dict with commodity information or None
        """
        if not self._loaded:
            self.load()

        term_lower = term.lower()

        # Search in commodity titles first (most specific)
        matches = self.df[
            self.df['Commodity Title'].str.lower().str.contains(term_lower, na=False)
        ]

        if not matches.empty:
            row = matches.iloc[0]
            return {
                "segment": row['Segment Title'],
                "segment_code": row['Segment'],
                "family": row['Family Title'],
                "family_code": row['Family'],
                "class": row['Class Title'],
                "class_code": row['Class'],
                "commodity": row['Commodity Title'],
                "commodity_code": row['Commodity'],
            }

        # Fallback: search in class titles
        matches = self.df[
            self.df['Class Title'].str.lower().str.contains(term_lower, na=False)
        ]

        if not matches.empty:
            row = matches.iloc[0]
            return {
                "segment": row['Segment Title'],
                "segment_code": row['Segment'],
                "family": row['Family Title'],
                "family_code": row['Family'],
                "class": row['Class Title'],
                "class_code": row['Class'],
                "commodity": row['Commodity Title'],
                "commodity_code": row['Commodity'],
            }

        return None

    def get_hierarchy(self, commodity_code: str) -> Optional[Dict]:
        """
        Get full hierarchy for a commodity code.

        Args:
            commodity_code: 8-digit UNSPSC code (e.g., "10101501")

        Returns:
            Dict with full hierarchy path
        """
        if not self._loaded:
            self.load()

        matches = self.df[self.df['Commodity'] == int(commodity_code)]
        if matches.empty:
            return None

        row = matches.iloc[0]
        return {
            "segment": row['Segment Title'],
            "family": row['Family Title'],
            "class": row['Class Title'],
            "commodity": row['Commodity Title'],
            "path": [
                row['Segment Title'],
                row['Family Title'],
                row['Class Title'],
                row['Commodity Title']
            ],
            "codes": {
                "segment": row['Segment'],
                "family": row['Family'],
                "class": row['Class'],
                "commodity": row['Commodity']
            }
        }

    def get_commodities_by_class(self, class_title: str) -> List[str]:
        """
        Get all commodities under a class.

        Args:
            class_title: Class title (e.g., "Livestock")

        Returns:
            List of commodity titles
        """
        if not self._loaded:
            self.load()

        return list(self.class_index.get(class_title.lower(), set()))


# Global singleton instance
_unspsc_loader: Optional[UNSPSCLoader] = None


def get_unspsc_loader(file_path: Optional[str] = None) -> UNSPSCLoader:
    """
    Get singleton UNSPSC loader instance.

    Args:
        file_path: Path to UNSPSC Excel file (required on first call)

    Returns:
        UNSPSCLoader instance
    """
    global _unspsc_loader

    if _unspsc_loader is None:
        if file_path is None:
            raise ValueError("file_path required for first initialization")
        _unspsc_loader = UNSPSCLoader(file_path)
        _unspsc_loader.load()

    return _unspsc_loader
