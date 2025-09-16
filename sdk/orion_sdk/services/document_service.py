"""
Service for document-related operations.
"""

import time
from pathlib import Path
from typing import Optional, Union

from ..config import OrionConfig
from ..exceptions import DocumentUploadError, ProcessingTimeoutError, ValidationError
from ..models import Document, ProcessingStatus
from ..utils import EmailValidator, FileValidator, HTTPClient


class DocumentService:

    def __init__(self, config: OrionConfig):
        self.config = config
        self.http_client = HTTPClient(config)
        self.file_validator = FileValidator(config.max_file_size)
        self.email_validator = EmailValidator()

    def upload(
        self,
        file_path: Union[str, Path],
        user_email: str,
        description: Optional[str] = None,
        wait_for_processing: bool = False,
        processing_timeout: int = 300,
    ) -> Document:
        """
        Upload a document to Orion.

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
            ProcessingTimeoutError: If processing times out (when wait_for_processing=True)
        """
        file_path = Path(file_path)

        self.file_validator.validate_file(file_path)
        self.email_validator.validate_email(user_email)

        try:
            with open(file_path, "rb") as file:
                files = {"file": file}
                data = {"email": user_email}
                if description:
                    data["description"] = description

                response = self.http_client.post("/v1/upload", files=files, data=data)

        except Exception as e:
            raise DocumentUploadError(f"Failed to upload document: {str(e)}")

        document = Document.from_upload_response(response, user_email, description)

        if wait_for_processing:
            document = self._wait_for_processing(document, processing_timeout)

        return document

    def get_status(self, document_id: str, user_email: str) -> Document:
        """
        Get the current status of a document.

        Note: This is a placeholder method since the current Orion API
        doesn't have a status endpoint. In a real implementation, this
        would query the document status.

        Args:
            document_id: ID of the document
            user_email: Email address of the user

        Returns:
            Document object with current status
        """
        # This is a placeholder implementation
        # In a real API, this would make a GET request to get document status
        raise NotImplementedError(
            "Document status checking is not yet implemented in the Orion API. "
            "Use library statistics to check if documents are processed."
        )

    def _wait_for_processing(self, document: Document, timeout: int) -> Document:
        """
        Wait for document processing to complete.

        Args:
            document: Document to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Updated document with final status

        Raises:
            ProcessingTimeoutError: If processing takes too long
        """
        start_time = time.time()
        poll_interval = 2  # Poll every 2 seconds

        while time.time() - start_time < timeout:
            try:
                # Try to get updated status
                # For now, we'll simulate this by checking library stats
                # In a real implementation, there would be a status endpoint

                # TODO: Implement actual status checking when API supports it
                time.sleep(poll_interval)

                # For now, assume processing completes after a reasonable time
                if time.time() - start_time > 30:  # Assume 30 seconds is enough
                    document.processing_status = ProcessingStatus.COMPLETED
                    return document

            except Exception:
                # Continue polling if there are transient errors
                time.sleep(poll_interval)
                continue

        # Timeout reached
        raise ProcessingTimeoutError(f"Document processing timed out after {timeout} seconds")

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
