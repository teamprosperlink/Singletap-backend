"""
Static dictionaries for Phase 0 preprocessing.

All dicts are pure Python literals, loaded at import time. No I/O.
"""

from .abbreviations import ABBREVIATIONS
from .mwe_reductions import GENERAL_MWE, ATTRIBUTE_MWE
from .spelling_variants import UK_TO_US
from .demonyms import DEMONYMS

__all__ = [
    "ABBREVIATIONS",
    "GENERAL_MWE",
    "ATTRIBUTE_MWE",
    "UK_TO_US",
    "DEMONYMS",
]
