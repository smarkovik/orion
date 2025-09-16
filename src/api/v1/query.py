"""Search query endpoint implementation."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ...core.logging import get_logger
from ...core.repositories import LibraryRepository
from ...core.services import CohereEmbeddingService, LibrarySearchEngine, QueryService
from ...models.query import ChunkResult, QueryRequest, QueryResponse

router = APIRouter()
logger = get_logger(__name__)

embedding_service = CohereEmbeddingService()
library_repository = LibraryRepository()
search_engine = LibrarySearchEngine(embedding_service)
query_service = QueryService(library_repository, search_engine, embedding_service)


@router.post("/query", response_model=QueryResponse)
async def search_documents(request: QueryRequest) -> QueryResponse:
    """
    Search for relevant document chunks in a user's library.

    This endpoint performs semantic search across all documents in a user's library,
    returning the most relevant chunks based on the specified algorithm.
    """
    try:
        event_data = {
            "user_email": request.email,
            "query_text": request.query,
            "algorithm": request.algorithm,
            "limit": request.limit,
        }
        logger.info("Search query received", extra={"event_data": event_data})

        search_results = await query_service.execute_query(
            user_email=request.email, query_text=request.query, algorithm=request.algorithm, limit=request.limit
        )

        library = await library_repository.load_library(request.email)

        chunk_results = []
        for result in search_results.results:
            chunk = result.chunk
            document_id = str(chunk.document_id)

            document = library.get_document(chunk.document_id)
            original_filename = document.original_filename if document else "unknown"

            chunk_result = ChunkResult(
                chunk_filename=chunk.filename,
                text=chunk.text,
                similarity_score=result.similarity_score,
                original_filename=original_filename,
                chunk_index=chunk.sequence_index,
                document_id=document_id,
                rank=result.rank,
            )
            chunk_results.append(chunk_result)

        response = QueryResponse(
            results=chunk_results,
            algorithm_used=search_results.get_algorithm_name(),
            total_documents_searched=library.get_document_count(),
            total_chunks_searched=search_results.total_chunks_searched,
            execution_time=search_results.execution_time,
            query_text=search_results.query_text,
        )

        logger.info(
            "Search completed successfully",
            extra={
                "event_data": {
                    **event_data,
                    "results_count": len(chunk_results),
                    "execution_time": search_results.execution_time,
                }
            },
        )

        return response

    except ValueError as e:
        # Client error (bad request)
        logger.warning(f"Invalid search request: {str(e)}", extra={"event_data": event_data})
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Server error
        logger.error(f"Search execution failed: {str(e)}", extra={"event_data": event_data})
        raise HTTPException(status_code=500, detail="Internal server error during search")


@router.get("/query/algorithms")
async def get_supported_algorithms() -> List[str]:
    try:
        algorithms = query_service.get_supported_algorithms()
        return algorithms
    except Exception as e:
        logger.error(f"Failed to get supported algorithms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/query/library/{email}/stats")
async def get_library_stats(email: str) -> Dict[str, Any]:
    try:
        stats = await query_service.get_library_stats(email)
        return stats
    except Exception as e:
        logger.error(f"Failed to get library stats for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
