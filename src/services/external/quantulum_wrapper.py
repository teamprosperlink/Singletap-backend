"""
Quantulum3 wrapper for extracting quantities from text.

quantulum3 extracts quantities with units from natural language text.
Example: "256gb storage" → Quantity(value=256, unit="gigabyte")
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Quantity:
    """
    Represents an extracted quantity.

    Attributes:
        value: Numeric value
        unit: Unit name (e.g., "gigabyte", "meter", "year")
        surface: Original text surface form (e.g., "256gb", "5 years")
        entity: Entity type (e.g., "storage", "length", "time")
    """
    value: float
    unit: str
    surface: str
    entity: str


def extract_quantities(text: str) -> List[Quantity]:
    """
    Extract quantities from text using quantulum3.

    Args:
        text: Text to parse (e.g., "laptop with 256gb ssd and 16gb ram")

    Returns:
        List of Quantity objects
    """
    try:
        # Import quantulum3 (lazy import to avoid startup delay)
        from quantulum3 import parser

        # Parse text
        quantities = parser.parse(text)

        # Convert to our Quantity dataclass
        results = []
        for q in quantities:
            results.append(Quantity(
                value=q.value,
                unit=q.unit.name,
                surface=q.surface,
                entity=q.unit.entity.name if q.unit.entity else "unknown"
            ))

        return results

    except ImportError:
        print("⚠️  quantulum3 not installed. Install with: pip install quantulum3")
        return []

    except Exception as e:
        print(f"⚠️  Error parsing quantities from '{text}': {e}")
        return []


def extract_first_quantity(text: str) -> Optional[Quantity]:
    """
    Extract the first quantity from text.

    Args:
        text: Text to parse

    Returns:
        First Quantity object or None
    """
    quantities = extract_quantities(text)
    return quantities[0] if quantities else None
