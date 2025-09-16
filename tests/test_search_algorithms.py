"""
Tests for search algorithms (cosine, hybrid, and base functionality).
"""

from typing import List
from unittest.mock import MagicMock, Mock

import pytest

from src.core.domain import Chunk, ChunkId, DocumentId, Vector
from src.core.search.algorithms.base_search import BaseSearchAlgorithm
from src.core.search.algorithms.cosine_search import CosineSearchAlgorithm
from src.core.search.algorithms.hybrid_search import HybridSearchAlgorithm
from src.core.search.query import ChunkSearchResult


class TestableBaseSearch(BaseSearchAlgorithm):
    """Concrete implementation of BaseSearchAlgorithm for testing."""

    def search(self, query_vector, chunks, limit, query_text=None):
        """Simple implementation for testing base functionality."""
        self._validate_inputs(query_vector, chunks, limit)
        valid_chunks = self._filter_valid_chunks(chunks)
        # Return simple scores for testing
        scores = [0.9, 0.8, 0.7][: len(valid_chunks)]
        return self._create_search_results(valid_chunks, scores, limit)

    def get_algorithm_name(self):
        return "testable"


@pytest.fixture
def sample_vectors():
    """Create sample vectors for testing."""
    return {
        "query": Vector.from_list([1.0, 0.0, 0.0], "test-model"),
        "chunk1": Vector.from_list([0.9, 0.1, 0.0], "test-model"),
        "chunk2": Vector.from_list([0.0, 1.0, 0.0], "test-model"),
        "chunk3": Vector.from_list([0.5, 0.5, 0.0], "test-model"),
    }


@pytest.fixture
def sample_chunks(sample_vectors):
    """Create sample chunks with embeddings for testing."""
    chunks = []
    for i, (name, vector) in enumerate(sample_vectors.items()):
        if name == "query":
            continue

        document_id = DocumentId.generate()
        chunk = Chunk(
            id=ChunkId(document_id.value, i),
            document_id=document_id,
            filename=f"doc_{document_id.value}_chunk_{i:03d}.txt",
            text=f"This is sample text for {name}",
            token_count=10,
            sequence_index=i,
            embedding=vector,
        )
        chunks.append(chunk)

    return chunks


@pytest.fixture
def chunks_without_embeddings():
    """Create chunks without embeddings for testing validation."""
    chunks = []
    for i in range(2):
        document_id = DocumentId.generate()
        chunk = Chunk(
            id=ChunkId(document_id.value, i),
            document_id=document_id,
            filename=f"doc_{document_id.value}_chunk_{i:03d}.txt",
            text=f"Chunk {i} without embedding",
            token_count=10,
            sequence_index=i,
        )
        chunks.append(chunk)
    return chunks


class TestBaseSearchAlgorithm:
    """Test the base search algorithm functionality."""

    def test_validate_inputs_valid(self, sample_vectors, sample_chunks):
        """Test validation with valid inputs."""
        search = TestableBaseSearch()
        # Should not raise any exception
        search._validate_inputs(sample_vectors["query"], sample_chunks, 5)

    def test_validate_inputs_negative_limit(self, sample_vectors, sample_chunks):
        """Test validation fails with negative limit."""
        search = TestableBaseSearch()
        with pytest.raises(ValueError, match="Limit must be positive"):
            search._validate_inputs(sample_vectors["query"], sample_chunks, -1)

    def test_validate_inputs_zero_limit(self, sample_vectors, sample_chunks):
        """Test validation fails with zero limit."""
        search = TestableBaseSearch()
        with pytest.raises(ValueError, match="Limit must be positive"):
            search._validate_inputs(sample_vectors["query"], sample_chunks, 0)

    def test_validate_inputs_empty_chunks(self, sample_vectors):
        """Test validation fails with empty chunks list."""
        search = TestableBaseSearch()
        with pytest.raises(ValueError, match="Chunks list cannot be empty"):
            search._validate_inputs(sample_vectors["query"], [], 5)

    def test_validate_inputs_chunks_without_embeddings(self, sample_vectors, chunks_without_embeddings):
        """Test validation fails when chunks don't have embeddings."""
        search = TestableBaseSearch()
        with pytest.raises(ValueError, match="Found 2 chunks without embeddings"):
            search._validate_inputs(sample_vectors["query"], chunks_without_embeddings, 5)

    def test_validate_inputs_dimension_mismatch(self, sample_chunks):
        """Test validation fails when query vector dimension doesn't match chunk embeddings."""
        search = TestableBaseSearch()
        wrong_dimension_vector = Vector.from_list([1.0, 0.0], "test-model")  # 2D instead of 3D

        with pytest.raises(
            ValueError, match="Query vector dimension \\(2\\) does not match chunk embedding dimension \\(3\\)"
        ):
            search._validate_inputs(wrong_dimension_vector, sample_chunks, 5)

    def test_filter_valid_chunks(self, sample_chunks, chunks_without_embeddings):
        """Test filtering chunks to only include those with embeddings."""
        search = TestableBaseSearch()
        all_chunks = sample_chunks + chunks_without_embeddings

        valid_chunks = search._filter_valid_chunks(all_chunks)

        assert len(valid_chunks) == len(sample_chunks)
        assert all(chunk.has_embedding() for chunk in valid_chunks)

    def test_create_search_results_valid(self, sample_chunks):
        """Test creating search results with valid inputs."""
        search = TestableBaseSearch()
        scores = [0.9, 0.7, 0.8]

        results = search._create_search_results(sample_chunks, scores, 5)

        assert len(results) == 3
        assert all(isinstance(result, ChunkSearchResult) for result in results)

        # Check ordering (highest score first)
        assert results[0].similarity_score == 0.9
        assert results[1].similarity_score == 0.8
        assert results[2].similarity_score == 0.7

        # Check ranks
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3

    def test_create_search_results_respects_limit(self, sample_chunks):
        """Test that search results respect the limit parameter."""
        search = TestableBaseSearch()
        scores = [0.9, 0.7, 0.8]

        results = search._create_search_results(sample_chunks, scores, 2)

        assert len(results) == 2
        assert results[0].similarity_score == 0.9
        assert results[1].similarity_score == 0.8

    def test_create_search_results_mismatched_lengths(self, sample_chunks):
        """Test creating search results fails when chunks and scores have different lengths."""
        search = TestableBaseSearch()
        scores = [0.9, 0.7]  # Only 2 scores for 3 chunks

        with pytest.raises(ValueError, match="Chunks and scores lists must have the same length"):
            search._create_search_results(sample_chunks, scores, 5)


