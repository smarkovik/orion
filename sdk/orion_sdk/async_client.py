"""
Async client for the Orion SDK.
"""

from pathlib import Path
from typing import List, Optional, Union

from .config import OrionConfig
from .models import Document, LibraryStats, SearchResponse


class AsyncOrionClient:
    """
    Async version of the Orion client.

    This client provides async methods for all operations,
    allowing for better performance in async applications.

    Example:
        async with AsyncOrionClient(base_url="http://localhost:8000") as client:
            # Upload multiple documents concurrently
            upload_tasks = [
                client.upload_document(f"./doc{i}.pdf", "user@example.com")
                for i in range(1, 4)
            ]

            documents = await asyncio.gather(*upload_tasks)

            # Search after all uploads complete
            response = await client.search(
                query="important findings",
                user_email="user@example.com"
            )
    """

    def __init__(
        self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None, timeout: int = 30, **kwargs
    ):
        """
        Initialize the async Orion client.

        Args:
            base_url: Base URL of the Orion API
            api_key: API key for authentication (optional)
            timeout: Request timeout in seconds
            **kwargs: Additional configuration options
        """
        self.config = OrionConfig(base_url=base_url, api_key=api_key, timeout=timeout, **kwargs)

        # TODO: Initialize async services
        # These would be async versions of the services with aiohttp
        self._document_service = None
        self._query_service = None
        self._library_service = None

    async def upload_document(
        self,
        file_path: Union[str, Path],
        user_email: str,
        description: Optional[str] = None,
        wait_for_processing: bool = False,
        processing_timeout: int = 300,
    ) -> Document:
        """
        Async upload a document for processing.

        Note: This is a placeholder implementation. In a real async SDK,
        this would use aiohttp for async HTTP requests.
        """
        raise NotImplementedError(
            "Async client is not yet fully implemented. "
            "This would require aiohttp and async versions of all services."
        )

    async def search(
        self,
        query: str,
        user_email: str,
        algorithm: str = "cosine",
        limit: int = 10,
    ) -> SearchResponse:
        """
        Async search for relevant document chunks.

        Note: This is a placeholder implementation.
        """
        raise NotImplementedError(
            "Async client is not yet fully implemented. "
            "This would require aiohttp and async versions of all services."
        )

    async def get_library_stats(self, user_email: str) -> LibraryStats:
        """
        Async get statistics about a user's document library.

        Note: This is a placeholder implementation.
        """
        raise NotImplementedError(
            "Async client is not yet fully implemented. "
            "This would require aiohttp and async versions of all services."
        )

    async def get_supported_algorithms(self) -> List[str]:
        """
        Async get list of supported search algorithms.

        Note: This is a placeholder implementation.
        """
        raise NotImplementedError(
            "Async client is not yet fully implemented. "
            "This would require aiohttp and async versions of all services."
        )

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        await self.close()

    async def close(self) -> None:
        """
        Close the async client and clean up resources.

        This should be called when you're done using the client
        to properly close async HTTP connections.
        """
        # TODO: Close async HTTP sessions
        pass

    @property
    def base_url(self) -> str:
        """Get the base URL of the API."""
        return self.config.base_url

    @property
    def timeout(self) -> int:
        """Get the request timeout."""
        return self.config.timeout
