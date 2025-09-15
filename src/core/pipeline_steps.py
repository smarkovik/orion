"""Concrete pipeline steps for file processing workflows."""

from pathlib import Path
from typing import Any, List

import cohere
import tiktoken

from .config import settings
from .converter import FileConverter
from .logging import get_logger
from .pipeline import PipelineContext, PipelineStep, StepResult, StepStatus, pipeline_registry
from .storage import StorageFactory

logger = get_logger(__name__)


class FileConversionStep(PipelineStep):
    """Convert uploaded file to text format."""

    def __init__(self) -> None:
        super().__init__(
            name="file_conversion",
            description="Convert uploaded file to text format",
            retry_count=2,
        )

    async def execute(self, context: PipelineContext) -> StepResult:
        """Convert file to text."""
        try:
            converter = FileConverter.from_settings(context.email)
            success, converted_path = converter.process_file(context.file_path, context.original_filename)

            if success and converted_path:
                context.metadata["converted_text_path"] = converted_path
                return StepResult(
                    status=StepStatus.SUCCESS,
                    message=f"File converted successfully to {converted_path}",
                    data={"converted_path": converted_path},
                )
            else:
                return StepResult(
                    status=StepStatus.FAILED,
                    message="File conversion failed",
                    error="Converter returned failure status",
                )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                message="File conversion failed with exception",
                error=str(e),
            )


class TextChunkingStep(PipelineStep):
    """Chunk text into smaller pieces for embedding."""

    def __init__(self) -> None:
        super().__init__(
            name="text_chunking",
            description="Split text into chunks for embedding generation",
            retry_count=1,
        )

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if no converted text path available."""
        return "converted_text_path" not in context.metadata

    async def execute(self, context: PipelineContext) -> StepResult:
        """Chunk the converted text."""
        try:
            text_file_path = Path(context.metadata["converted_text_path"])

            if not text_file_path.exists():
                return StepResult(
                    status=StepStatus.FAILED,
                    message="Converted text file not found",
                    error=f"File does not exist: {text_file_path}",
                )

            with open(text_file_path, "r", encoding="utf-8") as f:
                text_content = f.read()

            encoding = tiktoken.get_encoding(settings.tiktoken_encoding)
            chunks = self._create_text_chunks(text_content, encoding)

            chunks_dir = settings.get_user_raw_chunks_path(context.email)
            chunks_dir.mkdir(parents=True, exist_ok=True)

            base_filename = text_file_path.stem
            chunk_files = []

            for i, chunk in enumerate(chunks):
                chunk_filename = f"{base_filename}_chunk_{i:03d}.txt"
                chunk_path = chunks_dir / chunk_filename

                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk)

                chunk_files.append(str(chunk_path))

            context.metadata["chunks_dir"] = str(chunks_dir)
            context.metadata["chunk_count"] = len(chunks)

            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Text chunked into {len(chunks)} pieces",
                data={
                    "chunks_dir": str(chunks_dir),
                    "chunk_count": len(chunks),
                    "chunk_files": chunk_files,
                },
            )

        except Exception as e:
            return StepResult(status=StepStatus.FAILED, message="Text chunking failed", error=str(e))

    def _create_text_chunks(self, text: str, encoding: Any) -> List[str]:
        """Create overlapping text chunks using tiktoken encoding."""
        tokens = encoding.encode(text)
        chunk_size = settings.chunk_size
        overlap_size = int(chunk_size * settings.chunk_overlap_percent)

        chunks = []
        start = 0

        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end >= len(tokens):
                break

            start = end - overlap_size

        return chunks


class EmbeddingGenerationStep(PipelineStep):
    """Generate embeddings for text chunks using Cohere API."""

    def __init__(self) -> None:
        super().__init__(
            name="embedding_generation",
            description="Generate embeddings using Cohere API",
            retry_count=3,  # API calls can be flaky
        )

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if no chunks directory available."""
        return "chunks_dir" not in context.metadata

    def can_retry(self, attempt: int, error: Exception) -> bool:
        """Retry on network/API errors, but not on auth errors."""
        if "api key" in str(error).lower() or "unauthorized" in str(error).lower():
            return False
        return super().can_retry(attempt, error)

    async def execute(self, context: PipelineContext) -> StepResult:
        """Generate embeddings for all chunks."""
        try:
            chunks_dir = Path(context.metadata["chunks_dir"])

            if not chunks_dir.exists():
                return StepResult(
                    status=StepStatus.FAILED,
                    message="Chunks directory not found",
                    error=f"Directory does not exist: {chunks_dir}",
                )

            chunk_files = list(chunks_dir.glob("*.txt"))
            if not chunk_files:
                return StepResult(
                    status=StepStatus.FAILED,
                    message="No chunk files found",
                    error=f"No .txt files in {chunks_dir}",
                )

            chunks_data = []
            for chunk_file in sorted(chunk_files):
                with open(chunk_file, "r", encoding="utf-8") as f:
                    chunk_text = f.read()

                chunks_data.append(
                    {
                        "filename": chunk_file.name,
                        "text": chunk_text,
                        "token_count": len(tiktoken.get_encoding(settings.tiktoken_encoding).encode(chunk_text)),
                    }
                )

            if not settings.cohere_api_key:
                return StepResult(
                    status=StepStatus.FAILED,
                    message="Cohere API key not configured",
                    error="COHERE_API_KEY environment variable not set",
                )

            cohere_client = cohere.Client(settings.cohere_api_key)
            texts = [str(chunk["text"]) for chunk in chunks_data]

            response = cohere_client.embed(
                texts=texts,
                model=settings.cohere_model,
                input_type="search_document",
            )

            if hasattr(response, "embeddings") and response.embeddings:
                response_embeddings = list(response.embeddings)
            else:
                return StepResult(
                    status=StepStatus.FAILED,
                    message="Invalid response from Cohere API",
                    error="No embeddings in API response",
                )

            embeddings_data = []
            for i, chunk in enumerate(chunks_data):
                embeddings_data.append(
                    {
                        "filename": chunk["filename"],
                        "text": chunk["text"],
                        "token_count": chunk["token_count"],
                        "embedding": response_embeddings[i],
                        "embedding_model": settings.cohere_model,
                    }
                )

            context.metadata["embeddings_data"] = embeddings_data
            context.metadata["embedding_count"] = len(embeddings_data)

            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Generated {len(embeddings_data)} embeddings using {settings.cohere_model}",
                data={
                    "embedding_count": len(embeddings_data),
                    "model": settings.cohere_model,
                },
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                message="Embedding generation failed",
                error=str(e),
            )


