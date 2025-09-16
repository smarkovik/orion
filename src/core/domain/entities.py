"""
Domain entities for the Orion document processing system.

Entities are objects that have identity and can change over time.
They represent the core business objects in our domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .value_objects import ChunkId, DocumentId, LibraryId, Vector


@dataclass
class Chunk:
    """
    A piece of a document with text content and optional vector embedding.

    Chunks are created during the text chunking process and represent
    overlapping segments of the original document text.
    """

    id: ChunkId
    document_id: DocumentId
    filename: str  # e.g., "document_chunk_001.txt"
    text: str
    token_count: int
    sequence_index: int  # Position in document (0, 1, 2...)
    embedding: Optional[Vector] = None
    embedding_model: Optional[str] = None

    def __post_init__(self) -> None:
        if self.token_count < 0:
            raise ValueError("Token count must be non-negative")

        if self.sequence_index < 0:
            raise ValueError("Sequence index must be non-negative")

        if self.id.sequence != self.sequence_index:
            raise ValueError(
                f"ChunkId sequence ({self.id.sequence}) must match " f"sequence_index ({self.sequence_index})"
            )

    def has_embedding(self) -> bool:
        """Check if this chunk has an embedding."""
        return self.embedding is not None

    def similarity_to(self, other_vector: Vector) -> float:
        """Calculate similarity to another vector."""
        if not self.has_embedding():
            raise ValueError("Cannot calculate similarity: chunk has no embedding")

        assert self.embedding is not None  # Already checked in has_embedding()
        return self.embedding.cosine_similarity(other_vector)

    def get_embedding_dimension(self) -> Optional[int]:
        """Get the dimension of the embedding if it exists."""
        return self.embedding.dimension if self.embedding else None


@dataclass
class Document:
    """
    A complete document with metadata and associated chunks.

    Documents represent the original files uploaded by users,
    along with all the chunks created during processing.
    """

    id: DocumentId
    library_id: LibraryId
    original_filename: str  # e.g., "report.pdf"
    uploaded_filename: str  # e.g., "uuid_report.pdf"
    content_type: str  # MIME type
    file_size: int  # Bytes
    upload_timestamp: datetime
    chunks: List[Chunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.file_size < 0:
            raise ValueError("File size must be non-negative")

        if not self.original_filename.strip():
            raise ValueError("Original filename cannot be empty")

        if not self.content_type.strip():
            raise ValueError("Content type cannot be empty")

    def add_chunk(self, chunk: Chunk) -> None:
        """Add a chunk to this document."""
        if chunk.document_id != self.id:
            raise ValueError(f"Chunk document_id ({chunk.document_id}) does not match " f"document id ({self.id})")

        document_base_name = self.get_base_filename()
        if not chunk.filename.startswith(document_base_name):
            # Skip chunks that don't belong to this document (handles corrupted embeddings files)
            return

        existing_sequences = {c.sequence_index for c in self.chunks}
        if chunk.sequence_index in existing_sequences:
            # Skip duplicate chunks instead of failing (handles corrupted embeddings files)
            return

        self.chunks.append(chunk)
        # Keep chunks sorted by sequence index
        self.chunks.sort(key=lambda c: c.sequence_index)

    def get_chunk_count(self) -> int:
        """Get the total number of chunks."""
        return len(self.chunks)

    def get_chunks_with_embeddings(self) -> List[Chunk]:
        """Get only chunks that have embeddings."""
        return [chunk for chunk in self.chunks if chunk.has_embedding()]

    def get_chunk_by_sequence(self, sequence: int) -> Optional[Chunk]:
        """Get a chunk by its sequence index."""
        for chunk in self.chunks:
            if chunk.sequence_index == sequence:
                return chunk
        return None

    def get_total_token_count(self) -> int:
        """Get the total token count across all chunks."""
        return sum(chunk.token_count for chunk in self.chunks)

    def has_embeddings(self) -> bool:
        """Check if this document has any chunks with embeddings."""
        return any(chunk.has_embedding() for chunk in self.chunks)

    def get_base_filename(self) -> str:
        """Get the base filename without extension."""
        # Remove extension from original filename
        parts = self.original_filename.rsplit(".", 1)
        return parts[0] if len(parts) > 1 else self.original_filename


@dataclass
class Library:
    """
    A user's collection of documents.

    The Library is the aggregate root that manages all documents
    for a specific user, providing search and organization capabilities.
    """

    id: LibraryId
    user_email: str
    documents: Dict[DocumentId, Document] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.id.email != self.user_email:
            raise ValueError(f"LibraryId email ({self.id.email}) must match " f"user_email ({self.user_email})")

    def add_document(self, document: Document) -> None:
        """Add a document to the library."""
        if document.library_id != self.id:
            raise ValueError(f"Document library_id ({document.library_id}) does not match " f"library id ({self.id})")

        if document.id in self.documents:
            raise ValueError(f"Document with id {document.id} already exists")

        self.documents[document.id] = document
        self.last_accessed = datetime.now()

    def remove_document(self, document_id: DocumentId) -> bool:
        """Remove a document from the library. Returns True if removed."""
        if document_id in self.documents:
            del self.documents[document_id]
            self.last_accessed = datetime.now()
            return True
        return False

    def get_document(self, document_id: DocumentId) -> Optional[Document]:
        """Get a document by its ID."""
        return self.documents.get(document_id)

    def find_document_by_filename(self, filename: str) -> Optional[Document]:
        """Find a document by its original filename."""
        for document in self.documents.values():
            if document.original_filename == filename:
                return document
        return None

    def get_all_documents(self) -> List[Document]:
        """Get all documents in the library."""
        return list(self.documents.values())

    def get_all_chunks(self) -> List[Chunk]:
        """Get all chunks from all documents in the library."""
        chunks = []
        for document in self.documents.values():
            chunks.extend(document.chunks)
        return chunks

    def get_chunks_with_embeddings(self) -> List[Chunk]:
        """Get all chunks that have embeddings from all documents."""
        chunks = []
        for document in self.documents.values():
            chunks.extend(document.get_chunks_with_embeddings())
        return chunks

    def get_document_count(self) -> int:
        """Get the total number of documents."""
        return len(self.documents)

    def get_total_chunk_count(self) -> int:
        """Get the total number of chunks across all documents."""
        return sum(doc.get_chunk_count() for doc in self.documents.values())

    def get_total_file_size(self) -> int:
        """Get the total file size of all documents in bytes."""
        return sum(doc.file_size for doc in self.documents.values())

    def has_documents_with_embeddings(self) -> bool:
        """Check if any documents in the library have embeddings."""
        return any(doc.has_embeddings() for doc in self.documents.values())

    def update_last_accessed(self) -> None:
        """Update the last accessed timestamp."""
        self.last_accessed = datetime.now()
