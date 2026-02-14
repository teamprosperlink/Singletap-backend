"""
Quantitative Resolver for numeric values with units.

Fully dynamic normalization using Quantulum3 + Pint:
  1. Quantulum3 extracts quantity + unit from ANY text (dynamic, all units)
  2. Pint converts to SI base units (dynamic, no hardcoded target)

Both values being compared end up in the same base unit automatically,
so "256 megabytes" and "0.25 gigabytes" both become bytes -- comparable.

Examples:
- "256gb"              -> Quantulum: 256 gigabyte -> Pint base: 274877906944 byte
- "3 years experience" -> Quantulum: 3 year       -> Pint base: 94608000 second
- "50k"                -> Currency handler: 50000 (no unit conversion)
- "100 watts"          -> Quantulum: 100 watt     -> Pint base: 100 kg*m2/s3
"""

from typing import Dict, Optional
from services.external.quantulum_wrapper import extract_first_quantity
from services.external.pint_wrapper import normalize_to_base


class QuantitativeResolver:
    """
    Resolver for numeric values with units.

    Fully dynamic two-stage normalization:
    1. Extract quantity from text (Quantulum3)
    2. Normalize to SI base unit (Pint)
    """

    def __init__(self):
        pass

    def resolve(self, value_str: str) -> Optional[Dict]:
        """
        Resolve a quantitative value to its base-unit form.

        Args:
            value_str: Value as string (e.g., "256gb", "5 miles", "3 years")

        Returns:
            Dict with "value", "unit", "original", "confidence" or None
        """
        quantity = extract_first_quantity(value_str)

        if not quantity:
            try:
                value = float(value_str)
                return {
                    "value": value,
                    "unit": "dimensionless",
                    "original": value_str,
                    "confidence": 0.5
                }
            except ValueError:
                return None

        base = normalize_to_base(quantity.value, quantity.unit)

        if base:
            return {
                "value": base["value"],
                "unit": base["unit"],
                "original_unit": base["original_unit"],
                "original": value_str,
                "confidence": 0.9
            }

        return {
            "value": quantity.value,
            "unit": quantity.unit,
            "original": value_str,
            "confidence": 0.7
        }

    def resolve_currency(self, value_str: str, currency: Optional[str] = None) -> Optional[Dict]:
        """
        Resolve currency value.

        Currency is NOT a physical unit -- Pint cannot convert between
        currencies. This handles numeric shorthand (lakh, crore, k)
        and preserves the currency code.

        Args:
            value_str: Value as string (e.g., "50k", "2.5 lakh")
            currency: Currency code (USD, INR, EUR) or None for "local"

        Returns:
            Dict with "value", "currency", "original"
        """
        value_lower = value_str.lower().replace(',', '')

        multiplier = 1
        if 'crore' in value_lower or 'cr' in value_lower:
            multiplier = 10000000
            value_lower = value_lower.replace('crore', '').replace('cr', '').strip()
        elif 'lakh' in value_lower or 'lac' in value_lower:
            multiplier = 100000
            value_lower = value_lower.replace('lakh', '').replace('lac', '').strip()
        elif 'k' in value_lower:
            multiplier = 1000
            value_lower = value_lower.replace('k', '').strip()

        try:
            value = float(value_lower) * multiplier

            return {
                "value": value,
                "currency": currency if currency else "local",
                "original": value_str,
                "confidence": 0.9
            }
        except ValueError:
            return None
