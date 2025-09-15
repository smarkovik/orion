"""Upload endpoint implementation."""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from ...core.config import settings
from ...core.logging import get_logger
from ...core.tasks import process_file_with_pipeline
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

            total_size += len(chunk)
            if total_size > settings.max_file_size:
                # Clean up if file is rejected
                file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size allowed: {settings.max_file_size // (1024*1024)}MB",
                )

            f.write(chunk)

    return total_size


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    email: str = Form(..., description="User email address"),
    description: Optional[str] = Form(None, description="Optional file description"),
) -> UploadResponse:
    """
    Upload a file using multipart/form-data.
    This endpoint accepts file uploads via standard HTTP multipart/form-data
    and saves them to the user's raw_uploads directory using streaming to avoid
    loading large files into memory.
    """
    try:
        await _validate_file_size(file)

        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(status_code=400, detail="Invalid email format")

        file_id = str(uuid.uuid4())

        settings.create_user_directories(email)
        user_raw_uploads_dir = settings.get_user_raw_uploads_path(email)

        original_filename = file.filename or "unknown_file"
        unique_filename = f"{file_id}_{original_filename}"
        file_path = user_raw_uploads_dir / unique_filename

        file_size = await _stream_file_to_disk(file, file_path)

        background_tasks.add_task(
            process_file_with_pipeline,
            file_path=file_path,
            email=email,
            file_id=file_id,
            original_filename=original_filename,
        )

        event_data = {
            "filename": original_filename,
            "saved_as": unique_filename,
            "content_type": file.content_type,
            "file_size": file_size,
            "file_id": file_id,
            "file_path": str(file_path),
            "user_email": email,
            "description": description,
            "pipeline_processing_queued": True,
        }

        logger.info(
            f"File uploaded successfully for user {email}: {original_filename} -> "
            f"{unique_filename}. Pipeline processing queued.",
            extra={"event_data": event_data},
        )

        return UploadResponse(
            message=f"File uploaded successfully to user folder: {email}. Pipeline processing started.",
            filename=original_filename,
            file_id=file_id,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            converted=False,  # Will be converted in background
            converted_path=None,  # Will be available after conversion
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like file too large)
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")
