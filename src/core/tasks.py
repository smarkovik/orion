"""Background task functions for file processing."""

from pathlib import Path

from .logging import get_logger
from .pipeline import PipelineContext
from .pipeline_factory import PipelineFactory

logger = get_logger(__name__)


async def process_file_with_pipeline(file_path: Path, email: str, file_id: str, original_filename: str) -> None:
    """Process file using the pipeline orchestrator."""
    try:
        context = PipelineContext(
            file_id=file_id,
            email=email,
            original_filename=original_filename,
            file_path=file_path,
        )

        pipeline = PipelineFactory.create_full_processing_pipeline()
        result = await pipeline.execute(context)

        logger.info(f"Pipeline execution completed for {email}: {file_id}")
        logger.info(f"Pipeline result: {result}")

    except Exception as e:
        logger.error(f"Pipeline execution failed for {email}: {file_id} - {str(e)}")
        raise
