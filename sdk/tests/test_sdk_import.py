"""
Basic import tests for the Orion SDK.

These tests verify that the SDK modules can be imported correctly
and that the basic structure is in place.
"""

import pytest


def test_main_imports():
    """Test that main SDK components can be imported."""
    from orion_sdk import (
        Document,
        LibraryStats,
        OrionClient,
        OrionConfig,
        OrionSDKError,
        QueryError,
        QueryResult,
        SearchResponse,
        ValidationError,
    )

    # Basic smoke test - just verify imports work
    assert OrionClient is not None
    assert OrionConfig is not None
    assert OrionSDKError is not None
    assert Document is not None


def test_client_initialization():
    """Test that the client can be initialized with default settings."""
    from orion_sdk import OrionClient

    client = OrionClient()
    assert client.base_url == "http://localhost:8000"
    assert client.timeout == 30

    # Test custom settings
    client = OrionClient(base_url="http://example.com:9000", timeout=60)
    assert client.base_url == "http://example.com:9000"
    assert client.timeout == 60

    client.close()


def test_config_object():
    """Test the configuration object."""
    from orion_sdk import OrionConfig

    config = OrionConfig()
    assert config.base_url == "http://localhost:8000"
    assert config.timeout == 30
    assert config.max_file_size == 50 * 1024 * 1024  # 50MB

    # Test URL normalization
    config = OrionConfig(base_url="http://example.com/")
    assert config.base_url == "http://example.com"  # Trailing slash removed


def test_exception_hierarchy():
    """Test the exception hierarchy."""
    from orion_sdk.exceptions import (
        APIError,
        DocumentUploadError,
        NetworkError,
        OrionSDKError,
        QueryError,
        ValidationError,
    )

    # Test inheritance
    assert issubclass(ValidationError, OrionSDKError)
    assert issubclass(DocumentUploadError, OrionSDKError)
    assert issubclass(QueryError, OrionSDKError)
    assert issubclass(APIError, OrionSDKError)
    assert issubclass(NetworkError, OrionSDKError)


def test_model_classes():
    """Test that model classes can be instantiated."""
    from datetime import datetime

    from orion_sdk.models import Document, LibraryStats, ProcessingStatus, QueryResult, SearchResponse

    # Test Document
    doc = Document(
        id="test-id",
        filename="test.pdf",
        user_email="test@example.com",
        file_size=1024,
        content_type="application/pdf",
        upload_timestamp=datetime.now(),
        processing_status=ProcessingStatus.PENDING,
    )
    assert doc.id == "test-id"
    assert not doc.is_processed
    assert not doc.has_error
    assert doc.is_processing

    # Test QueryResult
    result = QueryResult(
        text="Sample text",
        similarity_score=0.85,
        document_id="doc-id",
        original_filename="doc.pdf",
        chunk_index=0,
        rank=1,
        chunk_filename="doc_chunk_000.txt",
    )
    assert result.similarity_score == 0.85
    assert result.rank == 1

    # Test LibraryStats
    stats = LibraryStats(
        exists=True,
        document_count=5,
        chunk_count=50,
        chunks_with_embeddings=45,
        total_file_size=1024 * 1024 * 10,  # 10MB
    )
    assert stats.document_count == 5
    assert stats.total_file_size_mb == 10.0
    assert stats.embedding_coverage == 90.0


def test_validator_classes():
    """Test that validator classes work correctly."""
    from orion_sdk.utils.validators import EmailValidator, QueryValidator

    # Test email validation
    EmailValidator.validate_email("test@example.com")  # Should not raise

    with pytest.raises(Exception):  # Should raise ValidationError
        EmailValidator.validate_email("invalid-email")

    # Test query validation
    QueryValidator.validate_query("valid query")  # Should not raise

    with pytest.raises(Exception):  # Should raise ValidationError
        QueryValidator.validate_query("")


if __name__ == "__main__":
    # Run tests directly
    test_main_imports()
    test_client_initialization()
    test_config_object()
    test_exception_hierarchy()
    test_model_classes()
    test_validator_classes()
    print("✅ All import tests passed!")
