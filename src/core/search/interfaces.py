"""
Abstract interfaces for search functionality.

Defines the contracts that search algorithms and engines must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain import Chunk, Library, Vector
from .query import ChunkSearchResult, SearchQuery, SearchResults


class ISearchAlgorithm(ABC):
    """
    Abstract interface for search algorithms.

    Search algorithms take a query vector and a list of chunks,
    and return ranked search results.
    """

    @abstractmethod
    def search(
        self, query_vector: Vector, chunks: List[Chunk], limit: int, query_text: Optional[str] = None
    ) -> List[ChunkSearchResult]:
        """
        Search for relevant chunks using this algorithm.

        Args:
            query_vector: The vector representation of the search query
            chunks: List of chunks to search through (must have embeddings)
            limit: Maximum number of results to return
            query_text: Optional original query text (needed by hybrid algorithms)

        Returns:
            List of ChunkSearchResult objects, ranked by relevance
        """
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        pass


class ILibrarySearchEngine(ABC):
    """
    Abstract interface for library-level search operations.

    The search engine orchestrates the entire search process across
    a user's document library.
    """

    @abstractmethod
    async def search_library(self, library: Library, query: SearchQuery) -> SearchResults:
        """
        Search across all documents in a library.

        Args:
            library: The user's document library to search
            query: The search query with parameters

        Returns:
            SearchResults containing ranked chunks and metadata
        """
        pass

    @abstractmethod
    def get_supported_algorithms(self) -> List[str]:
        pass


class IEmbeddingService(ABC):
    """
    Abstract interface for generating embeddings from text.

    Used to convert query text into vector embeddings for similarity search.
    """

    @abstractmethod
    async def generate_embedding(self, text: str) -> Vector:
        """
        Generate a vector embedding for the given text.

        Args:
            text: The text to generate an embedding for

        Returns:
            Vector embedding of the text
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        pass


class ILibraryRepository(ABC):
    """
    Abstract interface for loading user libraries from storage.

    Handles the data access layer for retrieving documents and chunks.
    """

    @abstractmethod
    async def load_library(self, library_id: str) -> Library:
        """
        Load a complete library with all documents and chunks.

        Args:
            library_id: The user email identifying the library

        Returns:
            Library object with all documents and chunks loaded
        """
        pass

    @abstractmethod
    async def library_exists(self, library_id: str) -> bool:
        """
        Check if a library exists for the given user.

        Args:
            library_id: The user email identifying the library

        Returns:
            True if the library exists, False otherwise
        """
        pass
