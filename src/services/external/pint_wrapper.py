"""
Pint wrapper for unit conversion and normalization.

Uses Pint's built-in unit registry for DYNAMIC conversion between
any units — no hardcoded canonical unit mappings.

Pint knows thousands of units out-of-the-box:
  - Data: byte, kilobyte, megabyte, gigabyte, terabyte...
  - Time: second, minute, hour, day, month, year...
  - Length: meter, kilometer, mile, foot, inch...
  - Mass: gram, kilogram, pound, ounce...
  - Speed: km/h, mph, m/s...
  - Area: m², km², acre, hectare...
  - Temperature: celsius, fahrenheit, kelvin...
  - And hundreds more.

Two values are "comparable" if they share the same dimensionality.
Pint's .to_base_units() converts any unit to its SI base form,
so "256 megabytes" and "0.25 gigabytes" both become the same
value in bytes — no hardcoded target needed.
"""

from typing import Optional, Dict
from pint import UnitRegistry, DimensionalityError


# Global unit registry
_ureg: Optional[UnitRegistry] = None


def get_unit_registry() -> UnitRegistry:
    """
    Get global Pint unit registry instance.

    Returns:
        UnitRegistry instance
    """
    global _ureg

    if _ureg is None:
        _ureg = UnitRegistry()

    return _ureg


def normalize_to_base(value: float, from_unit: str) -> Optional[Dict]:
    """
    Normalize a value to its SI base unit dynamically.

    Pint determines the correct base unit automatically:
      - "256 megabyte" → {"value": 268435456, "unit": "byte"}
      - "3 year"       → {"value": 94608000, "unit": "second"}
      - "5 kilometer"  → {"value": 5000, "unit": "meter"}
      - "100 watt"     → {"value": 100, "unit": "kilogram * meter ** 2 / second ** 3"}

    No hardcoded mapping. Any unit Pint knows is supported.

    Args:
        value: Numeric value
        from_unit: Unit name as recognized by Pint

    Returns:
        Dict with "value", "unit", "original_unit" or None if conversion fails
    """
    try:
        ureg = get_unit_registry()

        quantity = value * ureg(from_unit)
        base = quantity.to_base_units()

        return {
            "value": base.magnitude,
            "unit": str(base.units),
            "original_unit": from_unit
        }

    except (DimensionalityError, AttributeError, ValueError, Exception) as e:
        print(f"Unit conversion error: {value} {from_unit} → base: {e}")
        return None


def normalize_unit(
    value: float, from_unit: str, to_unit: Optional[str] = None
) -> Optional[float]:
    """
    Convert value from one unit to another.

    If to_unit is provided, converts directly.
    If to_unit is None, converts to SI base unit.

    Args:
        value: Numeric value
        from_unit: Source unit (e.g., "megabyte", "mile", "year")
        to_unit: Target unit (optional, uses base unit if not provided)

    Returns:
        Converted value or None if conversion fails
    """
    try:
        ureg = get_unit_registry()

        quantity = value * ureg(from_unit)

        if to_unit:
            converted = quantity.to(to_unit)
        else:
            converted = quantity.to_base_units()

        return converted.magnitude

    except (DimensionalityError, AttributeError, ValueError) as e:
        print(f"Unit conversion error: {value} {from_unit} → {to_unit}: {e}")
        return None


def are_compatible(unit_a: str, unit_b: str) -> bool:
    """
    Check if two units are dimensionally compatible (can be compared).

    Examples:
      - "megabyte", "gigabyte" → True (both data)
      - "kilometer", "mile"    → True (both length)
      - "kilogram", "meter"    → False (mass vs length)

    Args:
        unit_a: First unit name
        unit_b: Second unit name

    Returns:
        True if units can be converted to each other
    """
    try:
        ureg = get_unit_registry()
        return ureg(unit_a).dimensionality == ureg(unit_b).dimensionality
    except Exception:
        return False
