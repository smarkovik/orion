# File Upload Processing Flow

This document describes the complete file upload and processing workflow in Orion, from the initial HTTP request to final vector storage.

## Overview

Orion processes files through a multi-stage pipeline that converts documents into searchable vector embeddings. The system supports various file formats and provides user-based file organization.

## Upload Flow

### 1. HTTP Upload Request

**Endpoint**: `POST /v1/upload`

**Request Format**: `multipart/form-data`

**Required Fields**:

- `file`: The document to upload
- `email`: User email (creates user-specific storage)

**Optional Fields**:

- `description`: File description for metadata

```bash
curl -X POST http://localhost:8000/v1/upload \
  -F "file=@document.pdf" \
  -F "email=user@domain.com" \
  -F "description=Important document"
```

### 2. File Validation

The system performs several validation checks:

#### Size Validation

- **Maximum Size**: 50MB (configurable via `MAX_FILE_SIZE`)
- **Streaming Validation**: File size is checked during streaming to avoid memory overflow
- **Early Termination**: Upload is terminated if size limit is exceeded

#### Email Validation

- **Format Check**: Basic email format validation (`@` and `.` validation)
- **User Directory Creation**: Creates user-specific directory structure

#### File Type Detection

- **MIME Type Detection**: Uses `python-magic` library for accurate file type detection
- **Extension Fallback**: Falls back to extension-based detection if MIME detection fails
- **Supported Formats**: PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, JSON, XML

### 3. File Storage

#### Unique File Naming

```
{uuid}_{original_filename}
```

- **UUID Generation**: Each file gets a unique identifier
- **Original Name Preservation**: Original filename is preserved for reference
- **Collision Prevention**: UUID prevents filename collisions

#### User Directory Structure

```
/app/orion/{user_email}/
├── raw_uploads/          # Original uploaded files
├── processed_text/       # Text extracted from files
├── raw_chunks/          # Text split into chunks
└── processed_vectors/   # Vector embeddings
```

#### Streaming Storage

- **Memory Efficient**: Files are streamed directly to disk in 8KB chunks
- **Size Monitoring**: Total size is tracked during streaming
- **Cleanup on Failure**: File is automatically deleted if validation fails

### 4. Background Processing

Once the file is successfully uploaded and stored, background processing is triggered:

#### Background Task Queuing

```python
background_tasks.add_task(
    process_file_with_pipeline,
    file_path=file_path,
    email=email,
    file_id=file_id,
    original_filename=original_filename,
)
```

#### Immediate Response

The API immediately returns a response while processing continues:

```json
{
  "message": "File uploaded successfully to user folder: user@domain.com. Pipeline processing started.",
  "filename": "document.pdf",
  "file_id": "uuid-1234-5678-9012",
  "file_size": 1024576,
  "content_type": "application/pdf",
  "converted": false,
  "converted_path": null
}
```

## Error Handling

### File Size Errors

- **HTTP 413**: File too large
- **Cleanup**: Partial files are automatically deleted
- **User Feedback**: Clear error message with size limit

### Validation Errors

- **HTTP 400**: Invalid email format or missing required fields
- **HTTP 500**: Internal server errors (logged for debugging)

### Processing Errors

- **Background Failure**: Processing failures are logged but don't affect the upload response
- **User Notification**: In production, users should be notified of processing failures

## Security Considerations

### File Upload Security

- **Size Limits**: Prevents denial-of-service attacks
- **Type Validation**: Only allows supported file types
- **User Isolation**: Each user has isolated storage

### Storage Security

- **Path Sanitization**: User emails are validated before directory creation
- **Permission Model**: Files are stored with appropriate permissions
- **Container Isolation**: Docker containers provide additional security

## Performance Characteristics

### Upload Performance

- **Streaming**: Large files don't consume excessive memory
- **Async Processing**: Upload response is immediate
- **Chunk Size**: 8KB chunks balance memory usage and I/O efficiency

### Storage Efficiency

- **User Organization**: Files are organized by user for efficient access
- **Unique Naming**: Prevents overwrites while maintaining traceability
- **Background Processing**: Doesn't block the upload response

## Monitoring and Logging

### Upload Events

All upload events are logged with structured data:

```json
{
  "filename": "document.pdf",
  "saved_as": "uuid_document.pdf",
  "content_type": "application/pdf",
  "file_size": 1024576,
  "file_id": "uuid-1234-5678-9012",
  "user_email": "user@domain.com",
  "description": "Important document",
  "pipeline_processing_queued": true
}
```

### Health Monitoring

- **File System**: Monitor disk space usage
- **Processing Queue**: Track background task completion
- **Error Rates**: Monitor upload and processing failure rates

## Configuration

### Environment Variables

- `MAX_FILE_SIZE`: Maximum upload size (default: 50MB)
- `ORION_BASE_DIR`: Base directory for all user data
- `LOG_LEVEL`: Logging verbosity

### Storage Configuration

- **Docker Volumes**: Persistent storage mapping
- **User Directories**: Automatic creation and permission setting
- **Cleanup Policies**: Configure retention and cleanup policies as needed
