"""Models for the query endpoint."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    body: Dict[str, Any] = Field(
        ..., description="Query body with flexible JSON structure"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "body": {
                    "query": "SELECT * FROM users WHERE active = true",
                    "filters": {"status": "active"},
                    "limit": 100,
                }
            }
        }
    )


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    result: str = Field(..., description="Query result as JSON string")
    status: str = Field(..., description="Query execution status")
    execution_time_ms: int = Field(
        ..., description="Query execution time in milliseconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": (
                    '{"data": [{"id": 1, "name": "John"}, '
                    '{"id": 2, "name": "Jane"}]}'
                ),
                "status": "success",
                "execution_time_ms": 150,
            }
        }
    )
