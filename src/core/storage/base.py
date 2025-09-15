"""Base storage interface for vector embeddings."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class VectorStorage(ABC):
    """Abstract base class for vector storage implementations."""

    def __init__(self, storage_path: Path):
        """Initialize storage with a base path.

        Args:
            storage_path: Base directory for storing vectors
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def save_embeddings(
        self,
        file_id: str,
        embeddings_data: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
    ) -> Path:
        """Save embeddings data to storage.

        Args:
            file_id: Unique identifier for the file
            embeddings_data: List of dictionaries containing embeddings and metadata
            metadata: Optional additional metadata about the file

        Returns:
            Path to the saved file
        """
        pass

    @abstractmethod
    def load_embeddings(self, file_id: str) -> List[Dict[str, Any]]:
        """Load embeddings data from storage.

        Args:
            file_id: Unique identifier for the file

        Returns:
            List of dictionaries containing embeddings and metadata

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        pass

    @abstractmethod
    def exists(self, file_id: str) -> bool:
        """Check if embeddings exist for a given file ID.

        Args:
            file_id: Unique identifier for the file

        Returns:
            True if embeddings exist, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Delete embeddings for a given file ID.

        Args:
            file_id: Unique identifier for the file

        Returns:
            True if deletion was successful, False if file didn't exist
        """
        pass

    @abstractmethod
    def list_files(self) -> List[str]:
        """List all stored file IDs.

        Returns:
            List of file IDs that have stored embeddings
        """
        pass
