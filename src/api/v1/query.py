"""Query endpoint implementation."""

import asyncio
import json
import time
from fastapi import APIRouter, HTTPException

from ...models.query import QueryRequest, QueryResponse
from ...core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest) -> QueryResponse:
    """
    Execute a query (mock implementation).
    This endpoint simulates query execution by logging the event and returning
    a mock result with execution time.
    """
    try:
        start_time = time.time()
        event_data = {"query_body": request.body, "body_size": len(str(request.body))}
        logger.info("Query execution event", extra={"event_data": event_data})
        await asyncio.sleep(0.1)  # Mock processing delay
        execution_time_ms = int((time.time() - start_time) * 1000)
        mock_result = {
            "data": [
                {"id": 1, "name": "John Doe", "status": "active"},
                {"id": 2, "name": "Jane Smith", "status": "inactive"},
            ],
            "total": 2,
            "execution_time_ms": execution_time_ms,
        }
        return QueryResponse(
            result=json.dumps(mock_result),
            status="success",
            execution_time_ms=execution_time_ms,
        )
    except Exception as e:
        logger.error(f"Query execution failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during query execution"
        )
