"""Background task functions for file processing."""

import json
from pathlib import Path
from typing import List

import cohere
import tiktoken

from .config import settings
from .converter import FileConverter
from .logging import get_logger
from .storage import StorageFactory

logger = get_logger(__name__)


async def convert_file_to_text(
    file_path: Path, email: str, file_id: str, original_filename: str
) -> None:
    try:

        logger.info(f"Starting text conversion for {email}: {file_id}")
        converter = FileConverter.from_settings(email)
        success, converted_path = converter.process_file(file_path, original_filename)
        if success:
            logger.info(
                f"Text conversion completed for {email}: {file_id} -> {converted_path}"
            )
            # next task in pipeline: chunk the text
            await chunk_text_file(Path(converted_path), email, file_id)
        else:
            logger.warning(f"Text conversion failed for {email}: {file_id}")
            raise (Exception(f"Text conversion failed for {email}: {file_id}"))
    except Exception as e:
        # TODO: Mark this file as failed, show to user as failed with a
        # message and a button to retry the conversion if reason is recoverable.
        # If reason is not recoverable, mark this file as failed - figure out product action.
        logger.error(
            f"Background text conversion error for {email}: {file_id} - {str(e)}"
        )


async def chunk_text_file(text_file_path: Path, email: str, file_id: str) -> None:
    try:
        logger.info(f"Starting text chunking for {email}: {file_id}")

        with open(text_file_path, "r", encoding="utf-8") as f:
            text_content = f.read()

        encoding = tiktoken.get_encoding(settings.tiktoken_encoding)
        chunks = _create_text_chunks(text_content, encoding)
        chunks_dir = settings.get_user_raw_chunks_path(email)
        chunks_dir.mkdir(parents=True, exist_ok=True)

        base_filename = text_file_path.stem
        chunk_files = []

        for i, chunk in enumerate(chunks):
            chunk_filename = f"{base_filename}_chunk_{i:03d}.txt"
            chunk_path = chunks_dir / chunk_filename

            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk)

            chunk_files.append(str(chunk_path))

        logger.info(
            f"Text chunking completed for {email}: {file_id}. Created {len(chunks)} chunks."
        )

        # Trigger next task in pipeline: generate embeddings
        await generate_embeddings(chunks_dir, email, file_id)

    except Exception as e:
        # TODO: Implement proper error handling and retry logic
        logger.error(f"Text chunking error for {email}: {file_id} - {str(e)}")
        raise


def _create_text_chunks(text: str, encoding) -> List[str]:
    """Create overlapping text chunks using tiktoken encoding."""
    tokens = encoding.encode(text)
    chunk_size = settings.chunk_size
    overlap_size = int(chunk_size * settings.chunk_overlap_percent)

    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end - overlap_size
        if end >= len(tokens):
            break

    return chunks


async def generate_embeddings(chunks_dir: Path, email: str, file_id: str) -> None:
    """Background task to generate vector embeddings from text chunks."""
    try:
        logger.info(f"Starting embedding generation for {email}: {file_id}")

        chunk_files = list(chunks_dir.glob("*.txt"))

        if not chunk_files:
            logger.warning(f"No chunk files found for {email}: {file_id}")
            return

        chunks_data = []
        for chunk_file in sorted(chunk_files):
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunk_text = f.read()
                chunks_data.append(
                    {
                        "filename": chunk_file.name,
                        "text": chunk_text,
                        "token_count": len(
                            tiktoken.get_encoding(settings.tiktoken_encoding).encode(
                                chunk_text
                            )
                        ),
                    }
                )

        logger.info(f"Read {len(chunks_data)} chunks for embedding generation.")

        if not settings.cohere_api_key:
            raise ValueError("COHERE_API_KEY not configured")

        cohere_client = cohere.Client(settings.cohere_api_key)

        # Extract texts for embedding
        texts = [chunk["text"] for chunk in chunks_data]

        logger.info(
            f"Calling Cohere API to generate embeddings for {len(texts)} chunks"
        )

        response = cohere_client.embed(
            texts=texts,
            model=settings.cohere_model,
            input_type="search_document",  # For RAG document embedding
        )

        embeddings_data = []
        for i, chunk in enumerate(chunks_data):
            embeddings_data.append(
                {
                    "filename": chunk["filename"],
                    "text": chunk["text"],
                    "token_count": chunk["token_count"],
                    "embedding": response.embeddings[i],
                    "embedding_model": settings.cohere_model,
                }
            )

        vectors_dir = settings.get_user_processed_vectors_path(email)
        storage = StorageFactory.create_storage(
            storage_type=settings.vector_storage_type, storage_path=vectors_dir
        )

        file_metadata = {
            "email": email,
            "file_id": file_id,
            "embedding_model": settings.cohere_model,
            "chunk_size": settings.chunk_size,
            "chunk_overlap_percent": settings.chunk_overlap_percent,
            "storage_type": settings.vector_storage_type,
        }

        saved_path = storage.save_embeddings(
            file_id=file_id, embeddings_data=embeddings_data, metadata=file_metadata
        )

        logger.info(
            f"Embedding generation completed for {email}: {file_id}. "
            f"Generated {len(embeddings_data)} embeddings using {settings.cohere_model}. "
            f"Saved to: {saved_path}"
        )

    except Exception as e:
        # TODO: Implement proper error handling and retry logic
        logger.error(f"Embedding generation error for {email}: {file_id} - {str(e)}")
        raise
