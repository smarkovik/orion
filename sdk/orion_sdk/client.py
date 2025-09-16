"""
Main client for the Orion SDK.
"""

from pathlib import Path
from typing import List, Optional, Union

from .config import OrionConfig
from .models import Document, LibraryStats, QueryResult, SearchResponse
from .services import DocumentService, LibraryService, QueryService


class OrionClient:
    """
    Main client for interacting with the Orion API.

    Provides a simple, intuitive interface for document upload,
    processing, and querying operations.

    Example:
        client = OrionClient(base_url="http://localhost:8000")

        # Upload a document
        document = client.upload_document(
            file_path="./report.pdf",
            user_email="user@example.com",
            description="Quarterly report"
        )

        # Search for content
        response = client.search(
            query="machine learning algorithms",
            user_email="user@example.com"
        )

        for result in response.results:
            print(f"Score: {result.similarity_score:.3f} - {result.text[:100]}...")
    """

    def __init__(
        self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None, timeout: int = 30, **kwargs
    ):
        """
        Initialize the Orion client.

        Args:
            base_url: Base URL of the Orion API
            api_key: API key for authentication (optional)
            timeout: Request timeout in seconds
            **kwargs: Additional configuration options
        """
        self.config = OrionConfig(base_url=base_url, api_key=api_key, timeout=timeout, **kwargs)

        self._document_service = DocumentService(self.config)
        self._query_service = QueryService(self.config)
        self._library_service = LibraryService(self.config)

    def upload_document(
        self,
        file_path: Union[str, Path],
        user_email: str,
        description: Optional[str] = None,
        wait_for_processing: bool = False,
        processing_timeout: int = 300,
    ) -> Document:
        """
        Upload a document for processing.

        Args:
            file_path: Path to the file to upload
            user_email: Email address of the user
            description: Optional description for the document
            wait_for_processing: Whether to wait for processing to complete
            processing_timeout: Maximum time to wait for processing (seconds)

        Returns:
            Document object with upload information

        Raises:
            ValidationError: If inputs are invalid
            DocumentUploadError: If upload fails
            ProcessingTimeoutError: If processing times out
        """
        return self._document_service.upload(
            file_path=file_path,
            user_email=user_email,
            description=description,
            wait_for_processing=wait_for_processing,
            processing_timeout=processing_timeout,
        )

    def get_document_status(self, document_id: str, user_email: str) -> Document:
        """
        Get the processing status of a document.

        Note: This feature is not yet implemented in the Orion API.

        Args:
            document_id: ID of the document
            user_email: Email address of the user

        Returns:
            Document object with current status

        Raises:
            NotImplementedError: This feature is not yet available
        """
        return self._document_service.get_status(document_id, user_email)

    # Query Operations

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
        return self._query_service.search(
            query=query,
            user_email=user_email,
            algorithm=algorithm,
            limit=limit,
        )

    def get_supported_algorithms(self) -> List[str]:
        """
        Get list of supported search algorithms.

        Returns:
            List of algorithm names

        Raises:
            QueryError: If request fails
        """
        return self._query_service.get_supported_algorithms()

    # Library Operations

    def get_library_stats(self, user_email: str) -> LibraryStats:
        """
        Get statistics about a user's document library.

        Args:
            user_email: Email address of the user

        Returns:
            LibraryStats with library information

        Raises:
            ValidationError: If email is invalid
            QueryError: If request fails
        """
        return self._library_service.get_stats(user_email)

    def list_documents(self, user_email: str) -> List[Document]:
        """
        List all documents in a user's library.

        Note: This feature is not yet implemented in the Orion API.

        Args:
            user_email: Email address of the user

        Returns:
            List of Document objects

        Raises:
            NotImplementedError: This feature is not yet available
        """
        return self._library_service.list_documents(user_email)

    def delete_document(self, document_id: str, user_email: str) -> bool:
        """
        Delete a document from the library.

        Note: This feature is not yet implemented in the Orion API.

        Args:
            document_id: ID of the document to delete
            user_email: Email address of the user

        Returns:
            True if deletion was successful

        Raises:
            NotImplementedError: This feature is not yet available
        """
        return self._library_service.delete_document(document_id, user_email)

    # Context Manager Support

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        self.close()

    def close(self) -> None:
        """
        Close the client and clean up resources.

        This should be called when you're done using the client
        to properly close HTTP connections.
        """
        self._document_service.close()
        self._query_service.close()
        self._library_service.close()

    # Convenience Properties

    @property
    def base_url(self) -> str:
        return self.config.base_url

    @property
    def timeout(self) -> int:
        return self.config.timeout