class TestCosineSearchAlgorithm:
    """Test the cosine similarity search algorithm."""

    def test_cosine_search_basic(self, sample_vectors, sample_chunks):
        """Test basic cosine similarity search."""
        search = CosineSearchAlgorithm()

        results = search.search(sample_vectors["query"], sample_chunks, 3)

        assert len(results) == 3
        assert all(isinstance(result, ChunkSearchResult) for result in results)

        # Results should be ordered by similarity (chunk1 should be most similar to query)
        assert results[0].similarity_score > results[1].similarity_score
        assert results[1].similarity_score > results[2].similarity_score

    def test_cosine_search_with_limit(self, sample_vectors, sample_chunks):
        """Test cosine search respects limit parameter."""
        search = CosineSearchAlgorithm()

        results = search.search(sample_vectors["query"], sample_chunks, 2)

        assert len(results) == 2

    def test_cosine_search_empty_query_text(self, sample_vectors, sample_chunks):
        """Test cosine search works with query_text parameter (even though it's not used)."""
        search = CosineSearchAlgorithm()

        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text="test query")

        assert len(results) == 3

    def test_get_algorithm_name(self):
        """Test algorithm name is correct."""
        search = CosineSearchAlgorithm()
        assert search.get_algorithm_name() == "cosine"

    def test_cosine_search_validation_errors(self, sample_vectors):
        """Test that cosine search properly validates inputs."""
        search = CosineSearchAlgorithm()

        # Test empty chunks
        with pytest.raises(ValueError, match="Chunks list cannot be empty"):
            search.search(sample_vectors["query"], [], 5)

        # Test negative limit
        with pytest.raises(ValueError, match="Limit must be positive"):
            search.search(sample_vectors["query"], [], -1)


