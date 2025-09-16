"""
Service for generating text embeddings using Cohere API.
"""

from typing import List

import cohere

from ..config import settings
from ..domain import Vector
from ..search.interfaces import IEmbeddingService


class CohereEmbeddingService(IEmbeddingService):
    """
    Embedding service using Cohere API.

    Generates vector embeddings for text using Cohere's embedding models.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize Cohere embedding service.

        Args:
            api_key: Cohere API key (defaults to settings)
            model: Cohere model name (defaults to settings)
        """
        self.api_key = api_key or settings.cohere_api_key
        self.model = model or settings.cohere_model

        if not self.api_key:
            raise ValueError("Cohere API key is required")

        self.client = cohere.Client(self.api_key)

    async def generate_embedding(self, text: str) -> Vector:
        """
        Generate a vector embedding for the given text.

        Args:
            text: The text to generate an embedding for

        Returns:
            Vector embedding of the text
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            response = self.client.embed(
                texts=[text], model=self.model, input_type="search_query"  # Optimize for search queries
            )
            embedding_values = response.embeddings[0]
            vector = Vector.from_list(embedding_values, self.model)

            return vector

        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {str(e)}")

    def get_model_name(self) -> str:
        """Get the name of the embedding model being used."""
        return self.model

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this service."""
        # Cohere embed-english-v3.0 produces 1024-dimensional embeddings
        # This should ideally be retrieved from the API, but for now we'll hardcode
        model_dimensions = {
            "embed-english-v3.0": 1024,
            "embed-english-light-v3.0": 384,
            "embed-multilingual-v3.0": 1024,
            "embed-multilingual-light-v3.0": 384,
        }

        return model_dimensions.get(self.model, 1024)  # Default to 1024

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Vector]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to generate embeddings for

        Returns:
            List of Vector embeddings
        """
        if not texts:
            return []

        valid_texts = [text for text in texts if text.strip()]
        if not valid_texts:
            raise ValueError("All texts are empty")

        try:
            response = self.client.embed(
                texts=valid_texts, model=self.model, input_type="search_document"  # Optimize for document content
            )
            vectors = []
            for embedding_values in response.embeddings:
                vector = Vector.from_list(embedding_values, self.model)
                vectors.append(vector)

            return vectors

        except Exception as e:
            raise RuntimeError(f"Failed to generate batch embeddings: {str(e)}")
