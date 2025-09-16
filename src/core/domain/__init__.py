"""
Domain models for Orion document processing and search system.

This module contains the core domain entities and value objects that represent
the business concepts of the system:
- Chunk: A piece of a document with text and embeddings
- Document: A complete document with metadata and chunks
- Library: A user's collection of documents
"""

from .entities import Chunk, Document, Library
from .value_objects import ChunkId, DocumentId, LibraryId, Vector

__all__ = [
    "ChunkId",
    "DocumentId",
    "LibraryId",
    "Vector",
    "Chunk",
    "Document",
    "Library",
]
