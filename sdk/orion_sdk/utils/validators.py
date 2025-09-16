"""
Input validation utilities for the Orion SDK.
"""

import re
from typing import Optional

from ..exceptions import ValidationError


class EmailValidator:
    """Validator for email addresses."""

    # Basic email regex pattern
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    @classmethod
    def validate_email(cls, email: str) -> None:
        """Validate an email address."""
        if not email:
            raise ValidationError("Email cannot be empty")

        if not isinstance(email, str):
            raise ValidationError("Email must be a string")

        email = email.strip()
        if not cls.EMAIL_PATTERN.match(email):
            raise ValidationError(f"Invalid email format: {email}")

    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        """Check if an email is valid without raising exceptions."""
        try:
            cls.validate_email(email)
            return True
        except ValidationError:
            return False


class QueryValidator:
    """Validator for search queries."""

    MIN_QUERY_LENGTH = 1
    MAX_QUERY_LENGTH = 1000

    @classmethod
    def validate_query(cls, query: str) -> None:
        """Validate a search query."""
        if not query:
            raise ValidationError("Query cannot be empty")

        if not isinstance(query, str):
            raise ValidationError("Query must be a string")

        query = query.strip()
        if len(query) < cls.MIN_QUERY_LENGTH:
            raise ValidationError(f"Query too short (minimum {cls.MIN_QUERY_LENGTH} characters)")

        if len(query) > cls.MAX_QUERY_LENGTH:
            raise ValidationError(f"Query too long (maximum {cls.MAX_QUERY_LENGTH} characters)")

    @classmethod
    def validate_algorithm(cls, algorithm: str, supported_algorithms: Optional[list] = None) -> None:
        """Validate a search algorithm."""
        if not algorithm:
            raise ValidationError("Algorithm cannot be empty")

        if not isinstance(algorithm, str):
            raise ValidationError("Algorithm must be a string")

        if supported_algorithms and algorithm not in supported_algorithms:
            supported = ", ".join(supported_algorithms)
            raise ValidationError(f"Unsupported algorithm: {algorithm}. Supported: {supported}")

    @classmethod
    def validate_limit(cls, limit: int, min_limit: int = 1, max_limit: int = 100) -> None:
        """Validate a result limit."""
        if not isinstance(limit, int):
            raise ValidationError("Limit must be an integer")

        if limit < min_limit:
            raise ValidationError(f"Limit too small (minimum {min_limit})")

        if limit > max_limit:
            raise ValidationError(f"Limit too large (maximum {max_limit})")
