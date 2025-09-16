"""
Tests for search interfaces, query objects, and result objects.
"""

from dataclasses import dataclass
from typing import List

import pytest

from src.core.domain import Chunk, ChunkId, DocumentId, LibraryId, Vector
from src.core.search.query.search_query import SearchAlgorithm, SearchQuery
from src.core.search.query.search_result import ChunkSearchResult, SearchResults


@pytest.fixture
def sample_vector():
    """Create a sample vector for testing."""
    return Vector.from_list([0.1, 0.2, 0.3, 0.4], "test-model")


@pytest.fixture
def sample_chunk():
    """Create a sample chunk for testing."""
    document_id = DocumentId.generate()
    return Chunk(
        id=ChunkId(document_id.value, 0),
        document_id=document_id,
        filename=f"doc_{document_id.value}_chunk_000.txt",
        text="This is a sample chunk for testing search results",
        token_count=10,
        sequence_index=0,
        embedding=Vector.from_list([0.5, 0.6, 0.7, 0.8], "test-model"),
    )


class TestSearchAlgorithm:
    """Test the SearchAlgorithm enum."""

    def test_search_algorithm_values(self):
        """Test that search algorithm values are correct."""
        assert SearchAlgorithm.COSINE.value == "cosine"
        assert SearchAlgorithm.HYBRID.value == "hybrid"

    def test_from_string_valid_algorithms(self):
        """Test creating SearchAlgorithm from valid strings."""
        assert SearchAlgorithm.from_string("cosine") == SearchAlgorithm.COSINE
        assert SearchAlgorithm.from_string("hybrid") == SearchAlgorithm.HYBRID

        # Test case insensitive
        assert SearchAlgorithm.from_string("COSINE") == SearchAlgorithm.COSINE
        assert SearchAlgorithm.from_string("Hybrid") == SearchAlgorithm.HYBRID
        assert SearchAlgorithm.from_string("CoSiNe") == SearchAlgorithm.COSINE

    def test_from_string_invalid_algorithm(self):
        """Test that invalid algorithm strings raise ValueError."""
        with pytest.raises(ValueError, match="Invalid algorithm 'invalid'"):
            SearchAlgorithm.from_string("invalid")

        with pytest.raises(ValueError, match="Invalid algorithm 'semantic'"):
            SearchAlgorithm.from_string("semantic")

        # Should show valid options
        with pytest.raises(ValueError, match="Valid options: \\['cosine', 'hybrid'\\]"):
            SearchAlgorithm.from_string("unknown")

    def test_from_string_empty_algorithm(self):
        """Test that empty algorithm string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid algorithm ''"):
            SearchAlgorithm.from_string("")


class TestSearchQuery:
    """Test the SearchQuery dataclass."""

    def test_search_query_creation_valid(self, sample_vector):
        """Test creating a valid search query."""
        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=10, embedding=sample_vector)

        assert query.text == "test query"
        assert query.algorithm == SearchAlgorithm.COSINE
        assert query.limit == 10
        assert query.embedding == sample_vector

    def test_search_query_creation_without_embedding(self):
        """Test creating a search query without embedding."""
        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.HYBRID, limit=5)

        assert query.text == "test query"
        assert query.algorithm == SearchAlgorithm.HYBRID
        assert query.limit == 5
        assert query.embedding is None

    def test_search_query_empty_text(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            SearchQuery(text="", algorithm=SearchAlgorithm.COSINE, limit=10)

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            SearchQuery(text="   ", algorithm=SearchAlgorithm.COSINE, limit=10)

    def test_search_query_invalid_limit(self):
        """Test that invalid limits raise ValueError."""
        # Zero limit
        with pytest.raises(ValueError, match="Limit must be positive"):
            SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=0)

        # Negative limit
        with pytest.raises(ValueError, match="Limit must be positive"):
            SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=-5)

        # Limit too high
        with pytest.raises(ValueError, match="Limit cannot exceed 1000 results"):
            SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=1001)

    def test_search_query_has_embedding(self, sample_vector):
        """Test the has_embedding method."""
        # Query with embedding
        query_with_embedding = SearchQuery(
            text="test query", algorithm=SearchAlgorithm.COSINE, limit=10, embedding=sample_vector
        )
        assert query_with_embedding.has_embedding() is True

        # Query without embedding
        query_without_embedding = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=10)
        assert query_without_embedding.has_embedding() is False

    def test_search_query_get_algorithm_name(self):
        """Test the get_algorithm_name method."""
        cosine_query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=10)
        assert cosine_query.get_algorithm_name() == "cosine"

        hybrid_query = SearchQuery(text="test query", algorithm=SearchAlgorithm.HYBRID, limit=10)
        assert hybrid_query.get_algorithm_name() == "hybrid"

    def test_search_query_edge_cases(self):
        """Test edge cases for SearchQuery."""
        # Limit of 1 (minimum valid)
        query = SearchQuery(text="test", algorithm=SearchAlgorithm.COSINE, limit=1)
        assert query.limit == 1

        # Limit of 1000 (maximum valid)
        query = SearchQuery(text="test", algorithm=SearchAlgorithm.COSINE, limit=1000)
        assert query.limit == 1000

        # Text with only valid content after stripping
        query = SearchQuery(text="  test query  ", algorithm=SearchAlgorithm.COSINE, limit=10)
        assert query.text == "  test query  "  # Original text preserved


class TestChunkSearchResult:
    """Test the ChunkSearchResult dataclass."""

    def test_chunk_search_result_creation(self, sample_chunk):
        """Test creating a chunk search result."""
        result = ChunkSearchResult(chunk=sample_chunk, similarity_score=0.85, rank=1)

        assert result.chunk == sample_chunk
        assert result.similarity_score == 0.85
        assert result.rank == 1

    def test_chunk_search_result_validation(self, sample_chunk):
        """Test chunk search result validation."""
        # Valid score range
        result = ChunkSearchResult(chunk=sample_chunk, similarity_score=0.0, rank=1)
        assert result.similarity_score == 0.0

        result = ChunkSearchResult(chunk=sample_chunk, similarity_score=1.0, rank=1)
        assert result.similarity_score == 1.0

        # Valid rank
        result = ChunkSearchResult(chunk=sample_chunk, similarity_score=0.5, rank=1)
        assert result.rank == 1

    def test_chunk_search_result_invalid_score(self, sample_chunk):
        """Test that invalid similarity scores raise ValueError."""
        # Score too low
        with pytest.raises(ValueError, match="Similarity score must be between 0.0 and 1.0"):
            ChunkSearchResult(chunk=sample_chunk, similarity_score=-0.1, rank=1)

        # Score too high
        with pytest.raises(ValueError, match="Similarity score must be between 0.0 and 1.0"):
            ChunkSearchResult(chunk=sample_chunk, similarity_score=1.1, rank=1)

    def test_chunk_search_result_invalid_rank(self, sample_chunk):
        """Test that invalid ranks raise ValueError."""
        # Zero rank
        with pytest.raises(ValueError, match="Rank must be positive"):
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.5, rank=0)

        # Negative rank
        with pytest.raises(ValueError, match="Rank must be positive"):
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.5, rank=-1)

    def test_chunk_search_result_get_preview(self, sample_chunk):
        """Test getting content preview."""
        result = ChunkSearchResult(chunk=sample_chunk, similarity_score=0.85, rank=1)

        # Test chunk access through result
        assert result.get_chunk_text() == sample_chunk.text
        assert result.get_chunk_filename() == sample_chunk.filename
        assert result.get_chunk_sequence() == sample_chunk.sequence_index

    def test_chunk_search_result_get_preview_with_long_content(self):
        """Test content preview with long text."""
        long_content = "This is a very long chunk content that exceeds the default preview length. " * 10
        document_id = DocumentId.generate()
        chunk = Chunk(
            id=ChunkId(document_id.value, 0),
            document_id=document_id,
            filename=f"doc_{document_id.value}_chunk_000.txt",
            text=long_content,
            token_count=100,
            sequence_index=0,
        )

        result = ChunkSearchResult(chunk=chunk, similarity_score=0.75, rank=2)

        # Test that we can access the chunk text
        assert result.get_chunk_text() == long_content
        assert len(result.get_chunk_text()) > 500  # Verify it's long


class TestSearchResults:
    """Test the SearchResults dataclass."""

    def test_search_results_creation(self, sample_chunk):
        """Test creating search results."""
        chunk_results = [
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1),
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.8, rank=2),
        ]

        library_id = LibraryId("test@example.com")

        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.123,
            total_chunks_searched=100,
            library_id=library_id,
            query_text="test query",
        )

        assert results.results == chunk_results
        assert results.algorithm_used == SearchAlgorithm.COSINE
        assert results.execution_time == 0.123
        assert results.total_chunks_searched == 100
        assert results.library_id == library_id
        assert results.query_text == "test query"

    def test_search_results_validation(self, sample_chunk):
        """Test search results validation."""
        chunk_results = [ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1)]

        # Valid execution time
        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.HYBRID,
            execution_time=0.0,
            total_chunks_searched=1,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )
        assert results.execution_time == 0.0

        # Valid chunks searched count
        results = SearchResults(
            results=[],
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.5,
            total_chunks_searched=0,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )
        assert results.total_chunks_searched == 0

    def test_search_results_invalid_execution_time(self, sample_chunk):
        """Test that invalid execution time raises ValueError."""
        chunk_results = [ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1)]

        with pytest.raises(ValueError, match="Execution time cannot be negative"):
            SearchResults(
                results=chunk_results,
                algorithm_used=SearchAlgorithm.COSINE,
                execution_time=-0.1,
                total_chunks_searched=1,
                library_id=LibraryId("test@example.com"),
                query_text="test",
            )

    def test_search_results_invalid_chunks_searched(self, sample_chunk):
        """Test that invalid chunks searched count raises ValueError."""
        chunk_results = [ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1)]

        with pytest.raises(ValueError, match="Total chunks searched cannot be negative"):
            SearchResults(
                results=chunk_results,
                algorithm_used=SearchAlgorithm.HYBRID,
                execution_time=0.1,
                total_chunks_searched=-1,
                library_id=LibraryId("test@example.com"),
                query_text="test",
            )

    def test_search_results_empty_query_text(self, sample_chunk):
        """Test that empty query text is allowed."""
        chunk_results = [ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1)]

        # Empty query text should be allowed
        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=1,
            library_id=LibraryId("test@example.com"),
            query_text="",
        )
        assert results.query_text == ""

        # Whitespace query text should also be allowed
        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=1,
            library_id=LibraryId("test@example.com"),
            query_text="   ",
        )
        assert results.query_text == "   "

    def test_search_results_get_count(self, sample_chunk):
        """Test getting result count."""
        chunk_results = [
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1),
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.8, rank=2),
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.7, rank=3),
        ]

        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=10,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        assert results.get_result_count() == 3

        # Test with empty results
        empty_results = SearchResults(
            results=[],
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=10,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        assert empty_results.get_result_count() == 0

    def test_search_results_has_results(self, sample_chunk):
        """Test checking if results exist."""
        # With results
        chunk_results = [ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1)]

        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=1,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        assert results.get_result_count() > 0

        # Without results
        empty_results = SearchResults(
            results=[],
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=0,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        assert empty_results.get_result_count() == 0

    def test_search_results_get_top_result(self, sample_chunk):
        """Test getting the top result."""
        chunk_results = [
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.9, rank=1),
            ChunkSearchResult(chunk=sample_chunk, similarity_score=0.8, rank=2),
        ]

        results = SearchResults(
            results=chunk_results,
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=2,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        top_result = results.get_top_result()
        assert top_result is not None
        assert top_result.rank == 1
        assert top_result.similarity_score == 0.9

        # Test with empty results
        empty_results = SearchResults(
            results=[],
            algorithm_used=SearchAlgorithm.COSINE,
            execution_time=0.1,
            total_chunks_searched=0,
            library_id=LibraryId("test@example.com"),
            query_text="test",
        )

        # Test with empty results - should raise exception
        with pytest.raises(ValueError, match="No results available"):
            empty_results.get_top_result()
