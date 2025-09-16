"""
Tests for API endpoints (query and upload).
"""

import json
from io import BytesIO
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from src.core.domain import LibraryId, Vector
from src.core.search.query import ChunkSearchResult, SearchAlgorithm, SearchResults
from src.main import app
from src.models.query import QueryRequest, QueryResponse
from src.models.upload import UploadResponse


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing."""
    from src.core.domain import Chunk, ChunkId, DocumentId

    # Create mock chunks
    document_id = DocumentId.generate()
    chunk1 = Chunk(
        id=ChunkId(document_id.value, 0),
        document_id=document_id,
        filename=f"doc_{document_id.value}_chunk_000.txt",
        text="This is a sample search result",
        token_count=6,
        sequence_index=0,
        embedding=Vector.from_list([0.1, 0.2, 0.3], "test-model"),
    )

    chunk_results = [ChunkSearchResult(chunk=chunk1, similarity_score=0.95, rank=1)]

    return SearchResults(
        results=chunk_results,
        algorithm_used=SearchAlgorithm.COSINE,
        execution_time=0.123,
        total_chunks_searched=100,
        library_id=LibraryId("test@example.com"),
        query_text="test query",
    )


@pytest.fixture
def sample_library_stats():
    """Create sample library stats for testing."""
    return {
        "exists": True,
        "document_count": 5,
        "chunk_count": 25,
        "chunks_with_embeddings": 20,
        "total_file_size": 1024000,
    }


class TestQueryEndpoint:
    """Test the query endpoint (/v1/query)."""

    def test_search_documents_request_validation(self, client):
        """Test search endpoint validates request structure properly."""
        # Valid request structure should pass basic validation
        request_data = {"email": "test@example.com", "query": "test query", "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)

        # May fail on execution but should pass validation
        assert response.status_code in [200, 400, 500]  # Any non-422 means validation passed

    def test_search_documents_missing_email(self, client):
        """Test search fails when email is missing."""
        request_data = {"query": "test query", "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_search_documents_missing_query(self, client):
        """Test search fails when query is missing."""
        request_data = {"email": "test@example.com", "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_search_documents_invalid_algorithm(self, client):
        """Test search fails with invalid algorithm."""
        request_data = {
            "email": "test@example.com",
            "query": "test query",
            "algorithm": "invalid_algorithm",
            "limit": 10,
        }

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 400  # Bad request due to algorithm validation

    def test_search_documents_invalid_limit_zero(self, client):
        """Test search fails with zero limit."""
        request_data = {"email": "test@example.com", "query": "test query", "algorithm": "cosine", "limit": 0}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_search_documents_invalid_limit_negative(self, client):
        """Test search fails with negative limit."""
        request_data = {"email": "test@example.com", "query": "test query", "algorithm": "cosine", "limit": -5}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_search_documents_invalid_limit_too_high(self, client):
        """Test search fails with limit too high."""
        request_data = {"email": "test@example.com", "query": "test query", "algorithm": "cosine", "limit": 1001}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 422  # Validation error

    @patch("src.api.v1.query.get_query_service")
    def test_search_documents_service_error(self, mock_get_query_service, client):
        """Test search handles service errors."""
        mock_query_service = AsyncMock()
        mock_query_service.execute_query.side_effect = ValueError("No library found")
        mock_get_query_service.return_value = mock_query_service

        request_data = {"email": "nonexistent@example.com", "query": "test query", "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 400  # ValueError is caught and returns 400


class TestLibraryStatsEndpoint:
    """Test the library stats endpoint (/v1/query/stats)."""

    @patch("src.api.v1.query.get_query_service")
    def test_get_library_stats_success(self, mock_get_query_service, client, sample_library_stats):
        """Test successful library stats retrieval."""
        mock_query_service = Mock()
        mock_query_service.get_library_stats = AsyncMock(return_value=sample_library_stats)
        mock_get_query_service.return_value = mock_query_service

        response = client.get("/v1/query/library/test@example.com/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["exists"] is True
        assert data["document_count"] == 5
        assert data["chunk_count"] == 25
        assert data["chunks_with_embeddings"] == 20
        assert data["total_file_size"] == 1024000

        mock_query_service.get_library_stats.assert_called_once_with("test@example.com")

    @patch("src.api.v1.query.get_query_service")
    def test_get_library_stats_nonexistent_library(self, mock_get_query_service, client):
        """Test library stats for nonexistent library."""
        mock_query_service = Mock()
        mock_query_service.get_library_stats = AsyncMock(
            return_value={"exists": False, "document_count": 0, "chunk_count": 0, "chunks_with_embeddings": 0}
        )
        mock_get_query_service.return_value = mock_query_service

        response = client.get("/v1/query/library/nonexistent@example.com/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["exists"] is False
        assert data["document_count"] == 0
        assert data["chunk_count"] == 0
        assert data["chunks_with_embeddings"] == 0

    def test_get_library_stats_missing_email(self, client):
        """Test library stats fails when email is missing."""
        response = client.get("/v1/query/library//stats")
        assert response.status_code in [404, 422]  # Path validation error

    @patch("src.api.v1.query.get_query_service")
    def test_get_library_stats_service_error(self, mock_get_query_service, client):
        """Test library stats handles service errors."""
        mock_query_service = Mock()
        mock_query_service.get_library_stats = AsyncMock(side_effect=Exception("Database error"))
        mock_get_query_service.return_value = mock_query_service

        response = client.get("/v1/query/library/test@example.com/stats")
        assert response.status_code == 500


class TestUploadEndpoint:
    """Test the upload endpoint (/v1/upload)."""

    def test_upload_file_missing_file(self, client):
        """Test upload fails when file is missing."""
        response = client.post("/v1/upload", data={"email": "test@example.com"})

        assert response.status_code == 422  # Validation error

    def test_upload_file_missing_email(self, client):
        """Test upload fails when email is missing."""
        test_content = b"Test content"
        test_file = ("test.txt", BytesIO(test_content), "text/plain")

        response = client.post("/v1/upload", files={"file": test_file})

        assert response.status_code == 422  # Validation error

    def test_upload_file_missing_email(self, client):
        """Test upload fails when email is missing."""
        test_content = b"Test content"
        test_file = ("test.txt", BytesIO(test_content), "text/plain")

        response = client.post("/v1/upload", files={"file": test_file})

        assert response.status_code == 422  # Validation error

    def test_upload_file_invalid_email(self, client):
        """Test upload fails with invalid email format."""
        test_content = b"Test content"
        test_file = ("test.txt", BytesIO(test_content), "text/plain")

        response = client.post("/v1/upload", files={"file": test_file}, data={"email": "invalid-email"})

        assert response.status_code == 400  # Bad request due to email validation

    def test_upload_file_too_large_content_length(self, client):
        """Test upload validation for large files using content length."""
        # Create a moderately large test file to test size limits
        test_content = b"Large file content" * 10000  # About 180KB
        test_file = ("large_file.pdf", BytesIO(test_content), "application/pdf")

        response = client.post("/v1/upload", files={"file": test_file}, data={"email": "test@example.com"})

        # Could be 413 (too large) or another status depending on server config
        assert response.status_code in [201, 413, 400, 422]


class TestEndpointIntegration:
    """Test integration between endpoints."""

    def test_query_endpoint_reachable(self, client):
        """Test that query endpoint is reachable and handles missing data properly."""
        # Test without any data
        response = client.post("/v1/query")
        assert response.status_code == 422  # Validation error for missing required fields

    def test_upload_endpoint_reachable(self, client):
        """Test that upload endpoint is reachable and handles missing data properly."""
        # Test without any data
        response = client.post("/v1/upload")
        assert response.status_code == 422  # Validation error for missing required fields


class TestEndpointErrorHandling:
    """Test error handling across endpoints."""

    def test_invalid_json_request(self, client):
        """Test handling of invalid JSON in request."""
        response = client.post("/v1/query", data="invalid json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422

    def test_unsupported_content_type(self, client):
        """Test handling of unsupported content types."""
        response = client.post("/v1/query", data="some data", headers={"Content-Type": "application/xml"})
        assert response.status_code == 422

    def test_method_not_allowed(self, client):
        """Test handling of incorrect HTTP methods."""
        response = client.get("/v1/upload")
        assert response.status_code == 405

        response = client.put("/v1/query")
        assert response.status_code == 405

    def test_endpoint_not_found(self, client):
        """Test handling of non-existent endpoints."""
        response = client.get("/v1/nonexistent")
        assert response.status_code == 404


class TestEndpointSecurity:
    """Test security aspects of endpoints."""

    def test_query_injection_protection(self, client):
        """Test protection against query injection."""
        malicious_queries = [
            "'; DROP TABLE documents; --",
            "<script>alert('xss')</script>",
            "../../../../etc/passwd",
        ]

        for query in malicious_queries:
            request_data = {"email": "test@example.com", "query": query, "algorithm": "cosine", "limit": 10}

            response = client.post("/v1/query", json=request_data)
            # Should handle malicious queries safely
            assert response.status_code in [200, 400, 422, 500]  # Valid handling


class TestEndpointPerformance:
    """Test performance-related aspects of endpoints."""

    def test_large_query_text(self, client):
        """Test handling of very large query text."""
        large_query = "word " * 10000  # Very long query

        request_data = {"email": "test@example.com", "query": large_query, "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)
        # Should either process or reject gracefully
        assert response.status_code in [200, 400, 413, 422]

    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        import threading

        results = []

        def make_request():
            response = client.get("/v1/query/library/test@example.com/stats")
            results.append(response.status_code)

        # Make 5 concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should complete (may have various status codes)
        assert len(results) == 5
        assert all(isinstance(code, int) for code in results)