class TestHybridSearchAlgorithm:
    """Test the hybrid search algorithm."""

    def test_hybrid_search_initialization_valid(self):
        """Test hybrid search initialization with valid weights."""
        search = HybridSearchAlgorithm(cosine_weight=0.6, keyword_weight=0.4)
        assert search.cosine_weight == 0.6
        assert search.keyword_weight == 0.4

    def test_hybrid_search_initialization_default(self):
        """Test hybrid search initialization with default weights."""
        search = HybridSearchAlgorithm()
        assert search.cosine_weight == 0.7
        assert search.keyword_weight == 0.3

    def test_hybrid_search_initialization_invalid_weights(self):
        """Test hybrid search initialization fails with invalid weights."""
        # Negative weight
        with pytest.raises(ValueError, match="Cosine weight must be between 0.0 and 1.0"):
            HybridSearchAlgorithm(cosine_weight=-0.1, keyword_weight=1.1)

        # Weight > 1.0
        with pytest.raises(ValueError, match="Keyword weight must be between 0.0 and 1.0"):
            HybridSearchAlgorithm(cosine_weight=0.5, keyword_weight=1.5)

        # Weights don't sum to 1.0
        with pytest.raises(ValueError, match="Cosine weight and keyword weight must sum to 1.0"):
            HybridSearchAlgorithm(cosine_weight=0.6, keyword_weight=0.3)

    def test_hybrid_search_basic(self, sample_vectors, sample_chunks):
        """Test basic hybrid search functionality."""
        search = HybridSearchAlgorithm()
        query_text = "sample text chunk1"

        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text=query_text)

        assert len(results) == 3
        assert all(isinstance(result, ChunkSearchResult) for result in results)
        assert all(0.0 <= result.similarity_score <= 1.0 for result in results)

    def test_hybrid_search_with_empty_query_text(self, sample_vectors, sample_chunks):
        """Test that hybrid search handles empty query text gracefully."""
        search = HybridSearchAlgorithm()

        # Should work with None query text (falls back to cosine only)
        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text=None)
        assert len(results) <= 3

        # Should work with empty query text (falls back to cosine only)
        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text="")
        assert len(results) <= 3

    def test_hybrid_search_keyword_matching(self, sample_vectors):
        """Test hybrid search keyword matching component."""
        search = HybridSearchAlgorithm()

        # Create chunks with specific content for keyword testing
        chunks = []
        contents = [
            "apple banana fruit delicious",
            "car vehicle transportation fast",
            "apple computer technology modern",
        ]

        for i, content in enumerate(contents):
            document_id = DocumentId.generate()
            chunk = Chunk(
                id=ChunkId(document_id.value, i),
                document_id=document_id,
                filename=f"doc_{document_id.value}_chunk_{i:03d}.txt",
                text=content,
                token_count=len(content.split()),
                sequence_index=i,
                embedding=sample_vectors["chunk1"],  # Use same embedding for all
            )
            chunks.append(chunk)

        # Search for "apple" - should boost chunks containing that word
        results = search.search(sample_vectors["query"], chunks, 3, query_text="apple")

        # Find chunks containing "apple"
        apple_chunks = [i for i, chunk in enumerate(chunks) if "apple" in chunk.text]

        # At least one apple chunk should be in top results
        apple_results = [result for result in results if "apple" in result.chunk.text]
        assert len(apple_results) >= 1

    def test_get_algorithm_name(self):
        """Test algorithm name is correct."""
        search = HybridSearchAlgorithm()
        assert search.get_algorithm_name() == "hybrid"

    def test_hybrid_search_text_preprocessing(self):
        """Test text preprocessing in hybrid search."""
        search = HybridSearchAlgorithm()

        # Test keyword extraction
        keywords = search._extract_keywords("Hello, World! This is a test.")
        # Should extract meaningful keywords, filtering stop words
        assert "hello" in keywords
        assert "world" in keywords
        assert "test" in keywords
        # Stop words should be filtered out
        assert "this" not in keywords
        assert "is" not in keywords

        # Test empty text
        keywords = search._extract_keywords("")
        assert keywords == []

        # Test text with only punctuation
        keywords = search._extract_keywords("!@#$%^&*()")
        assert keywords == []

    def test_hybrid_search_bm25_calculation(self, sample_vectors):
        """Test BM25 score calculation."""
        search = HybridSearchAlgorithm()

        # Create test chunks
        document_id1 = DocumentId.generate()
        chunk1 = Chunk(
            id=ChunkId(document_id1.value, 0),
            document_id=document_id1,
            filename=f"doc_{document_id1.value}_chunk_000.txt",
            text="apple banana apple fruit",
            token_count=4,
            sequence_index=0,
            embedding=sample_vectors["chunk1"],
        )

        document_id2 = DocumentId.generate()
        chunk2 = Chunk(
            id=ChunkId(document_id2.value, 0),
            document_id=document_id2,
            filename=f"doc_{document_id2.value}_chunk_000.txt",
            text="car vehicle fast",
            token_count=3,
            sequence_index=0,
            embedding=sample_vectors["chunk2"],
        )

        chunks = [chunk1, chunk2]
        query_text = "apple fruit"

        # Calculate keyword scores (which includes BM25-like calculation)
        scores = search._calculate_keyword_scores(query_text, chunks)

        assert len(scores) == 2
        assert scores[0] > scores[1]  # chunk1 should have higher score
        assert all(score >= 0 for score in scores)

    def test_hybrid_search_with_different_weights(self, sample_vectors, sample_chunks):
        """Test hybrid search with different weight configurations."""
        # Pure semantic search (cosine_weight=1.0)
        semantic_search = HybridSearchAlgorithm(cosine_weight=1.0, keyword_weight=0.0)
        semantic_results = semantic_search.search(
            sample_vectors["query"], sample_chunks, 3, query_text="irrelevant keywords"
        )

        # Pure keyword search (keyword_weight=1.0)
        keyword_search = HybridSearchAlgorithm(cosine_weight=0.0, keyword_weight=1.0)
        keyword_results = keyword_search.search(sample_vectors["query"], sample_chunks, 3, query_text="sample text")

        # Results should be different due to different weighting
        assert len(semantic_results) == 3
        assert len(keyword_results) == 3

    def test_hybrid_search_edge_cases(self, sample_vectors, sample_chunks):
        """Test hybrid search edge cases."""
        search = HybridSearchAlgorithm()

        # Query with no matching keywords
        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text="xyz nonexistent words")
        assert len(results) == 3  # Should still return results based on cosine similarity

        # Query with special characters
        results = search.search(sample_vectors["query"], sample_chunks, 3, query_text="test!@#$%^&*()query")
        assert len(results) == 3
