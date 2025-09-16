"""
Repository for loading user libraries from storage.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from ..domain import Chunk, ChunkId, Document, DocumentId, Library, LibraryId, Vector
from ..search.interfaces import ILibraryRepository
from ..storage.factory import StorageFactory


class LibraryRepository(ILibraryRepository):
    """
    Repository implementation for loading user libraries.

    Loads documents and chunks from the file system and converts them
    to domain objects.
    """

    def __init__(self) -> None:
        self.settings = settings

    async def load_library(self, library_id: str) -> Library:
        """
        Load a complete library with all documents and chunks.

        Args:
            library_id: The user email identifying the library

        Returns:
            Library object with all documents and chunks loaded
        """
        lib_id = LibraryId(library_id)

        library = Library(
            id=lib_id,
            user_email=library_id,
            created_at=datetime.now(),  # We don't track creation time yet
            last_accessed=datetime.now(),
        )

        documents = await self._load_user_documents(library_id)
        for document in documents:
            library.add_document(document)

        return library

    async def library_exists(self, library_id: str) -> bool:
        """
        Check if a library exists for the given user.

        Args:
            library_id: The user email identifying the library

        Returns:
            True if the library exists, False otherwise
        """
        user_base_path = self.settings.get_user_base_path(library_id)
        return user_base_path.exists()

    async def _load_user_documents(self, user_email: str) -> List[Document]:
        documents: List[Document] = []

        uploads_path = self.settings.get_user_raw_uploads_path(user_email)
        vectors_path = self.settings.get_user_processed_vectors_path(user_email)

        if not uploads_path.exists() or not vectors_path.exists():
            return documents

        vector_files = list(vectors_path.glob("*_embeddings.json")) + list(vectors_path.glob("*_embeddings.h5"))

        for vector_file in vector_files:
            try:
                file_id = vector_file.stem.replace("_embeddings", "")
                document_id = DocumentId(file_id)

                document = await self._load_document(user_email, document_id, vector_file)
                if document:
                    documents.append(document)

            except Exception as e:
                # Log error but continue with other documents
                print(f"Error loading document {vector_file}: {e}")
                continue

        return documents

    async def _load_document(self, user_email: str, document_id: DocumentId, vector_file: Path) -> Optional[Document]:
        try:
            storage = StorageFactory.create_storage(
                storage_type="json" if vector_file.suffix == ".json" else "hdf5", storage_path=vector_file.parent
            )
            # Load embeddings to get metadata (get_metadata not in base interface)
            embeddings_data = storage.load_embeddings(str(document_id))

            uploads_path = self.settings.get_user_raw_uploads_path(user_email)
            uploaded_file = self._find_uploaded_file(uploads_path, str(document_id))

            if not uploaded_file:
                print(f"Could not find uploaded file for document {document_id}")
                return None

            metadata: Dict[str, Any] = {}
            if embeddings_data and len(embeddings_data) > 0:
                first_chunk = embeddings_data[0]
                metadata = {
                    "original_filename": first_chunk.get("original_filename", uploaded_file.name),
                    "content_type": first_chunk.get("content_type", "application/pdf"),
                }

            library_id = LibraryId(user_email)
            document = Document(
                id=document_id,
                library_id=library_id,
                original_filename=metadata.get("original_filename", uploaded_file.name),
                uploaded_filename=uploaded_file.name,
                content_type=metadata.get("content_type", "application/octet-stream"),
                file_size=uploaded_file.stat().st_size,
                upload_timestamp=datetime.fromtimestamp(uploaded_file.stat().st_mtime),
                metadata=metadata,
            )

            chunks = await self._load_document_chunks(document_id, vector_file)
            for chunk in chunks:
                document.add_chunk(chunk)

            return document

        except Exception as e:
            print(f"Error loading document {document_id}: {e}")
            return None

    def _find_uploaded_file(self, uploads_path: Path, file_id: str) -> Optional[Path]:
        for file_path in uploads_path.glob(f"{file_id}_*"):
            return file_path
        return None

    async def _load_document_chunks(self, document_id: DocumentId, vector_file: Path) -> List[Chunk]:
        """Load all chunks for a document from the vector file."""
        chunks = []

        try:
            # Load embeddings data
            storage = StorageFactory.create_storage(
                storage_type="json" if vector_file.suffix == ".json" else "hdf5", storage_path=vector_file.parent
            )

            embeddings_data = storage.load_embeddings(str(document_id))

            for embedding_data in embeddings_data:
                try:
                    chunk = self._create_chunk_from_embedding_data(document_id, embedding_data)
                    chunks.append(chunk)
                except Exception as e:
                    print(f"Error creating chunk from embedding data: {e}")
                    continue

        except Exception as e:
            print(f"Error loading chunks for document {document_id}: {e}")

        return chunks

    def _create_chunk_from_embedding_data(self, document_id: DocumentId, embedding_data: Dict[str, Any]) -> Chunk:
        """Create a Chunk object from embedding data."""
        filename = embedding_data["filename"]
        text = embedding_data["text"]
        token_count = embedding_data["token_count"]
        embedding_values = embedding_data["embedding"]
        embedding_model = embedding_data["embedding_model"]
        chunk_id = ChunkId.from_filename(filename)
        vector = Vector.from_list(embedding_values, embedding_model)

        chunk = Chunk(
            id=chunk_id,
            document_id=document_id,
            filename=filename,
            text=text,
            token_count=token_count,
            sequence_index=chunk_id.sequence,
            embedding=vector,
            embedding_model=embedding_model,
        )

        return chunk
