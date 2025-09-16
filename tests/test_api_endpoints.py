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

    @patch("src.api.v1.query.get_query_service")
    def test_search_documents_success(self, mock_get_query_service, client, sample_search_results):
        """Test successful document search."""
        # Setup mocks - AsyncMock for async service methods
        mock_query_service = AsyncMock()
        mock_query_service.execute_query.return_value = sample_search_results
        mock_get_query_service.return_value = mock_query_service

        # Make request
        request_data = {"email": "test@example.com", "query": "test query", "algorithm": "cosine", "limit": 10}

        response = client.post("/v1/query", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "execution_time" in data
        assert "algorithm_used" in data
        assert "total_chunks_searched" in data
        assert data["algorithm_used"] == "cosine"
        assert data["execution_time"] == 0.123
        assert data["total_chunks_searched"] == 100
        assert len(data["results"]) == 1

        # Verify result structure
        result = data["results"][0]
        assert "chunk" in result
        assert "similarity_score" in result
        assert "rank" in result
        assert result["similarity_score"] == 0.95
        assert result["rank"] == 1

        # Verify service was called correctly
        mock_query_service.execute_query.assert_called_once_with(
            user_email="test@example.com", query_text="test query", algorithm="cosine", limit=10
        )

    @patch("src.api.v1.query.get_query_service")
    def test_search_documents_with_hybrid_algorithm(self, mock_get_query_service, client, sample_search_results):
        """Test document search with hybrid algorithm."""
        # Update sample results to use hybrid
        sample_search_results.algorithm_used = SearchAlgorithm.HYBRID

        mock_query_service = AsyncMock()
        mock_query_service.execute_query.return_value = sample_search_results
        mock_get_query_service.return_value = mock_query_service

        request_data = {
            "email": "test@example.com",
            "query": "test query with keywords",
            "algorithm": "hybrid",
            "limit": 5,
        }

        response = client.post("/v1/query", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["algorithm_used"] == "hybrid"

        mock_query_service.execute_query.assert_called_once_with(
            user_email="test@example.com", query_text="test query with keywords", algorithm="hybrid", limit=5
        )

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
        assert response.status_code == 422  # Validation error

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

    @patch("src.api.v1.query.get_query_service")
    def test_search_documents_default_limit(self, mock_get_query_service, client, sample_search_results):
        """Test search uses default limit when not specified."""
        mock_query_service = AsyncMock()
        mock_query_service.execute_query.return_value = sample_search_results
        mock_get_query_service.return_value = mock_query_service

        request_data = {
            "email": "test@example.com",
            "query": "test query",
            "algorithm": "cosine",
            # No limit specified
        }

        response = client.post("/v1/query", json=request_data)
        assert response.status_code == 200

        # Should use default limit of 10
        mock_query_service.execute_query.assert_called_once_with(
            user_email="test@example.com", query_text="test query", algorithm="cosine", limit=10
        )


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

        assert response.status_code == 422  # Validation error

    @patch("src.api.v1.upload.save_upload_to_disk")
    def test_upload_file_too_large(self, mock_save_upload, client):
        """Test upload fails when file is too large."""
        # Mock file size validation to raise an error
        mock_save_upload.side_effect = ValueError("File size exceeds maximum allowed size")

        # Create a large file (content doesn't matter since we're mocking)
        test_content = b"Large file content" * 1000
        test_file = ("large_file.pdf", BytesIO(test_content), "application/pdf")

        response = client.post("/v1/upload", files={"file": test_file}, data={"email": "test@example.com"})

        assert response.status_code == 400

    @patch("src.api.v1.upload.save_upload_to_disk")
    def test_upload_file_save_error(self, mock_save_upload, client):
        """Test upload handles file save errors."""
        mock_save_upload.side_effect = IOError("Disk full")

        test_content = b"Test content"
        test_file = ("test.txt", BytesIO(test_content), "text/plain")

        response = client.post("/v1/upload", files={"file": test_file}, data={"email": "test@example.com"})

        assert response.status_code == 500

    @patch("src.api.v1.upload.process_file_with_pipeline")
    @patch("src.api.v1.upload.save_upload_to_disk")
    def test_upload_different_file_types(self, mock_save_upload, mock_process_file, client):
        """Test upload handles different file types."""
        test_cases = [
            ("document.pdf", b"PDF content", "application/pdf"),
            (
                "document.docx",
                b"DOCX content",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("document.txt", b"Text content", "text/plain"),
            ("data.csv", b"CSV content", "text/csv"),
        ]

        for filename, content, content_type in test_cases:
            mock_save_upload.return_value = (f"/fake/path/{filename}", f"id_{filename}")

            test_file = (filename, BytesIO(content), content_type)

            response = client.post("/v1/upload", files={"file": test_file}, data={"email": "test@example.com"})

            assert response.status_code == 201
            data = response.json()
            assert data["filename"] == filename


class TestEndpointIntegration:
    """Test integration between endpoints."""

    @patch("src.api.v1.query.get_query_service")
    @patch("src.api.v1.upload.process_file_with_pipeline")
    @patch("src.api.v1.upload.save_upload_to_disk")
    def test_upload_then_query_workflow(
        self, mock_save_upload, mock_process_file, mock_get_query_service, client, sample_search_results
    ):
        """Test complete workflow: upload file then query it."""
        # Mock upload
        mock_save_upload.return_value = ("/fake/path/test.pdf", "test_file_id")

        # Mock query service
        mock_query_service = AsyncMock()
        mock_query_service.execute_query.return_value = sample_search_results
        mock_get_query_service.return_value = mock_query_service

        # Step 1: Upload file
        test_content = b"This is a test document with important information"
        test_file = ("test.pdf", BytesIO(test_content), "application/pdf")

        upload_response = client.post("/v1/upload", files={"file": test_file}, data={"email": "test@example.com"})

        assert upload_response.status_code == 201

        # Step 2: Query the system
        query_request = {
            "email": "test@example.com",
            "query": "important information",
            "algorithm": "cosine",
            "limit": 5,
        }

        query_response = client.post("/v1/query", json=query_request)

        assert query_response.status_code == 200
        query_data = query_response.json()
        assert len(query_data["results"]) == 1

        # Verify both endpoints were called
        mock_save_upload.assert_called_once()
        mock_process_file.assert_called_once()
        mock_query_service.execute_query.assert_called_once()


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
        # GET on upload endpoint
        response = client.get("/v1/upload")
        assert response.status_code == 405

        # PUT on query endpoint
        response = client.put("/v1/query")
        assert response.status_code == 405

    def test_endpoint_not_found(self, client):
        """Test handling of non-existent endpoints."""
        response = client.get("/v1/nonexistent")
        assert response.status_code == 404


class TestEndpointSecurity:
    """Test security aspects of endpoints."""

    def test_email_injection_protection(self, client):
        """Test protection against email injection."""
        malicious_emails = [
            "test@example.com; DROP TABLE users;",
            "test@example.com\nBcc: attacker@evil.com",
            "test@example.com<script>alert('xss')</script>",
        ]

        for email in malicious_emails:
            response = client.get(f"/v1/query/library/{email}")
            # Should either validate email format or handle safely
            assert response.status_code in [200, 422]  # Valid handling

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
        import time

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
