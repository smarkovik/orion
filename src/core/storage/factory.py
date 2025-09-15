"""Factory for creating vector storage instances."""

from pathlib import Path
from typing import Dict, Type

from .base import VectorStorage
from .hdf5_storage import HDF5VectorStorage
from .json_storage import JSONVectorStorage


class StorageFactory:
    """Factory for creating appropriate storage instances."""

    # Registry of available storage implementations
    _storage_types: Dict[str, Type[VectorStorage]] = {
        "json": JSONVectorStorage,
        "hdf5": HDF5VectorStorage,
    }

    @classmethod
    def create_storage(self, storage_type: str, storage_path: Path) -> VectorStorage:
        """Create a storage instance of the specified type.

        Given: A storage type and path
        When: Storage creation is requested
        Then: Return appropriate storage implementation

        Args:
            storage_type: Type of storage ("json", "hdf5", etc.)
            storage_path: Base path for storage

        Returns:
            VectorStorage instance

        Raises:
            ValueError: If storage type is not supported
        """
        if storage_type not in self._storage_types:
            available_types = ", ".join(self._storage_types.keys())
            raise ValueError(f"Unsupported storage type '{storage_type}'. " f"Available types: {available_types}")

        storage_class = self._storage_types[storage_type]
        return storage_class(storage_path)

    @classmethod
    def register_storage(cls, storage_type: str, storage_class: Type[VectorStorage]) -> None:
        """Register a new storage implementation.

        Given: A storage type name and implementation class
        When: Registration is called
        Then: The new storage type becomes available

        Args:
            storage_type: Name for the storage type
            storage_class: Storage implementation class
        """
        cls._storage_types[storage_type] = storage_class

    @classmethod
    def available_storage_types(cls) -> list[str]:
        """Get list of available storage types.

        Returns:
            List of supported storage type names
        """
        return list(cls._storage_types.keys())
