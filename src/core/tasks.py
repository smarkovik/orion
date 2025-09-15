"""Background task functions for file processing."""

from pathlib import Path

from .logging import get_logger

logger = get_logger(__name__)


async def convert_file_to_text(
    file_path: Path, email: str, file_id: str, original_filename: str
) -> None:
    """Background task to convert uploaded file to text.

    Given: A file has been uploaded and saved to raw_uploads
    When: This background task is executed
    Then: The file should be converted to text and saved to processed_text
    """
    try:
        from .converter import FileConverter

        logger.info(f"Starting text conversion for {email}: {file_id}")

        converter = FileConverter.from_settings(email)
        success, converted_path = converter.process_file(file_path, original_filename)

        if success:
            logger.info(
                f"Text conversion completed for {email}: {file_id} -> {converted_path}"
            )
        else:
            logger.warning(f"Text conversion failed for {email}: {file_id}")

    except Exception as e:
        # TODO: Mark this file as failed, show to user as failed with a
        # message and a button to retry the conversion if reason is recoverable.
        # If reason is not recoverable, mark this file as failed - figure out product action.
        logger.error(
            f"Background text conversion error for {email}: {file_id} - {str(e)}"
        )


async def chunk_text_file(text_file_path: Path, email: str, file_id: str) -> None:
    """Background task to chunk converted text into smaller pieces.

    Given: A text file has been created from document conversion
    When: This background task is executed
    Then: The text should be split into chunks and saved to raw_chunks
    """
    # TODO: Implement text chunking logic
    logger.info(f"Text chunking task queued for {email}: {file_id}")
    pass


async def generate_embeddings(chunks_dir: Path, email: str, file_id: str) -> None:
    """Background task to generate vector embeddings from text chunks.

    Given: Text chunks have been created
    When: This background task is executed
    Then: Vector embeddings should be generated and saved to processed_vectors
    """
    # TODO: Implement vector embedding generation
    logger.info(f"Vector embedding task queued for {email}: {file_id}")
    pass
