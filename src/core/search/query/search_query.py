"""
Search query domain objects.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ...domain import Vector


class SearchAlgorithm(Enum):
    """Supported search algorithms."""

    COSINE = "cosine"
    HYBRID = "hybrid"

    @classmethod
    def from_string(cls, algorithm: str) -> "SearchAlgorithm":
        """Create SearchAlgorithm from string, case-insensitive."""
        algorithm_lower = algorithm.lower()
        for alg in cls:
            if alg.value == algorithm_lower:
                return alg

        valid_algorithms = [alg.value for alg in cls]
        raise ValueError(f"Invalid algorithm '{algorithm}'. Valid options: {valid_algorithms}")


@dataclass
class SearchQuery:
    """
    Represents a search query with all parameters.

    This is the main input object for search operations.
    """

    text: str
    algorithm: SearchAlgorithm
    limit: int
    embedding: Optional[Vector] = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Query text cannot be empty")

        if self.limit <= 0:
            raise ValueError("Limit must be positive")

        if self.limit > 1000:
            raise ValueError("Limit cannot exceed 1000 results")

    def has_embedding(self) -> bool:
        """Check if this query has a pre-computed embedding."""
        return self.embedding is not None

    def get_algorithm_name(self) -> str:
        """Get the algorithm name as a string."""
        return self.algorithm.value
