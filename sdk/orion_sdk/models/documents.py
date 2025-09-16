"""
Document-related data models.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ProcessingStatus(Enum):
    """Processing status of a document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document:
    """Represents a document in the Orion system."""

    id: str
    filename: str
    user_email: str
    file_size: int
    content_type: str
    upload_timestamp: datetime
    processing_status: ProcessingStatus
    description: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_processed(self) -> bool:
        return self.processing_status == ProcessingStatus.COMPLETED

    @property
    def has_error(self) -> bool:
        return self.processing_status == ProcessingStatus.FAILED

    @property
    def is_processing(self) -> bool:
        return self.processing_status in (ProcessingStatus.PENDING, ProcessingStatus.PROCESSING)

    @classmethod
    def from_upload_response(
        cls, response_data: dict, user_email: str, description: Optional[str] = None
    ) -> "Document":
        return cls(
            id=response_data["file_id"],
            filename=response_data["filename"],
            user_email=user_email,
            file_size=response_data["file_size"],
            content_type=response_data["content_type"],
            upload_timestamp=datetime.now(),
            processing_status=ProcessingStatus.PROCESSING,  # Assume processing after upload
            description=description,
        )

    def __str__(self) -> str:
        return f"Document(id={self.id}, filename={self.filename}, status={self.processing_status.value})"

    def __repr__(self) -> str:
        return self.__str__()
