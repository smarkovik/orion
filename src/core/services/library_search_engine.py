"""
Main search engine for library-level search operations.
"""

import time
from typing import Dict, List

from ..domain import Library
from ..search.algorithms import CosineSearchAlgorithm, HybridSearchAlgorithm
from ..search.interfaces import IEmbeddingService, ILibrarySearchEngine, ISearchAlgorithm
from ..search.query import SearchAlgorithm, SearchQuery, SearchResults


class LibrarySearchEngine(ILibrarySearchEngine):
    """
    Main search engine that orchestrates search across a user's library.

    Supports multiple search algorithms and handles the complete search workflow.
    """

    def __init__(self, embedding_service: IEmbeddingService):
        self.embedding_service = embedding_service

        self.algorithms: Dict[SearchAlgorithm, ISearchAlgorithm] = {
            SearchAlgorithm.COSINE: CosineSearchAlgorithm(),
            SearchAlgorithm.HYBRID: HybridSearchAlgorithm(),
        }

    async def search_library(self, library: Library, query: SearchQuery) -> SearchResults:
        """
        Search across all documents in a library.

        Args:
            library: The user's document library to search
            query: The search query with parameters

        Returns:
            SearchResults containing ranked chunks and metadata
        """
        start_time = time.time()

        try:
            if not library.has_documents_with_embeddings():
                return self._create_empty_results(library, query, start_time)

            if not query.has_embedding():
                query.embedding = await self.embedding_service.generate_embedding(query.text)

            chunks_with_embeddings = library.get_chunks_with_embeddings()

            if not chunks_with_embeddings:
                return self._create_empty_results(library, query, start_time)

            algorithm = self.algorithms.get(query.algorithm)
            if not algorithm:
                raise ValueError(f"Unsupported search algorithm: {query.algorithm}")

            if query.embedding is None:
                raise ValueError("Query embedding is required for search")

            search_results = algorithm.search(
                query_vector=query.embedding,
                chunks=chunks_with_embeddings,
                limit=query.limit,
                query_text=query.text,
            )
            execution_time = time.time() - start_time
            return SearchResults(
                results=search_results,
                algorithm_used=query.algorithm,
                execution_time=execution_time,
                total_chunks_searched=len(chunks_with_embeddings),
                library_id=library.id,
                query_text=query.text,
            )

        except Exception as e:
            # Log error and re-raise
            print(f"Search error: {str(e)}")
            raise

    def get_supported_algorithms(self) -> List[str]:
        return [algorithm.value for algorithm in self.algorithms.keys()]

    def _create_empty_results(self, library: Library, query: SearchQuery, start_time: float) -> SearchResults:
        execution_time = time.time() - start_time

        return SearchResults(
            results=[],
            algorithm_used=query.algorithm,
            execution_time=execution_time,
            total_chunks_searched=0,
            library_id=library.id,
            query_text=query.text,
        )
