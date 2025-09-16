"""
Service for library management operations.
"""

from typing import List

from ..config import OrionConfig
from ..exceptions import QueryError, ValidationError
from ..models import Document, LibraryStats
from ..utils import EmailValidator, HTTPClient


class LibraryService:
    """Service for library management and statistics."""

    def __init__(self, config: OrionConfig):
        self.config = config
        self.http_client = HTTPClient(config)
        self.email_validator = EmailValidator()

    def get_stats(self, user_email: str) -> LibraryStats:
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
        self.email_validator.validate_email(user_email)

        try:
            response = self.http_client.get(f"/v1/query/library/{user_email}/stats")
            return LibraryStats.from_api_response(response)

        except Exception as e:
            raise QueryError(f"Failed to get library stats: {str(e)}")

    def list_documents(self, user_email: str) -> List[Document]:
        """
        List all documents in a user's library.

        Note: This is a placeholder method since the current Orion API
        doesn't have a document listing endpoint.

        Args:
            user_email: Email address of the user

        Returns:
            List of Document objects

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        # This is a placeholder implementation
        # In a real API, this would make a GET request to list documents
        raise NotImplementedError(
            "Document listing is not yet implemented in the Orion API. "
            "Use library statistics to get basic information about the library."
        )

    def delete_document(self, document_id: str, user_email: str) -> bool:
        """
        Delete a document from the library.

        Note: This is a placeholder method since the current Orion API
        doesn't have a document deletion endpoint.

        Args:
            document_id: ID of the document to delete
            user_email: Email address of the user

        Returns:
            True if deletion was successful

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        # This is a placeholder implementation
        # In a real API, this would make a DELETE request
        raise NotImplementedError("Document deletion is not yet implemented in the Orion API.")

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
