"""
File handling utilities for the Orion SDK.
"""

import mimetypes
from pathlib import Path
from typing import List, Optional

from ..exceptions import ValidationError


class FileValidator:
    """Validator for file uploads."""

    # Supported file extensions based on Orion's capabilities
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".json", ".xml"}

    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
        "application/json",
        "text/xml",
        "application/xml",
    }

    def __init__(self, max_file_size: int = 50 * 1024 * 1024):  # 50MB default
        self.max_file_size = max_file_size

    def validate_file(self, file_path: Path) -> None:
        """Validate a file for upload."""
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        if not file_path.exists():
            raise ValidationError(f"File does not exist: {file_path}")

        if not file_path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")

        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise ValidationError(f"File too large: {actual_mb:.1f}MB (max: {max_mb:.1f}MB)")

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            raise ValidationError(f"Unsupported file extension: {file_path.suffix}. Supported: {supported}")

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type not in self.SUPPORTED_MIME_TYPES:
            # Only warn for MIME type mismatches since extension check is more reliable
            pass

    def get_file_info(self, file_path: Path) -> dict:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        mime_type, _ = mimetypes.guess_type(str(file_path))
        file_size = file_path.stat().st_size

        return {
            "filename": file_path.name,
            "size": file_size,
            "size_mb": file_size / (1024 * 1024),
            "extension": file_path.suffix.lower(),
            "mime_type": mime_type,
            "is_supported": file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS,
        }

    def get_supported_extensions(self) -> List[str]:
        return sorted(list(self.SUPPORTED_EXTENSIONS))

    def is_supported_file(self, file_path: Path) -> bool:
        try:
            self.validate_file(file_path)
            return True
        except ValidationError:
            return False
