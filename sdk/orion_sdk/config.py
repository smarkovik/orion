"""
Configuration settings for the Orion SDK.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrionConfig:
    """Configuration for the Orion SDK."""

    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout: int = 30
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    retry_attempts: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    user_agent: str = "orion-sdk/0.1.0"

    def __post_init__(self):
        """Load configuration from environment variables if not provided."""
        if not self.api_key:
            self.api_key = os.getenv("ORION_API_KEY")

        if base_url_env := os.getenv("ORION_BASE_URL"):
            self.base_url = base_url_env

        if timeout_env := os.getenv("ORION_TIMEOUT"):
            try:
                self.timeout = int(timeout_env)
            except ValueError:
                pass  # Keep default value

        self.base_url = self.base_url.rstrip("/")

    @property
    def headers(self) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def get_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"
