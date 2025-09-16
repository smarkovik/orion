"""
Cosine similarity search algorithm.
"""

from typing import List, Optional

from ...domain import Chunk, Vector
from ..query import ChunkSearchResult
from .base_search import BaseSearchAlgorithm


class CosineSearchAlgorithm(BaseSearchAlgorithm):
    """
    Pure cosine similarity search algorithm.

    Computes cosine similarity between the query vector and each chunk's
    embedding vector, ranking results by similarity score.
    """

    def search(
        self, query_vector: Vector, chunks: List[Chunk], limit: int, query_text: Optional[str] = None
    ) -> List[ChunkSearchResult]:
        """
        Search using cosine similarity.

        Args:
            query_vector: The vector representation of the search query
            chunks: List of chunks to search through (must have embeddings)
            limit: Maximum number of results to return

        Returns:
            List of ChunkSearchResult objects, ranked by cosine similarity
        """
        # Validate inputs
        self._validate_inputs(query_vector, chunks, limit)

        # Filter to only chunks with embeddings (should be all of them after validation)
        valid_chunks = self._filter_valid_chunks(chunks)

        # Calculate cosine similarity for each chunk
        similarities = []
        for chunk in valid_chunks:
            assert chunk.embedding is not None  # Already validated in _filter_valid_chunks
            similarity = chunk.embedding.cosine_similarity(query_vector)
            similarities.append(similarity)

        # Create and return ranked results
        return self._create_search_results(valid_chunks, similarities, limit)

    def get_algorithm_name(self) -> str:
        """Get the name of this search algorithm."""
        return "cosine"
