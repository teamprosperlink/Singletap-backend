"""
Taxonomy loaders for GPC, UNSPSC, and other classification systems.
"""

from .gpc_loader import GPCLoader
from .unspsc_loader import UNSPSCLoader

__all__ = ["GPCLoader", "UNSPSCLoader"]
