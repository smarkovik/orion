"""Models for the upload endpoint."""

from typing import Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response model for file upload."""

    message: str = Field(..., description="Success message")
    filename: str = Field(..., description="Name of the uploaded file")
    file_id: str = Field(..., description="Unique identifier for an uploaded file")
    file_size: int = Field(..., description="Size of the uploaded file in bytes")
    content_type: str = Field(..., description="MIME type of the uploaded file")
    converted: bool = Field(default=False, description="Whether the file was converted")
    converted_path: Optional[str] = Field(
        default=None, description="Path to converted file if conversion was successful"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "File uploaded successfully",
                "filename": "document.pdf",
                "file_id": "uuid-1234-5678-9012",
                "file_size": 1024000,
                "content_type": "application/pdf",
            }
        }