class VectorStorageStep(PipelineStep):
    """Store embeddings in the configured vector storage."""

    def __init__(self) -> None:
        super().__init__(
            name="vector_storage",
            description="Store embeddings in vector database",
            retry_count=2,
        )

    def should_skip(self, context: PipelineContext) -> bool:
        """Skip if no embeddings data available."""
        return "embeddings_data" not in context.metadata

    async def execute(self, context: PipelineContext) -> StepResult:
        """Store embeddings in the configured storage."""
        try:
            embeddings_data = context.metadata["embeddings_data"]

            vectors_dir = settings.get_user_processed_vectors_path(context.email)
            storage = StorageFactory.create_storage(storage_type=settings.vector_storage_type, storage_path=vectors_dir)

            file_metadata = {
                "email": context.email,
                "file_id": context.file_id,
                "original_filename": context.original_filename,
                "embedding_model": settings.cohere_model,
                "chunk_size": settings.chunk_size,
                "chunk_overlap_percent": settings.chunk_overlap_percent,
                "storage_type": settings.vector_storage_type,
                "pipeline_execution": True,
            }

            saved_path = storage.save_embeddings(
                file_id=context.file_id,
                embeddings_data=embeddings_data,
                metadata=file_metadata,
            )

            context.metadata["storage_path"] = str(saved_path)

            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Embeddings stored successfully at {saved_path}",
                data={
                    "storage_path": str(saved_path),
                    "storage_type": settings.vector_storage_type,
                    "embedding_count": len(embeddings_data),
                },
            )

        except Exception as e:
            return StepResult(status=StepStatus.FAILED, message="Vector storage failed", error=str(e))


pipeline_registry.register_step(FileConversionStep)
pipeline_registry.register_step(TextChunkingStep)
pipeline_registry.register_step(EmbeddingGenerationStep)
pipeline_registry.register_step(VectorStorageStep)
