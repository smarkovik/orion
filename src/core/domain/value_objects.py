"""
Value objects for the Orion domain model.

Value objects are immutable objects that represent concepts in the domain
that are defined by their attributes rather than their identity.
"""

import re
import uuid
from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class ChunkId:
    """Unique identifier for a text chunk within a document."""

    document_id: str
    sequence: int

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("Chunk sequence must be non-negative")

    def __str__(self) -> str:
        return f"{self.document_id}_chunk_{self.sequence:03d}"

    @classmethod
    def from_filename(cls, filename: str) -> "ChunkId":
        """Create ChunkId from chunk filename like 'document_chunk_001.txt'."""
        base_name = filename.replace(".txt", "")

        # Extract document_id and sequence from pattern: {document_id}_chunk_{sequence}
        match = re.match(r"^(.+)_chunk_(\d+)$", base_name)
        if not match:
            raise ValueError(f"Invalid chunk filename format: {filename}")

        document_id = match.group(1)
        sequence = int(match.group(2))

        return cls(document_id=document_id, sequence=sequence)


@dataclass(frozen=True)
class DocumentId:
    """Unique identifier for a document."""

    value: str

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.value)
        except ValueError:
            raise ValueError(f"DocumentId must be a valid UUID: {self.value}")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> "DocumentId":
        """Generate a new random DocumentId."""
        return cls(str(uuid.uuid4()))

    @classmethod
    def from_filename(cls, filename: str) -> "DocumentId":
        """Extract DocumentId from uploaded filename like 'uuid_originalname.ext'."""
        # Split on first underscore to separate UUID from original filename
        parts = filename.split("_", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid uploaded filename format: {filename}")

        uuid_part = parts[0]
        return cls(uuid_part)


@dataclass(frozen=True)
class LibraryId:
    """Unique identifier for a user's document library."""

    email: str

    def __post_init__(self) -> None:
        if not self._is_valid_email(self.email):
            raise ValueError(f"Invalid email format: {self.email}")

    def __str__(self) -> str:
        return self.email

    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


@dataclass(frozen=True)
class Vector:
    """Vector embedding representation with metadata."""

    values: List[float]
    dimension: int
    model: str

    def __post_init__(self) -> None:
        if len(self.values) != self.dimension:
            raise ValueError(f"Vector dimension mismatch: expected {self.dimension}, " f"got {len(self.values)}")

        if self.dimension <= 0:
            raise ValueError("Vector dimension must be positive")

    def cosine_similarity(self, other: "Vector") -> float:
        """Calculate cosine similarity with another vector."""
        if self.dimension != other.dimension:
            raise ValueError(
                f"Cannot compare vectors of different dimensions: " f"{self.dimension} vs {other.dimension}"
            )

        a = np.array(self.values)
        b = np.array(other.values)

        # Calculate cosine similarity: (a · b) / (||a|| * ||b||)
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def magnitude(self) -> float:
        """Calculate the magnitude (L2 norm) of the vector."""
        return float(np.linalg.norm(self.values))

    @classmethod
    def from_list(cls, values: List[float], model: str) -> "Vector":
        """Create Vector from a list of float values."""
        return cls(values=values, dimension=len(values), model=model)

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array for efficient operations."""
        return np.array(self.values)
