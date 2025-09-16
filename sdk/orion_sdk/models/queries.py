"""
Query-related data models.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class QueryResult:
    """Represents a single search result chunk."""

    text: str
    similarity_score: float
    document_id: str
    original_filename: str
    chunk_index: int
    rank: int
    chunk_filename: str

    @classmethod
    def from_api_response(cls, data: dict) -> "QueryResult":
        return cls(
            text=data["text"],
            similarity_score=data["similarity_score"],
            document_id=data["document_id"],
            original_filename=data["original_filename"],
            chunk_index=data["chunk_index"],
            rank=data["rank"],
            chunk_filename=data["chunk_filename"],
        )

    def __str__(self) -> str:
        return f"QueryResult(rank={self.rank}, score={self.similarity_score:.3f}, text={self.text[:50]}...)"

    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class SearchResponse:

    results: List[QueryResult]
    algorithm_used: str
    total_documents_searched: int
    total_chunks_searched: int
    execution_time: float
    query_text: str

    @classmethod
    def from_api_response(cls, data: dict) -> "SearchResponse":
        results = [QueryResult.from_api_response(result) for result in data["results"]]

        return cls(
            results=results,
            algorithm_used=data["algorithm_used"],
            total_documents_searched=data["total_documents_searched"],
            total_chunks_searched=data["total_chunks_searched"],
            execution_time=data["execution_time"],
            query_text=data["query_text"],
        )

    @property
    def result_count(self) -> int:
        return len(self.results)

    def get_top_results(self, n: int = 5) -> List[QueryResult]:
        """Get the top N results by rank."""
        return sorted(self.results, key=lambda x: x.rank)[:n]

    def __str__(self) -> str:
        return (
            f"SearchResponse(query='{self.query_text}', results={len(self.results)}, time={self.execution_time:.3f}s)"
        )

    def __repr__(self) -> str:
        return self.__str__()
