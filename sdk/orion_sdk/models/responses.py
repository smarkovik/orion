"""
Response data models.
"""

from dataclasses import dataclass


@dataclass
class LibraryStats:
    """Statistics about a user's document library."""

    exists: bool
    document_count: int
    chunk_count: int
    chunks_with_embeddings: int
    total_file_size: int

    @classmethod
    def from_api_response(cls, data: dict) -> "LibraryStats":
        return cls(
            exists=data["exists"],
            document_count=data["document_count"],
            chunk_count=data["chunk_count"],
            chunks_with_embeddings=data["chunks_with_embeddings"],
            total_file_size=data["total_file_size"],
        )

    @property
    def total_file_size_mb(self) -> float:
        return self.total_file_size / (1024 * 1024)

    @property
    def avg_chunks_per_document(self) -> float:
        if self.document_count == 0:
            return 0.0
        return self.chunk_count / self.document_count

    @property
    def embedding_coverage(self) -> float:
        """Get percentage of chunks that have embeddings."""
        if self.chunk_count == 0:
            return 0.0
        return (self.chunks_with_embeddings / self.chunk_count) * 100

    def __str__(self) -> str:
        if not self.exists:
            return "LibraryStats(library does not exist)"

        return (
            f"LibraryStats(docs={self.document_count}, "
            f"chunks={self.chunk_count}, "
            f"embeddings={self.chunks_with_embeddings}, "
            f"size={self.total_file_size_mb:.1f}MB)"
        )

    def __repr__(self) -> str:
        return self.__str__()
