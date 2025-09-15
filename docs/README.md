# Orion Documentation

This directory contains comprehensive documentation for the Orion file processing system.

## Getting Started

For setup and deployment instructions, see the main [README.md](../README.md) in the project root.

## Architecture Documentation

### [File Upload Processing](file-upload-processing.md)

Complete workflow documentation covering:

- HTTP upload flow and validation
- File streaming and storage
- Background processing triggers
- Error handling and security
- Performance characteristics

### [Text Chunking & Storage](chunking-storage.md)

Detailed guide to text chunking strategy:

- Token-based chunking with tiktoken
- Overlapping chunk strategy
- File organization and naming
- Configuration options and performance tuning

### [Processing Pipeline](processing-pipeline.md)

Architecture overview of the processing pipeline:

- Pipeline orchestrator design
- Step-by-step processing flow
- Error handling and retry logic
- Performance monitoring and observability

### [Disk Storage & File Organization](disk-storage-organization.md)

File system organization and storage strategies:

- Directory structure and hierarchy
- File naming conventions
- Storage backends (JSON vs HDF5)
- Docker volume configuration
- Backup and recovery procedures

## Quick Reference

### File Processing Flow

```
Upload → Validation → Storage → Background Processing
                                       ↓
Vector Storage ← Embedding Generation ← Text Chunking ← File Conversion
```

### Directory Structure

```
/app/orion/{user_email}/
├── raw_uploads/          # Original files
├── processed_text/       # Converted text
├── raw_chunks/          # Text chunks
└── processed_vectors/   # Vector embeddings
```

### Key Configuration

- **Chunk Size**: 512 tokens (configurable)
- **Overlap**: 10% between chunks
- **Max File Size**: 50MB
- **Storage**: JSON (default) or HDF5
- **Embeddings**: Cohere embed-english-v3.0

## Development Notes

See [Notes.md](Notes.md) for additional development thoughts and considerations.

## API Documentation

Interactive API documentation is available when running the application:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
