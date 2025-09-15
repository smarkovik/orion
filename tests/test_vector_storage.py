"""Tests for vector storage implementations."""

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from src.core.storage import (
    HDF5VectorStorage,
    JSONVectorStorage,
    StorageFactory,
    VectorStorage,
)


class TestJSONVectorStorage:
    """Test JSON vector storage implementation."""

    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage path.

        Given: A need for isolated test storage
        When: Tests are run
        Then: A temporary directory is provided and cleaned up
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_embeddings_data(self):
        """Create sample embeddings data for testing.

        Given: A need for test embeddings data
        When: Tests require embeddings
        Then: Consistent sample data is provided
        """
        return [
            {
                "filename": "chunk_001.txt",
                "text": "This is the first chunk of text.",
                "token_count": 8,
                "embedding": [0.1, 0.2, 0.3],
                "embedding_model": "embed-english-v3.0",
            },
            {
                "filename": "chunk_002.txt",
                "text": "This is the second chunk of text.",
                "token_count": 9,
                "embedding": [0.4, 0.5, 0.6],
                "embedding_model": "embed-english-v3.0",
            },
        ]

    def test_json_storage_save_and_load(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test saving and loading embeddings with JSON storage.

        Given: A JSON storage instance and sample embeddings data
        When: Data is saved and then loaded
        Then: The loaded data matches the original data
        """
        storage = JSONVectorStorage(temp_storage_path)
        file_id = "test_document_123"
        metadata = {"email": "test@example.com", "upload_time": "2024-01-01"}

        saved_path = storage.save_embeddings(file_id, sample_embeddings_data, metadata)

        assert saved_path.exists()
        assert saved_path.name == f"{file_id}_embeddings.json"

        loaded_data = storage.load_embeddings(file_id)

        assert len(loaded_data) == len(sample_embeddings_data)
        assert loaded_data == sample_embeddings_data

    def test_json_storage_file_structure(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test the structure of saved JSON files.

        Given: A JSON storage instance
        When: Embeddings are saved
        Then: The JSON file has the expected structure with metadata
        """
        storage = JSONVectorStorage(temp_storage_path)
        file_id = "test_structure"
        metadata = {"test_key": "test_value"}

        saved_path = storage.save_embeddings(file_id, sample_embeddings_data, metadata)

        with open(saved_path, "r") as f:
            raw_data = json.load(f)

        assert raw_data["file_id"] == file_id
        assert raw_data["embeddings"] == sample_embeddings_data
        assert raw_data["metadata"] == metadata
        assert raw_data["storage_format"] == "json"
        assert raw_data["embedding_count"] == len(sample_embeddings_data)

    def test_json_storage_exists_and_delete(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test existence check and deletion operations.

        Given: A JSON storage instance with saved embeddings
        When: Existence is checked and deletion is performed
        Then: Operations return expected results
        """
        storage = JSONVectorStorage(temp_storage_path)
        file_id = "test_delete"

        assert not storage.exists(file_id)

        storage.save_embeddings(file_id, sample_embeddings_data, {})

        assert storage.exists(file_id)

        assert storage.delete(file_id) is True
        assert not storage.exists(file_id)

        assert storage.delete(file_id) is False

    def test_json_storage_list_files(self, temp_storage_path, sample_embeddings_data):
        """Test listing stored files.

        Given: A JSON storage instance with multiple saved files
        When: List operation is called
        Then: All file IDs are returned in sorted order
        """
        storage = JSONVectorStorage(temp_storage_path)
        file_ids = ["doc_001", "doc_002", "doc_003"]

        for file_id in file_ids:
            storage.save_embeddings(file_id, sample_embeddings_data, {})

        listed_files = storage.list_files()

        assert len(listed_files) == len(file_ids)
        assert listed_files == sorted(file_ids)

    def test_json_storage_load_nonexistent_file(self, temp_storage_path):
        """Test loading from a non-existent file.

        Given: A JSON storage instance
        When: Loading is attempted for a non-existent file
        Then: FileNotFoundError is raised
        """
        storage = JSONVectorStorage(temp_storage_path)

        with pytest.raises(FileNotFoundError):
            storage.load_embeddings("nonexistent_file")

    def test_json_storage_get_metadata(self, temp_storage_path, sample_embeddings_data):
        """Test retrieving metadata for stored embeddings.

        Given: JSON storage with embeddings and metadata
        When: Metadata is requested
        Then: The correct metadata is returned
        """
        storage = JSONVectorStorage(temp_storage_path)
        file_id = "test_metadata"
        metadata = {"email": "user@example.com", "model": "test-model"}

        storage.save_embeddings(file_id, sample_embeddings_data, metadata)

        retrieved_metadata = storage.get_metadata(file_id)
        assert retrieved_metadata == metadata


class TestStorageFactory:
    """Test the storage factory implementation."""

    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage path.

        Given: A need for isolated test storage
        When: Tests are run
        Then: A temporary directory is provided and cleaned up
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_create_json_storage(self, temp_storage_path):
        """Test creating JSON storage through factory.

        Given: A storage factory
        When: JSON storage is requested
        Then: A JSONVectorStorage instance is returned
        """
        storage = StorageFactory.create_storage("json", temp_storage_path)

        assert isinstance(storage, JSONVectorStorage)
        assert storage.storage_path == temp_storage_path

    def test_create_hdf5_storage(self, temp_storage_path):
        """Test creating HDF5 storage through factory.

        Given: A storage factory
        When: HDF5 storage is requested
        Then: An HDF5VectorStorage instance is returned
        """
        storage = StorageFactory.create_storage("hdf5", temp_storage_path)

        assert isinstance(storage, HDF5VectorStorage)
        assert storage.storage_path == temp_storage_path


class TestHDF5VectorStorage:
    """Test HDF5 vector storage implementation."""

    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage path.

        Given: A need for isolated test storage
        When: Tests are run
        Then: A temporary directory is provided and cleaned up
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_embeddings_data(self):
        """Create sample embeddings data for testing.

        Given: A need for test embeddings data
        When: Tests require embeddings
        Then: Consistent sample data is provided
        """
        return [
            {
                "filename": "chunk_001.txt",
                "text": "This is the first chunk of text.",
                "token_count": 8,
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "embedding_model": "embed-english-v3.0",
            },
            {
                "filename": "chunk_002.txt",
                "text": "This is the second chunk of text.",
                "token_count": 9,
                "embedding": [0.5, 0.6, 0.7, 0.8],
                "embedding_model": "embed-english-v3.0",
            },
        ]

    def test_hdf5_storage_save_and_load(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test saving and loading embeddings with HDF5 storage.

        Given: An HDF5 storage instance and sample embeddings data
        When: Data is saved and then loaded
        Then: The loaded data matches the original data
        """
        storage = HDF5VectorStorage(temp_storage_path)
        file_id = "test_document_123"
        metadata = {"email": "test@example.com", "upload_time": "2024-01-01"}

        saved_path = storage.save_embeddings(file_id, sample_embeddings_data, metadata)

        assert saved_path.exists()
        assert saved_path.name == f"{file_id}_embeddings.h5"

        loaded_data = storage.load_embeddings(file_id)

        assert len(loaded_data) == len(sample_embeddings_data)
        for original, loaded in zip(sample_embeddings_data, loaded_data):
            assert loaded["filename"] == original["filename"]
            assert loaded["text"] == original["text"]
            assert loaded["token_count"] == original["token_count"]
            assert loaded["embedding_model"] == original["embedding_model"]
            # Check embeddings with some tolerance for float precision
            assert len(loaded["embedding"]) == len(original["embedding"])
            for orig_val, loaded_val in zip(original["embedding"], loaded["embedding"]):
                assert abs(orig_val - loaded_val) < 1e-6

    def test_hdf5_storage_exists_and_delete(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test existence check and deletion operations.

        Given: An HDF5 storage instance with saved embeddings
        When: Existence is checked and deletion is performed
        Then: Operations return expected results
        """
        storage = HDF5VectorStorage(temp_storage_path)
        file_id = "test_delete"

        assert not storage.exists(file_id)

        storage.save_embeddings(file_id, sample_embeddings_data, {})

        assert storage.exists(file_id)

        assert storage.delete(file_id) is True
        assert not storage.exists(file_id)

        assert storage.delete(file_id) is False

    def test_hdf5_storage_list_files(self, temp_storage_path, sample_embeddings_data):
        """Test listing stored files.

        Given: An HDF5 storage instance with multiple saved files
        When: List operation is called
        Then: All file IDs are returned in sorted order
        """
        storage = HDF5VectorStorage(temp_storage_path)
        file_ids = ["doc_001", "doc_002", "doc_003"]

        for file_id in file_ids:
            storage.save_embeddings(file_id, sample_embeddings_data, {})

        listed_files = storage.list_files()

        assert len(listed_files) == len(file_ids)
        assert listed_files == sorted(file_ids)

    def test_hdf5_storage_get_metadata(self, temp_storage_path, sample_embeddings_data):
        """Test retrieving metadata for stored embeddings.

        Given: HDF5 storage with embeddings and metadata
        When: Metadata is requested
        Then: The correct metadata is returned
        """
        storage = HDF5VectorStorage(temp_storage_path)
        file_id = "test_metadata"
        metadata = {"email": "user@example.com", "model": "test-model"}

        storage.save_embeddings(file_id, sample_embeddings_data, metadata)

        retrieved_metadata = storage.get_metadata(file_id)
        assert retrieved_metadata == metadata

    def test_hdf5_storage_get_embeddings_array(
        self, temp_storage_path, sample_embeddings_data
    ):
        """Test getting embeddings as numpy array.

        Given: HDF5 storage with saved embeddings
        When: Embeddings array is requested
        Then: A numpy array with correct shape and values is returned
        """
        import numpy as np

        storage = HDF5VectorStorage(temp_storage_path)
        file_id = "test_array"

        storage.save_embeddings(file_id, sample_embeddings_data, {})

        embeddings_array = storage.get_embeddings_array(file_id)

        assert isinstance(embeddings_array, np.ndarray)
        assert embeddings_array.shape == (2, 4)  # 2 embeddings, 4 dimensions each
        assert embeddings_array.dtype == np.float32

        expected = np.array(
            [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]], dtype=np.float32
        )
        np.testing.assert_array_almost_equal(embeddings_array, expected)
