"""
Tests for query service and library search engine.
"""

import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.core.domain import Chunk, ChunkId, DocumentId, Library, LibraryId, Vector
from src.core.search.interfaces import IEmbeddingService, ILibraryRepository
from src.core.search.query import ChunkSearchResult, SearchAlgorithm, SearchQuery, SearchResults
from src.core.services.library_search_engine import LibrarySearchEngine
from src.core.services.query_service import QueryService


@pytest.fixture
def mock_library_repository():
    """Create a mock library repository."""
    repo = Mock(spec=ILibraryRepository)
    repo.library_exists = AsyncMock()
    repo.load_library = AsyncMock()
    return repo


@pytest.fixture
def mock_search_engine():
    """Create a mock search engine."""
    engine = Mock()
    engine.search_library = AsyncMock()
    engine.get_supported_algorithms = Mock(return_value=["cosine", "hybrid"])
    return engine


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = Mock(spec=IEmbeddingService)
    service.generate_embedding = AsyncMock()
    return service


@pytest.fixture
def sample_library():
    """Create a sample library for testing."""
    from datetime import datetime

    from src.core.domain import Document

    library = Library(id=LibraryId("test@example.com"), user_email="test@example.com")

    # Create a document and add chunks to it
    document_id = DocumentId.generate()
    document = Document(
        id=document_id,
        library_id=library.id,
        original_filename="test_document.txt",
        uploaded_filename=f"{document_id.value}_test_document.txt",
        content_type="text/plain",
        file_size=1000,
        upload_timestamp=datetime.now(),
    )

    # Add some chunks with embeddings to the document
    for i in range(3):
        chunk = Chunk(
            id=ChunkId(document_id.value, i),
            document_id=document_id,
            filename=f"doc_{document_id.value}_chunk_{i:03d}.txt",
            text=f"Sample chunk {i}",
            token_count=10,
            sequence_index=i,
            embedding=Vector.from_list([0.1 * i, 0.2 * i, 0.3 * i], "test-model"),
        )
        document.add_chunk(chunk)

    # Add the document to the library
    library.add_document(document)

    return library


@pytest.fixture
def sample_search_results(sample_library):
    """Create sample search results."""
    chunks = list(sample_library.get_all_chunks())
    if len(chunks) < 2:
        # Create additional chunks if needed
        from datetime import datetime

        document_id = DocumentId.generate()
        document = sample_library.get_all_documents()[0] if sample_library.get_all_documents() else None
        if document:
            for i in range(2 - len(chunks)):
                chunk = Chunk(
                    id=ChunkId(document.id.value, len(chunks) + i),
                    document_id=document.id,
                    filename=f"doc_{document.id.value}_chunk_{len(chunks) + i:03d}.txt",
                    text=f"Additional chunk {len(chunks) + i}",
                    token_count=10,
                    sequence_index=len(chunks) + i,
                    embedding=Vector.from_list([0.3 + 0.1 * i, 0.4 + 0.1 * i, 0.5 + 0.1 * i], "test-model"),
                )
                document.add_chunk(chunk)
                chunks.append(chunk)

    chunk_results = [
        ChunkSearchResult(chunk=chunks[0], similarity_score=0.9, rank=1),
        ChunkSearchResult(chunk=chunks[1], similarity_score=0.8, rank=2),
    ]

    return SearchResults(
        results=chunk_results,
        algorithm_used=SearchAlgorithm.COSINE,
        execution_time=0.123,
        total_chunks_searched=3,
        library_id=sample_library.id,
        query_text="test query",
    )


