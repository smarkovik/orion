"""
Search result domain objects.
"""

from dataclasses import dataclass
from typing import List

from ...domain import Chunk, LibraryId
from .search_query import SearchAlgorithm


@dataclass
class ChunkSearchResult:
    """
    Represents a single chunk search result with relevance score.

    Contains the chunk and its computed relevance to the search query.
    """

    chunk: Chunk
    similarity_score: float
    rank: int

    def __post_init__(self):
        if self.similarity_score < 0.0 or self.similarity_score > 1.0:
            raise ValueError(f"Similarity score must be between 0.0 and 1.0, got {self.similarity_score}")

        if self.rank < 1:
            raise ValueError(f"Rank must be positive, got {self.rank}")

    def get_chunk_filename(self) -> str:
        return self.chunk.filename

    def get_chunk_text(self) -> str:
        return self.chunk.text

    def get_document_id(self) -> str:
        return str(self.chunk.document_id)

    def get_chunk_sequence(self) -> int:
        return self.chunk.sequence_index


@dataclass
class SearchResults:
    """
    Complete search results with metadata.

    Contains all search results along with execution metadata
    and statistics about the search operation.
    """

    results: List[ChunkSearchResult]
    algorithm_used: SearchAlgorithm
    execution_time: float
    total_chunks_searched: int
    library_id: LibraryId
    query_text: str

    def __post_init__(self):
        if self.execution_time < 0:
            raise ValueError("Execution time cannot be negative")

        if self.total_chunks_searched < 0:
            raise ValueError("Total chunks searched cannot be negative")

        for i, result in enumerate(self.results):
            expected_rank = i + 1
            if result.rank != expected_rank:
                raise ValueError(f"Result at index {i} has rank {result.rank}, expected {expected_rank}")

    def get_result_count(self) -> int:
        return len(self.results)

    def get_top_result(self) -> ChunkSearchResult:
        if not self.results:
            raise ValueError("No results available")
        return self.results[0]

    def get_algorithm_name(self) -> str:
        return self.algorithm_used.value

    def get_average_similarity(self) -> float:
        if not self.results:
            return 0.0

        total_similarity = sum(result.similarity_score for result in self.results)
        return total_similarity / len(self.results)

    def get_results_above_threshold(self, threshold: float) -> List[ChunkSearchResult]:
        return [result for result in self.results if result.similarity_score >= threshold]
