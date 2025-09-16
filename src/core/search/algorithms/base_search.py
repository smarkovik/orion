"""
Base class for search algorithms.
"""

from abc import ABC
from typing import List

from ...domain import Chunk, Vector
from ..interfaces import ISearchAlgorithm
from ..query import ChunkSearchResult


class BaseSearchAlgorithm(ISearchAlgorithm, ABC):
    """
    Base implementation for search algorithms.

    Provides common functionality like result ranking and validation.
    """

    def _validate_inputs(self, query_vector: Vector, chunks: List[Chunk], limit: int) -> None:
        """Validate search inputs."""
        if limit <= 0:
            raise ValueError("Limit must be positive")

        if not chunks:
            raise ValueError("Chunks list cannot be empty")

        # Check that all chunks have embeddings
        chunks_without_embeddings = [chunk for chunk in chunks if not chunk.has_embedding()]
        if chunks_without_embeddings:
            raise ValueError(f"Found {len(chunks_without_embeddings)} chunks without embeddings")

        # Check embedding dimensions match
        first_chunk_dimension = chunks[0].get_embedding_dimension()
        if query_vector.dimension != first_chunk_dimension:
            raise ValueError(
                f"Query vector dimension ({query_vector.dimension}) does not match "
                f"chunk embedding dimension ({first_chunk_dimension})"
            )

    def _create_search_results(self, chunks: List[Chunk], scores: List[float], limit: int) -> List[ChunkSearchResult]:
        """
        Create ranked search results from chunks and scores.

        Args:
            chunks: List of chunks (same order as scores)
            scores: List of similarity scores (same order as chunks)
            limit: Maximum number of results to return

        Returns:
            List of ChunkSearchResult objects, ranked by score (highest first)
        """
        if len(chunks) != len(scores):
            raise ValueError("Chunks and scores lists must have the same length")

        # Combine chunks with their scores
        chunk_score_pairs = list(zip(chunks, scores))

        # Sort by score in descending order (highest similarity first)
        chunk_score_pairs.sort(key=lambda x: x[1], reverse=True)

        # Create search results with ranks
        results = []
        for rank, (chunk, score) in enumerate(chunk_score_pairs[:limit], start=1):
            result = ChunkSearchResult(chunk=chunk, similarity_score=score, rank=rank)
            results.append(result)

        return results

    def _filter_valid_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Filter chunks to only include those with embeddings."""
        return [chunk for chunk in chunks if chunk.has_embedding()]
