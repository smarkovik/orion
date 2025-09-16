"""Models for the search query endpoint."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """Request model for search query endpoint."""

    email: str = Field(..., description="User email to identify the document library")
    query: str = Field(..., description="Search query text")
    algorithm: str = Field("cosine", description="Search algorithm: 'cosine' or 'hybrid'")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results to return")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "query": "machine learning algorithms",
                "algorithm": "cosine",
                "limit": 10,
            }
        }
    )


class ChunkResult(BaseModel):
    """Individual chunk search result."""

    chunk_filename: str = Field(..., description="Filename of the chunk")
    text: str = Field(..., description="Text content of the chunk")
    similarity_score: float = Field(..., description="Similarity score (0.0 to 1.0)")
    original_filename: str = Field(..., description="Original document filename")
    chunk_index: int = Field(..., description="Sequence index of chunk in document")
    document_id: str = Field(..., description="ID of the source document")
    rank: int = Field(..., description="Rank in search results (1-based)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_filename": "document_chunk_001.txt",
                "text": "Machine learning is a subset of artificial intelligence...",
                "similarity_score": 0.87,
                "original_filename": "ml_guide.pdf",
                "chunk_index": 1,
                "document_id": "a7f3e2d1-4b6c-4a8e-9f1d-2e3c4d5f6a7b",
                "rank": 1,
            }
        }
    )


class QueryResponse(BaseModel):
    """Response model for search query endpoint."""

    results: List[ChunkResult] = Field(..., description="List of search results")
    algorithm_used: str = Field(..., description="Search algorithm that was used")
    total_documents_searched: int = Field(..., description="Number of documents in the library")
    total_chunks_searched: int = Field(..., description="Number of chunks searched")
    execution_time: float = Field(..., description="Query execution time in seconds")
    query_text: str = Field(..., description="The original query text")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "chunk_filename": "document_chunk_001.txt",
                        "text": "Machine learning is a subset of artificial intelligence...",
                        "similarity_score": 0.87,
                        "original_filename": "ml_guide.pdf",
                        "chunk_index": 1,
                        "document_id": "a7f3e2d1-4b6c-4a8e-9f1d-2e3c4d5f6a7b",
                        "rank": 1,
                    }
                ],
                "algorithm_used": "cosine",
                "total_documents_searched": 5,
                "total_chunks_searched": 127,
                "execution_time": 0.234,
                "query_text": "machine learning algorithms",
            }
        }
    )
