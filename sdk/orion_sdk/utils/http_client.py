"""
HTTP client utilities for the Orion SDK.
"""

import time
from typing import Any, Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import OrionConfig
from ..exceptions import APIError, AuthenticationError, NetworkError, NotFoundError, RateLimitError


class HTTPClient:
    """HTTP client with built-in retry logic and error handling."""

    def __init__(self, config: OrionConfig):
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a configured requests session."""
        session = requests.Session()
        session.headers.update(self.config.headers)

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            response_data = response.json() if response.content else {}
        except ValueError:
            response_data = {}

        if response.status_code == 200 or response.status_code == 201:
            return response_data

        if response.status_code == 401:
            raise AuthenticationError(response_data.get("detail", "Authentication failed"))
        elif response.status_code == 404:
            raise NotFoundError(response_data.get("detail", "Resource not found"))
        elif response.status_code == 429:
            raise RateLimitError(response_data.get("detail", "Rate limit exceeded"))
        elif 400 <= response.status_code < 500:
            raise APIError(
                response_data.get("detail", f"Client error: {response.status_code}"),
                response.status_code,
                response_data,
            )
        elif 500 <= response.status_code < 600:
            raise APIError(
                response_data.get("detail", f"Server error: {response.status_code}"),
                response.status_code,
                response_data,
            )
        else:
            raise APIError(f"Unexpected response: {response.status_code}", response.status_code, response_data)

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        url = self.config.get_url(endpoint)
        try:
            response = self.session.get(url, params=params, timeout=self.config.timeout, verify=self.config.verify_ssl)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during GET request: {str(e)}")

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request."""
        url = self.config.get_url(endpoint)
        try:
            response = self.session.post(
                url, data=data, json=json, files=files, timeout=self.config.timeout, verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during POST request: {str(e)}")

    def put(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a PUT request."""
        url = self.config.get_url(endpoint)
        try:
            response = self.session.put(
                url, data=data, json=json, timeout=self.config.timeout, verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during PUT request: {str(e)}")

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        url = self.config.get_url(endpoint)
        try:
            response = self.session.delete(url, timeout=self.config.timeout, verify=self.config.verify_ssl)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during DELETE request: {str(e)}")

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
