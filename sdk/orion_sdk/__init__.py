"""
Orion SDK - Python client for the Orion document processing and search API.

This SDK provides a simple, intuitive interface for uploading documents,
processing them through the Orion pipeline, and performing semantic search
queries on the processed content.
"""

from .async_client import AsyncOrionClient
from .client import OrionClient
from .config import OrionConfig
from .exceptions import (
    APIError,
    DocumentUploadError,
    OrionSDKError,
    ProcessingTimeoutError,
    QueryError,
    ValidationError,
)
from .models import Document, LibraryStats, ProcessingStatus, QueryResult, SearchResponse

__version__ = "0.1.0"
__author__ = "Orion Team"
__email__ = "support@orion.ai"

__all__ = [
    # Main clients
    "OrionClient",
    "AsyncOrionClient",
    # Configuration
    "OrionConfig",
    # Exceptions
    "OrionSDKError",
    "DocumentUploadError",
    "ProcessingTimeoutError",
    "QueryError",
    "ValidationError",
    "APIError",
    # Models
    "Document",
    "QueryResult",
    "SearchResponse",
    "LibraryStats",
    "ProcessingStatus",
    # Metadata
    "__version__",
]
