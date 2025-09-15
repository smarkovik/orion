"""Upload endpoint implementation."""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...core.config import settings
from ...core.converter import FileConverter
from ...core.logging import get_logger
from ...models.upload import UploadResponse

router = APIRouter()
logger = get_logger(__name__)


async def _validate_file_size(file: UploadFile) -> None:
    """Validate file size without loading entire file into memory."""
    if file.size is not None and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed: {settings.max_file_size // (1024*1024)}MB",
        )


async def _stream_file_to_disk(file: UploadFile, file_path: Path) -> int:
    """Stream file to disk and return total bytes written."""
    total_size = 0
    chunk_size = 8192  # 8KB chunks

    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            # Check if we're exceeding max file size during streaming
            total_size += len(chunk)
            if total_size > settings.max_file_size:
                # Clean up partial file
                file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size allowed: {settings.max_file_size // (1024*1024)}MB",
                )

            f.write(chunk)

    return total_size


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    description: Optional[str] = Form(None, description="Optional file description"),
) -> UploadResponse:
    """
    Upload a file using multipart/form-data.
    This endpoint accepts file uploads via standard HTTP multipart/form-data
    and saves them to the configured upload directory using streaming to avoid
    loading large files into memory.
    """
    try:
        # Validate file size if available in headers
        await _validate_file_size(file)

        file_id = str(uuid.uuid4())
        upload_dir = settings.upload_path
        converted_dir = settings.converted_path
        upload_dir.mkdir(parents=True, exist_ok=True)
        converted_dir.mkdir(parents=True, exist_ok=True)

        # Create unique filename to avoid conflicts
        original_filename = file.filename or "unknown_file"
        unique_filename = f"{file_id}_{original_filename}"
        file_path = upload_dir / unique_filename

        # Stream file to disk
        file_size = await _stream_file_to_disk(file, file_path)

        # Initialize converter and process file
        converter = FileConverter.from_settings()
        conversion_success, converted_path = converter.process_file(
            file_path, original_filename
        )

        event_data = {
            "filename": original_filename,
            "saved_as": unique_filename,
            "content_type": file.content_type,
            "file_size": file_size,
            "file_id": file_id,
            "file_path": str(file_path),
            "description": description,
            "converted": conversion_success,
            "converted_path": converted_path,
        }

        logger.info(
            f"File uploaded successfully: {original_filename} -> {unique_filename}. Converted: {conversion_success}",
            extra={"event_data": event_data},
        )

        return UploadResponse(
            message=(
                "File uploaded and processed successfully"
                if conversion_success
                else "File uploaded successfully"
            ),
            filename=original_filename,
            file_id=file_id,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            converted=conversion_success,
            converted_path=converted_path,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like file too large)
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during upload"
        )
