"""
Tests for the embedding service.
"""

from typing import List
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.domain import Vector
from src.core.services.embedding_service import CohereEmbeddingService


@pytest.fixture
def mock_cohere_client():
    """Create a mock Cohere client."""
    client = Mock()

    # Mock single embedding response
    single_response = Mock()
    single_response.embeddings = [[0.1, 0.2, 0.3, 0.4]]

    # Mock batch embedding response
    batch_response = Mock()
    batch_response.embeddings = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]]

    client.embed.return_value = single_response
    return client


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.cohere_api_key = "test-api-key"
    settings.cohere_model = "embed-english-v3.0"
    return settings


class TestCohereEmbeddingService:
    """Test the Cohere embedding service."""

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_initialization_with_defaults(self, mock_settings_module, mock_cohere_class):
        """Test initialization with default settings."""
        mock_settings_module.cohere_api_key = "default-key"
        mock_settings_module.cohere_model = "default-model"

        service = CohereEmbeddingService()

        assert service.api_key == "default-key"
        assert service.model == "default-model"
        mock_cohere_class.assert_called_once_with("default-key")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_initialization_with_custom_params(self, mock_settings_module, mock_cohere_class):
        """Test initialization with custom parameters."""
        service = CohereEmbeddingService(api_key="custom-key", model="custom-model")

        assert service.api_key == "custom-key"
        assert service.model == "custom-model"
        mock_cohere_class.assert_called_once_with("custom-key")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_initialization_missing_api_key(self, mock_settings_module, mock_cohere_class):
        """Test initialization fails when API key is missing."""
        mock_settings_module.cohere_api_key = None

        with pytest.raises(ValueError, match="Cohere API key is required"):
            CohereEmbeddingService()

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_initialization_empty_api_key(self, mock_settings_module, mock_cohere_class):
        """Test initialization fails when API key is empty."""
        mock_settings_module.cohere_api_key = ""

        with pytest.raises(ValueError, match="Cohere API key is required"):
            CohereEmbeddingService()

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, mock_settings_module, mock_cohere_class, mock_cohere_client):
        """Test successful embedding generation."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "embed-english-v3.0"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock successful response
        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3, 0.4]]
        mock_cohere_client.embed.return_value = mock_response

        # Generate embedding
        result = await service.generate_embedding("test text")

        # Verify result
        assert isinstance(result, Vector)
        assert result.values == [0.1, 0.2, 0.3, 0.4]
        assert result.model == "embed-english-v3.0"

        # Verify API call
        mock_cohere_client.embed.assert_called_once_with(
            texts=["test text"], model="embed-english-v3.0", input_type="search_query"
        )

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, mock_settings_module, mock_cohere_class):
        """Test embedding generation fails with empty text."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"

        service = CohereEmbeddingService()

        with pytest.raises(ValueError, match="Text cannot be empty"):
            await service.generate_embedding("")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            await service.generate_embedding("   ")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, mock_settings_module, mock_cohere_class, mock_cohere_client):
        """Test embedding generation handles API errors."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock API error
        mock_cohere_client.embed.side_effect = Exception("API rate limit exceeded")

        with pytest.raises(RuntimeError, match="Failed to generate embedding: API rate limit exceeded"):
            await service.generate_embedding("test text")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_no_embeddings_returned(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test embedding generation handles empty response."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock empty response
        mock_response = Mock()
        mock_response.embeddings = []
        mock_cohere_client.embed.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await service.generate_embedding("test text")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_invalid_response_format(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test embedding generation handles invalid response format."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock invalid response format
        mock_response = Mock()
        mock_response.embeddings = "invalid format"
        mock_cohere_client.embed.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await service.generate_embedding("test text")

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_get_model_name(self, mock_settings_module, mock_cohere_class):
        """Test getting the model name."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "embed-english-v3.0"

        service = CohereEmbeddingService()
        assert service.get_model_name() == "embed-english-v3.0"

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_get_embedding_dimension_known_models(self, mock_settings_module, mock_cohere_class):
        """Test getting embedding dimension for known models."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_cohere_class.return_value = Mock()

        # Test different known models
        test_cases = [
            ("embed-english-v3.0", 1024),
            ("embed-english-light-v3.0", 384),
            ("embed-multilingual-v3.0", 1024),
            ("embed-multilingual-light-v3.0", 384),
        ]

        for model, expected_dim in test_cases:
            mock_settings_module.cohere_model = model
            service = CohereEmbeddingService()
            assert service.get_embedding_dimension() == expected_dim

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    def test_get_embedding_dimension_unknown_model(self, mock_settings_module, mock_cohere_class):
        """Test getting embedding dimension for unknown model defaults to 1024."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "unknown-model"
        mock_cohere_class.return_value = Mock()

        service = CohereEmbeddingService()
        assert service.get_embedding_dimension() == 1024  # Default

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self, mock_settings_module, mock_cohere_class, mock_cohere_client):
        """Test successful batch embedding generation."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "embed-english-v3.0"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock successful batch response
        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
        mock_cohere_client.embed.return_value = mock_response

        # Generate batch embeddings
        texts = ["text 1", "text 2", "text 3"]
        results = await service.generate_embeddings_batch(texts)

        # Verify results
        assert len(results) == 3
        assert all(isinstance(result, Vector) for result in results)
        assert results[0].values == [0.1, 0.2, 0.3]
        assert results[1].values == [0.4, 0.5, 0.6]
        assert results[2].values == [0.7, 0.8, 0.9]

        # Verify API call
        mock_cohere_client.embed.assert_called_once_with(
            texts=texts, model="embed-english-v3.0", input_type="search_document"
        )

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty_list(self, mock_settings_module, mock_cohere_class):
        """Test batch embedding generation with empty list."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"

        service = CohereEmbeddingService()

        result = await service.generate_embeddings_batch([])
        assert result == []

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_all_empty_texts(self, mock_settings_module, mock_cohere_class):
        """Test batch embedding generation fails when all texts are empty."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"

        service = CohereEmbeddingService()

        with pytest.raises(ValueError, match="All texts are empty"):
            await service.generate_embeddings_batch(["", "   ", ""])

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_filters_empty_texts(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test batch embedding generation filters out empty texts."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "embed-english-v3.0"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock response for valid texts only
        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_cohere_client.embed.return_value = mock_response

        # Mix of valid and empty texts
        texts = ["valid text 1", "", "valid text 2", "   "]
        results = await service.generate_embeddings_batch(texts)

        # Should only return embeddings for valid texts
        assert len(results) == 2

        # Verify API called with filtered texts
        mock_cohere_client.embed.assert_called_once_with(
            texts=["valid text 1", "valid text 2"], model="embed-english-v3.0", input_type="search_document"
        )

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_api_error(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test batch embedding generation handles API errors."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock API error
        mock_cohere_client.embed.side_effect = Exception("Batch processing failed")

        with pytest.raises(RuntimeError, match="Failed to generate batch embeddings: Batch processing failed"):
            await service.generate_embeddings_batch(["text 1", "text 2"])

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_invalid_response(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test batch embedding generation handles invalid response format."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "test-model"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock invalid response format
        mock_response = Mock()
        mock_response.embeddings = "not a list"
        mock_cohere_client.embed.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate batch embeddings"):
            await service.generate_embeddings_batch(["text 1", "text 2"])

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_partial_invalid_embeddings(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test batch embedding generation handles partial invalid embeddings."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_settings_module.cohere_model = "embed-english-v3.0"
        mock_cohere_class.return_value = mock_cohere_client

        service = CohereEmbeddingService()

        # Mock response with mix of valid and invalid embeddings
        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], "invalid", [0.4, 0.5, 0.6]]  # Valid  # Invalid  # Valid
        mock_cohere_client.embed.return_value = mock_response

        results = await service.generate_embeddings_batch(["text 1", "text 2", "text 3"])

        # Should only return valid embeddings
        assert len(results) == 2
        assert results[0].values == [0.1, 0.2, 0.3]
        assert results[1].values == [0.4, 0.5, 0.6]

    @patch("src.core.services.embedding_service.cohere.Client")
    @patch("src.core.services.embedding_service.settings")
    @pytest.mark.asyncio
    async def test_generate_embedding_with_custom_model(
        self, mock_settings_module, mock_cohere_class, mock_cohere_client
    ):
        """Test embedding generation uses the correct model."""
        mock_settings_module.cohere_api_key = "test-key"
        mock_cohere_class.return_value = mock_cohere_client

        # Create service with custom model
        service = CohereEmbeddingService(model="embed-multilingual-v3.0")

        # Mock successful response
        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3, 0.4]]
        mock_cohere_client.embed.return_value = mock_response

        result = await service.generate_embedding("test text")

        # Verify correct model was used
        assert result.model == "embed-multilingual-v3.0"
        mock_cohere_client.embed.assert_called_once_with(
            texts=["test text"], model="embed-multilingual-v3.0", input_type="search_query"
        )