class TestQueryService:
    """Test the main query service."""

    def test_query_service_initialization(self, mock_library_repository, mock_search_engine, mock_embedding_service):
        """Test query service initialization."""
        service = QueryService(
            library_repository=mock_library_repository,
            search_engine=mock_search_engine,
            embedding_service=mock_embedding_service,
        )

        assert service.library_repository == mock_library_repository
        assert service.search_engine == mock_search_engine
        assert service.embedding_service == mock_embedding_service

    @pytest.mark.asyncio
    async def test_execute_query_success(
        self, mock_library_repository, mock_search_engine, mock_embedding_service, sample_library, sample_search_results
    ):
        """Test successful query execution."""
        # Setup mocks
        mock_library_repository.library_exists.return_value = True
        mock_library_repository.load_library.return_value = sample_library
        mock_search_engine.search_library.return_value = sample_search_results

        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        # Execute query
        results = await service.execute_query(
            user_email="test@example.com", query_text="test query", algorithm="cosine", limit=10
        )

        # Verify results
        assert results == sample_search_results

        # Verify mock calls
        mock_library_repository.library_exists.assert_called_once_with("test@example.com")
        mock_library_repository.load_library.assert_called_once_with("test@example.com")
        mock_search_engine.search_library.assert_called_once()

        # Check the search query passed to search engine
        call_args = mock_search_engine.search_library.call_args
        assert call_args[0][0] == sample_library
        search_query = call_args[0][1]
        assert search_query.text == "test query"
        assert search_query.algorithm == SearchAlgorithm.COSINE
        assert search_query.limit == 10

    @pytest.mark.asyncio
    async def test_execute_query_empty_email(self, mock_library_repository, mock_search_engine, mock_embedding_service):
        """Test query execution fails with empty email."""
        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        with pytest.raises(ValueError, match="User email cannot be empty"):
            await service.execute_query(user_email="", query_text="test query", algorithm="cosine", limit=10)

        with pytest.raises(ValueError, match="User email cannot be empty"):
            await service.execute_query(user_email="   ", query_text="test query", algorithm="cosine", limit=10)

    @pytest.mark.asyncio
    async def test_execute_query_empty_query_text(
        self, mock_library_repository, mock_search_engine, mock_embedding_service
    ):
        """Test query execution fails with empty query text."""
        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            await service.execute_query(user_email="test@example.com", query_text="", algorithm="cosine", limit=10)

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            await service.execute_query(user_email="test@example.com", query_text="   ", algorithm="cosine", limit=10)

    @pytest.mark.asyncio
    async def test_execute_query_invalid_limit(
        self, mock_library_repository, mock_search_engine, mock_embedding_service
    ):
        """Test query execution fails with invalid limit."""
        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        with pytest.raises(ValueError, match="Limit must be positive"):
            await service.execute_query(
                user_email="test@example.com", query_text="test query", algorithm="cosine", limit=0
            )

        with pytest.raises(ValueError, match="Limit must be positive"):
            await service.execute_query(
                user_email="test@example.com", query_text="test query", algorithm="cosine", limit=-5
            )

    @pytest.mark.asyncio
    async def test_execute_query_library_not_exists(
        self, mock_library_repository, mock_search_engine, mock_embedding_service
    ):
        """Test query execution fails when library doesn't exist."""
        mock_library_repository.library_exists.return_value = False

        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        with pytest.raises(ValueError, match="No library found for user: test@example.com"):
            await service.execute_query(
                user_email="test@example.com", query_text="test query", algorithm="cosine", limit=10
            )

    @pytest.mark.asyncio
    async def test_execute_query_invalid_algorithm(
        self, mock_library_repository, mock_search_engine, mock_embedding_service
    ):
        """Test query execution fails with invalid algorithm."""
        mock_library_repository.library_exists.return_value = True

        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        with pytest.raises(ValueError, match="Invalid algorithm"):
            await service.execute_query(
                user_email="test@example.com", query_text="test query", algorithm="invalid_algo", limit=10
            )

    def test_get_supported_algorithms(self, mock_library_repository, mock_search_engine, mock_embedding_service):
        """Test getting supported algorithms."""
        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        algorithms = service.get_supported_algorithms()

        assert algorithms == ["cosine", "hybrid"]
        mock_search_engine.get_supported_algorithms.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_library_stats_library_exists(
        self, mock_library_repository, mock_search_engine, mock_embedding_service, sample_library
    ):
        """Test getting library stats when library exists."""
        mock_library_repository.library_exists.return_value = True
        mock_library_repository.load_library.return_value = sample_library

        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        stats = await service.get_library_stats("test@example.com")

        assert stats["exists"] is True
        assert stats["document_count"] == sample_library.get_document_count()
        assert stats["chunk_count"] == sample_library.get_total_chunk_count()
        assert stats["chunks_with_embeddings"] == len(sample_library.get_chunks_with_embeddings())
        assert stats["total_file_size"] == sample_library.get_total_file_size()

    @pytest.mark.asyncio
    async def test_get_library_stats_library_not_exists(
        self, mock_library_repository, mock_search_engine, mock_embedding_service
    ):
        """Test getting library stats when library doesn't exist."""
        mock_library_repository.library_exists.return_value = False

        service = QueryService(mock_library_repository, mock_search_engine, mock_embedding_service)

        stats = await service.get_library_stats("test@example.com")

        expected = {"exists": False, "document_count": 0, "chunk_count": 0, "chunks_with_embeddings": 0}
        assert stats == expected


