"""
Query-related domain objects for search functionality.
"""

from .search_query import SearchAlgorithm, SearchQuery
from .search_result import ChunkSearchResult, SearchResults

__all__ = [
    "SearchQuery",
    "SearchAlgorithm",
    "ChunkSearchResult",
    "SearchResults",
]
