"""
API Layer: FastAPI routes and endpoints.

This module contains all API endpoints for the Vriddhi Matching Engine.
"""

from .routes import router, set_global_state, get_global_state

__all__ = ["router", "set_global_state", "get_global_state"]
