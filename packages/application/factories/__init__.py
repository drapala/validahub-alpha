"""
Application layer factories for creating domain objects.

These factories handle parsing and transformation of external data
into domain objects, keeping the domain layer pure.
"""

from .ccm_factory import CCMFactory

__all__ = ["CCMFactory"]