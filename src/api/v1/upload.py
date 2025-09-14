"""Upload endpoint implementation."""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...core.logging import get_logger
from ...models.upload import UploadResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    description: Optional[str] = Form(None, description="Optional file description"),
) -> UploadResponse:
    """
    Upload a file using multipart/form-data.
    This endpoint accepts file uploads via standard HTTP multipart/form-data
    and saves them to the /app/uploads directory.
    """
    try:
        file_id = str(uuid.uuid4())
        upload_dir = Path("/app/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        content = await file.read()
        file_size = len(content)

        # Create unique filename to avoid conflicts
        original_filename = file.filename or "unknown_file"
        unique_filename = f"{file_id}_{original_filename}"
        file_path = upload_dir / unique_filename

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(content)

        event_data = {
            "filename": original_filename,
            "saved_as": unique_filename,
            "content_type": file.content_type,
            "file_size": file_size,
            "file_id": file_id,
            "file_path": str(file_path),
            "description": description,
        }

        logger.info(
            f"File uploaded successfully: {original_filename} -> {unique_filename}",
            extra={"event_data": event_data},
        )

        return UploadResponse(
            message="File uploaded successfully",
            filename=original_filename,
            file_id=file_id,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during upload"
        )
