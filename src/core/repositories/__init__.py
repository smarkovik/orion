"""
Repository implementations for data access.

Repositories handle loading and saving domain objects from/to storage.
"""

from .library_repository import LibraryRepository

__all__ = [
    "LibraryRepository",
]
