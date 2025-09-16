"""
Exception classes for the Orion SDK.
"""

from typing import Any, Dict, Optional


class OrionSDKError(Exception):
    """Base exception for all Orion SDK errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DocumentUploadError(OrionSDKError):
    """Raised when document upload fails."""

    pass


class ProcessingTimeoutError(OrionSDKError):
    """Raised when document processing times out."""

    pass


class QueryError(OrionSDKError):
    """Raised when query execution fails."""

    pass


class ValidationError(OrionSDKError):
    """Raised when input validation fails."""

    pass


class APIError(OrionSDKError):
    """Raised when the API returns an error response."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_data: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        return f"API Error {self.status_code}: {self.message}"


class NetworkError(OrionSDKError):
    """Raised when network communication fails."""

    pass


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class NotFoundError(APIError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, 429)
