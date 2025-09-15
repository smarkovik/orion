"""Upload endpoint implementation."""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from ...core.config import settings
from ...core.logging import get_logger
from ...models.upload import UploadResponse

router = APIRouter()
logger = get_logger(__name__)


async def convert_file_to_text(
    file_path: Path, email: str, file_id: str, original_filename: str
) -> None:
    """Background task to convert uploaded file to text."""
    try:
        from ...core.converter import FileConverter

        logger.info(f"Starting text conversion for {email}: {file_id}")

        # Create converter and process file
        converter = FileConverter.from_settings(email)
        success, converted_path = converter.process_file(file_path, original_filename)

        if success:
            logger.info(
                f"Text conversion completed for {email}: {file_id} -> {converted_path}"
            )
        else:
            logger.warning(f"Text conversion failed for {email}: {file_id}")

    except Exception as e:
        # here we should mark this file as failed, show to the user as failed with a
        # message and a button to retry the conversion if reason is recoverable.
        # if reason is not recoverable, we should mark this file as failed.
        logger.error(
            f"Background text conversion error for {email}: {file_id} - {str(e)}"
        )


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
            convert_file_to_text,
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
            "text_conversion_queued": True,
        }

        logger.info(
            f"File uploaded successfully for user {email}: {original_filename} -> {unique_filename}. Text conversion queued.",
            extra={"event_data": event_data},
        )

        return UploadResponse(
            message=f"File uploaded successfully to user folder: {email}. Text conversion started.",
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
        raise HTTPException(
            status_code=500, detail="Internal server error during upload"
        )
