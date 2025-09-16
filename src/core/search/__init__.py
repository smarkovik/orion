"""
Search functionality for the Orion document processing system.

This module provides search capabilities across user document libraries,
including multiple search algorithms and result ranking.
"""

from .interfaces import ILibrarySearchEngine, ISearchAlgorithm
from .query import ChunkSearchResult, SearchAlgorithm, SearchQuery, SearchResults

__all__ = [
    "ISearchAlgorithm",
    "ILibrarySearchEngine",
    "SearchQuery",
    "SearchResults",
    "ChunkSearchResult",
    "SearchAlgorithm",
]