class TestLibrarySearchEngine:
    """Test the library search engine."""

    @pytest.fixture
    def search_engine(self, mock_embedding_service):
        """Create a library search engine instance."""
        return LibrarySearchEngine(mock_embedding_service)

    def test_library_search_engine_initialization(self, mock_embedding_service):
        """Test search engine initialization."""
        engine = LibrarySearchEngine(mock_embedding_service)

        assert engine.embedding_service == mock_embedding_service
        assert SearchAlgorithm.COSINE in engine.algorithms
        assert SearchAlgorithm.HYBRID in engine.algorithms

    @pytest.mark.asyncio
    async def test_search_library_success(self, search_engine, sample_library, mock_embedding_service):
        """Test successful library search."""
        # Setup mock embedding
        query_vector = Vector.from_list([0.5, 0.5, 0.5], "test-model")
        mock_embedding_service.generate_embedding.return_value = query_vector

        # Create search query
        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5)

        # Execute search
        with patch("time.time", side_effect=[1000.0, 1000.5]):  # Mock execution time
            results = await search_engine.search_library(sample_library, query)

        # Verify results
        assert isinstance(results, SearchResults)
        assert results.algorithm_used == SearchAlgorithm.COSINE
        assert results.execution_time == 0.5
        assert results.total_chunks_searched == len(sample_library.get_chunks_with_embeddings())
        assert results.library_id == sample_library.id
        assert results.query_text == "test query"
        assert len(results.results) <= 5

        # Verify embedding was generated
        mock_embedding_service.generate_embedding.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_library_with_existing_embedding(self, search_engine, sample_library, mock_embedding_service):
        """Test library search when query already has embedding."""
        # Create search query with embedding
        query_vector = Vector.from_list([0.5, 0.5, 0.5], "test-model")
        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5, embedding=query_vector)

        # Execute search
        results = await search_engine.search_library(sample_library, query)

        # Verify results
        assert isinstance(results, SearchResults)

        # Verify embedding was NOT generated (already existed)
        mock_embedding_service.generate_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_library_no_documents_with_embeddings(self, search_engine, mock_embedding_service):
        """Test search with library that has no documents with embeddings."""
        # Create empty library
        empty_library = Library(id=LibraryId("test@example.com"), user_email="test@example.com")

        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5)

        # Execute search
        with patch("time.time", side_effect=[1000.0, 1000.1]):
            results = await search_engine.search_library(empty_library, query)

        # Verify empty results
        assert len(results.results) == 0
        assert results.total_chunks_searched == 0
        assert abs(results.execution_time - 0.1) < 0.001  # Allow for floating point precision

    @pytest.mark.asyncio
    async def test_search_library_unsupported_algorithm(self, search_engine, sample_library):
        """Test search with unsupported algorithm."""
        # Create a mock algorithm that's not in the engine
        mock_algorithm = Mock()
        mock_algorithm.value = "unsupported"

        query = SearchQuery(text="test query", algorithm=mock_algorithm, limit=5)

        with pytest.raises(ValueError, match="Unsupported search algorithm"):
            await search_engine.search_library(sample_library, query)

    @pytest.mark.asyncio
    async def test_search_library_hybrid_algorithm(self, search_engine, sample_library, mock_embedding_service):
        """Test library search with hybrid algorithm."""
        # Setup mock embedding
        query_vector = Vector.from_list([0.5, 0.5, 0.5], "test-model")
        mock_embedding_service.generate_embedding.return_value = query_vector

        # Create search query for hybrid search
        query = SearchQuery(text="test query with keywords", algorithm=SearchAlgorithm.HYBRID, limit=3)

        # Execute search
        results = await search_engine.search_library(sample_library, query)

        # Verify results
        assert isinstance(results, SearchResults)
        assert results.algorithm_used == SearchAlgorithm.HYBRID
        assert len(results.results) <= 3

    def test_get_supported_algorithms(self, search_engine):
        """Test getting supported algorithms."""
        algorithms = search_engine.get_supported_algorithms()

        assert "cosine" in algorithms
        assert "hybrid" in algorithms
        assert len(algorithms) == 2

    @pytest.mark.asyncio
    async def test_search_library_handles_errors(self, search_engine, sample_library, mock_embedding_service):
        """Test that search engine properly handles and re-raises errors."""
        # Make embedding service raise an error
        mock_embedding_service.generate_embedding.side_effect = RuntimeError("API error")

        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5)

        # Should re-raise the error
        with pytest.raises(RuntimeError, match="API error"):
            await search_engine.search_library(sample_library, query)

    @pytest.mark.asyncio
    async def test_search_library_no_chunks_with_embeddings(self, search_engine, mock_embedding_service):
        """Test search with library that has chunks but no embeddings."""
        # Create library with chunks but no embeddings
        from datetime import datetime

        from src.core.domain import Document

        library = Library(id=LibraryId("test@example.com"), user_email="test@example.com")

        document_id = DocumentId.generate()
        document = Document(
            id=document_id,
            library_id=library.id,
            original_filename="test_no_embedding.txt",
            uploaded_filename=f"{document_id.value}_test_no_embedding.txt",
            content_type="text/plain",
            file_size=100,
            upload_timestamp=datetime.now(),
        )

        chunk_without_embedding = Chunk(
            id=ChunkId(document_id.value, 0),
            document_id=document_id,
            filename=f"doc_{document_id.value}_chunk_000.txt",
            text="Sample chunk without embedding",
            token_count=5,
            sequence_index=0,
            # No embedding
        )
        document.add_chunk(chunk_without_embedding)
        library.add_document(document)

        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5)

        # Execute search
        with patch("time.time", side_effect=[1000.0, 1000.1]):
            results = await search_engine.search_library(library, query)

        # Should return empty results
        assert len(results.results) == 0
        assert results.total_chunks_searched == 0

    @pytest.mark.asyncio
    async def test_create_empty_results(self, search_engine, sample_library):
        """Test creation of empty search results."""
        query = SearchQuery(text="test query", algorithm=SearchAlgorithm.COSINE, limit=5)

        start_time = 1000.0
        with patch("time.time", return_value=1000.2):
            results = search_engine._create_empty_results(sample_library, query, start_time)

        assert len(results.results) == 0
        assert results.algorithm_used == SearchAlgorithm.COSINE
        assert results.execution_time == 0.2
        assert results.total_chunks_searched == 0
        assert results.library_id == sample_library.id
        assert results.query_text == "test query"
