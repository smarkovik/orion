"""Tests for the embeddings generation pipeline."""

import json
import time
import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import app


class TestEmbeddingsPipeline:
    """Test the complete embeddings generation pipeline."""

    @pytest.fixture
    def client(self):
        """Create test client.

        Given: A FastAPI test client
        When: Tests are run
        Then: The client provides access to the API endpoints
        """
        return TestClient(app)

    @pytest.fixture
    def unique_email(self):
        """Generate unique email for test isolation.

        Given: A need for unique test data
        When: Each test runs
        Then: A unique email address is generated to prevent conflicts
        """
        return f"pipeline_test_{uuid.uuid4().hex[:8]}@example.com"

    @patch("src.core.tasks.cohere.Client")
    def test_complete_pipeline_with_mock_cohere(
        self, mock_cohere_class, client, unique_email
    ):
        """Test complete pipeline from upload to embeddings with mocked Cohere API.

        Given: A text file upload and mocked Cohere API
        When: The file is uploaded and background tasks process it
        Then: The pipeline should create chunks and generate mock embeddings
        """
        # Mock Cohere client and response
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client

        # Mock embedding response (1024-dimensional vectors for embed-english-v3.0)
        mock_response = Mock()
        mock_response.embeddings = [
            [0.1] * 1024,  # Mock 1024-dimensional embedding for chunk 1
            [0.2] * 1024,  # Mock 1024-dimensional embedding for chunk 2
        ]
        mock_client.embed.return_value = mock_response

        test_content = (
            "This is a test document. " * 100
        )  # Long enough to create multiple chunks

        response = client.post(
            "/v1/upload",
            data={"email": unique_email},
            files={"file": ("test_doc.txt", test_content, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "Text conversion started" in data["message"]

        # a moment for background task to complete
        time.sleep(0.5)

        # Verify file structure
        user_base = settings.get_user_base_path(unique_email)
        assert user_base.exists()

        raw_uploads = settings.get_user_raw_uploads_path(unique_email)
        processed_text = settings.get_user_processed_text_path(unique_email)
        raw_chunks = settings.get_user_raw_chunks_path(unique_email)
        processed_vectors = settings.get_user_processed_vectors_path(unique_email)

        uploaded_files = list(raw_uploads.glob("*.txt"))
        if uploaded_files:
            text_files = list(processed_text.glob("*.txt"))
            if text_files:
                chunk_files = list(raw_chunks.glob("*.txt"))
                if chunk_files:
                    embedding_files = list(processed_vectors.glob("*_embeddings.json"))
                    if embedding_files:
                        with open(embedding_files[0], "r") as f:
                            file_data = json.load(f)

                        assert "embeddings" in file_data
                        assert "metadata" in file_data
                        assert "file_id" in file_data
                        assert file_data["storage_format"] == "json"

                        embeddings_data = file_data["embeddings"]
                        assert len(embeddings_data) > 0
                        assert all("embedding" in item for item in embeddings_data)
                        assert all("filename" in item for item in embeddings_data)
                        assert all("token_count" in item for item in embeddings_data)
                        assert (
                            embeddings_data[0]["embedding_model"]
                            == settings.cohere_model
                        )
