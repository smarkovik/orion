"""
Main query service that orchestrates the complete query workflow.
"""

from typing import List

from ..search.interfaces import IEmbeddingService, ILibraryRepository, ILibrarySearchEngine
from ..search.query import SearchAlgorithm, SearchQuery, SearchResults


class QueryService:
    """
    Main service for executing search queries.

    Orchestrates the complete query workflow from request to response.
    """

    def __init__(
        self,
        library_repository: ILibraryRepository,
        search_engine: ILibrarySearchEngine,
        embedding_service: IEmbeddingService,
    ):
        self.library_repository = library_repository
        self.search_engine = search_engine
        self.embedding_service = embedding_service

    async def execute_query(self, user_email: str, query_text: str, algorithm: str, limit: int = 10) -> SearchResults:
        """
        Execute a search query against a user's document library.

        Args:
            user_email: Email identifying the user's library
            query_text: The search query text
            algorithm: Search algorithm to use ("cosine" or "hybrid")
            limit: Maximum number of results to return

        Returns:
            SearchResults containing ranked chunks and metadata
        """
        if not user_email.strip():
            raise ValueError("User email cannot be empty")

        if not query_text.strip():
            raise ValueError("Query text cannot be empty")

        if limit <= 0:
            raise ValueError("Limit must be positive")

        if not await self.library_repository.library_exists(user_email):
            raise ValueError(f"No library found for user: {user_email}")

        try:
            search_algorithm = SearchAlgorithm.from_string(algorithm)
        except ValueError as e:
            raise ValueError(f"Invalid algorithm: {str(e)}")
        search_query = SearchQuery(text=query_text, algorithm=search_algorithm, limit=limit)
        library = await self.library_repository.load_library(user_email)
        results = await self.search_engine.search_library(library, search_query)
        return results

    def get_supported_algorithms(self) -> List[str]:
        return self.search_engine.get_supported_algorithms()

    async def get_library_stats(self, user_email: str) -> dict:
        if not await self.library_repository.library_exists(user_email):
            return {"exists": False, "document_count": 0, "chunk_count": 0, "chunks_with_embeddings": 0}

        library = await self.library_repository.load_library(user_email)

        return {
            "exists": True,
            "document_count": library.get_document_count(),
            "chunk_count": library.get_total_chunk_count(),
            "chunks_with_embeddings": len(library.get_chunks_with_embeddings()),
            "total_file_size": library.get_total_file_size(),
        }
