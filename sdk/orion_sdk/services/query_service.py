"""
Service for query and search operations.
"""

from typing import List

from ..config import OrionConfig
from ..exceptions import QueryError, ValidationError
from ..models import QueryResult, SearchResponse
from ..utils import EmailValidator, HTTPClient, QueryValidator


class QueryService:
    """Service for search and query operations."""

    def __init__(self, config: OrionConfig):
        self.config = config
        self.http_client = HTTPClient(config)
        self.email_validator = EmailValidator()
        self.query_validator = QueryValidator()

    def search(
        self,
        query: str,
        user_email: str,
        algorithm: str = "cosine",
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search for relevant document chunks.

        Args:
            query: Search query text
            user_email: Email address of the user
            algorithm: Search algorithm to use ("cosine" or "hybrid")
            limit: Maximum number of results to return

        Returns:
            SearchResponse with results and metadata

        Raises:
            ValidationError: If inputs are invalid
            QueryError: If search fails
        """
        self.query_validator.validate_query(query)
        self.email_validator.validate_email(user_email)
        self.query_validator.validate_limit(limit)

        try:
            supported_algorithms = self.get_supported_algorithms()
            self.query_validator.validate_algorithm(algorithm, supported_algorithms)
        except Exception:
            self.query_validator.validate_algorithm(algorithm)

        request_data = {
            "email": user_email,
            "query": query,
            "algorithm": algorithm,
            "limit": limit,
        }

        try:
            response = self.http_client.post("/v1/query", json=request_data)
            return SearchResponse.from_api_response(response)

        except Exception as e:
            raise QueryError(f"Search failed: {str(e)}")

    def get_supported_algorithms(self) -> List[str]:
        try:
            response = self.http_client.get("/v1/query/algorithms")
            return response  # API returns a list directly

        except Exception as e:
            raise QueryError(f"Failed to get supported algorithms: {str(e)}")

    def close(self) -> None:
        self.http_client.close()
