# Disk Storage & File Organization

This document describes how Orion organizes and manages files on disk, including directory structures, naming conventions, and storage strategies.

## Storage Architecture Overview

Orion uses a hierarchical file organization system designed for:

- **User Isolation**: Each user has completely separated storage
- **Processing Stages**: Clear separation between processing stages
- **Scalability**: Efficient access patterns for large numbers of files
- **Maintainability**: Predictable structure for operations and debugging

## Directory Structure

### Root Organization

```
/app/orion/                           # Base directory (configurable)
├── user1@domain.com/                 # User-specific directories
├── user2@company.org/
├── admin@system.local/
└── ...
```

**Configuration**:

- Environment variable: `ORION_BASE_DIR`
- Default (Docker): `/app/orion`
- Default (Local): `./orion`

### User Directory Structure

Each user gets a complete processing pipeline directory structure:

```
/app/orion/{user_email}/
├── raw_uploads/          # Original uploaded files
├── processed_text/       # Text extracted from files
├── raw_chunks/          # Text split into chunks
└── processed_vectors/   # Vector embeddings storage
```

#### Directory Purposes

**`raw_uploads/`**

- **Purpose**: Store original uploaded files exactly as received
- **Retention**: Permanent (for reprocessing capabilities)
- **Access Pattern**: Write-once, read-rarely
- **File Format**: Original format (PDF, DOCX, etc.)

**`processed_text/`**

- **Purpose**: Store text extracted from documents
- **Content**: Plain text converted from various formats
- **Access Pattern**: Write-once, read for chunking
- **File Format**: UTF-8 encoded `.txt` files

**`raw_chunks/`**

- **Purpose**: Store individual text chunks before embedding
- **Content**: Overlapping text segments for embedding generation
- **Access Pattern**: Write-once, read for embedding generation
- **File Format**: UTF-8 encoded `.txt` files

**`processed_vectors/`**

- **Purpose**: Store final vector embeddings and metadata
- **Content**: Vector embeddings with associated metadata
- **Access Pattern**: Write-once, read-many for queries
- **File Format**: JSON or HDF5 depending on configuration

## File Naming Conventions

### Raw Uploads

**Pattern**: `{uuid}_{original_filename}`

**Examples**:

```
a7f3e2d1-4b6c-4a8e-9f1d-2e3c4d5f6a7b_report.pdf
e8d9f1a2-5c7e-4b9f-a2d3-3f4e5d6f7a8b_spreadsheet.xlsx
b6c8d0e1-3a5c-4e7f-8d9f-4e5f6a7b8c9d_document.docx
```

**Benefits**:

- **Uniqueness**: UUID prevents filename collisions
- **Traceability**: Original filename preserved for reference
- **URL Safety**: UUID provides safe characters for web interfaces

### Processed Text

**Pattern**: `{base_filename}.txt`

**Examples**:

```
report.txt                    # From report.pdf
spreadsheet.txt              # From spreadsheet.xlsx
document.txt                 # From document.docx
```

**Derivation**: Base filename extracted from original filename (without extension)

### Text Chunks

**Pattern**: `{base_filename}_chunk_{sequence:03d}.txt`

**Examples**:

```
report_chunk_000.txt         # First chunk
report_chunk_001.txt         # Second chunk
report_chunk_002.txt         # Third chunk
...
report_chunk_023.txt         # 24th chunk
```

**Features**:

- **Sequential Ordering**: Zero-padded numbers ensure proper sorting
- **Base Filename**: Maintains relationship to source document
- **Predictable**: Easy to programmatically generate and parse

### Vector Embeddings

#### JSON Storage Format

**Pattern**: `{file_id}_embeddings.json`

**Examples**:

```
a7f3e2d1-4b6c-4a8e-9f1d-2e3c4d5f6a7b_embeddings.json
e8d9f1a2-5c7e-4b9f-a2d3-3f4e5d6f7a8b_embeddings.json
```

#### HDF5 Storage Format

**Pattern**: `{file_id}_embeddings.h5`

**Examples**:

```
a7f3e2d1-4b6c-4a8e-9f1d-2e3c4d5f6a7b_embeddings.h5
e8d9f1a2-5c7e-4b9f-a2d3-3f4e5d6f7a8b_embeddings.h5
```

## Storage Implementation

### Directory Creation

#### Automatic User Directory Setup

```python
def create_user_directories(self, email: str) -> None:
    """Create all necessary directories for a user."""
    user_base = self.get_user_base_path(email)

    directories = [
        self.get_user_raw_uploads_path(email),
        self.get_user_processed_text_path(email),
        self.get_user_raw_chunks_path(email),
        self.get_user_processed_vectors_path(email),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
```

#### Path Resolution

```python
def get_user_base_path(self, email: str) -> Path:
    return self.orion_base_path / email

def get_user_raw_uploads_path(self, email: str) -> Path:
    return self.get_user_base_path(email) / "raw_uploads"

def get_user_processed_text_path(self, email: str) -> Path:
    return self.get_user_base_path(email) / "processed_text"

def get_user_raw_chunks_path(self, email: str) -> Path:
    return self.get_user_base_path(email) / "raw_chunks"

def get_user_processed_vectors_path(self, email: str) -> Path:
    return self.get_user_base_path(email) / "processed_vectors"
```

### File Operations

#### Streaming File Upload

```python
async def _stream_file_to_disk(file: UploadFile, file_path: Path) -> int:
    total_size = 0
    chunk_size = 8192  # 8KB chunks

    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > settings.max_file_size:
                file_path.unlink(missing_ok=True)  # Cleanup
                raise HTTPException(status_code=413, detail="File too large")

            f.write(chunk)

    return total_size
```

#### Text File Writing

```python
# UTF-8 encoding for all text files
with open(output_path, "w", encoding="utf-8") as f:
    f.write(text_content)
```

## Storage Backends

### JSON Storage

#### File Structure

```json
{
  "file_id": "uuid-1234-5678-9012",
  "embeddings": [
    {
      "filename": "document_chunk_000.txt",
      "text": "chunk text content...",
      "token_count": 487,
      "embedding": [0.123, -0.456, ...],
      "embedding_model": "embed-english-v3.0"
    }
  ],
  "metadata": {
    "email": "user@domain.com",
    "original_filename": "document.pdf",
    "chunk_size": 512,
    "embedding_model": "embed-english-v3.0"
  },
  "storage_format": "json",
  "embedding_count": 25
}
```

#### Characteristics

- **Human Readable**: Easy to inspect and debug
- **Universal**: Works with any JSON-compatible tool
- **Inefficient**: Large file sizes for big vectors
- **Slow**: Text parsing overhead for large datasets

### HDF5 Storage

#### File Structure

```python
# HDF5 internal structure
/embeddings          # Compressed float32 array
/texts              # String array with chunk texts
/filenames          # String array with chunk filenames
/token_counts       # Int32 array with token counts
/embedding_models   # String array with model names

# Attributes (metadata)
file_id: "uuid-1234-5678-9012"
embedding_count: 25
embedding_dimension: 1024
storage_format: "hdf5"
metadata: {...}  # JSON-encoded metadata
```

#### Characteristics

- **Efficient**: Compact binary storage with compression
- **Fast**: Optimized for numerical array operations
- **Compressed**: GZIP compression with checksums
- **Cross-Platform**: Standard format with broad support

#### Compression Settings

```python
f.create_dataset(
    "embeddings",
    data=embeddings_array,
    compression="gzip",         # GZIP compression
    compression_opts=9,         # Maximum compression
    shuffle=True,              # Byte reordering for better compression
    fletcher32=True,           # Data integrity checksums
)
```

## Docker Volume Configuration

### Production Mapping

```yaml
# docker-compose.yml
services:
  orion-api:
    volumes:
      - $HOME/Desktop/orion:/app/orion # User data persistence
      - ./logs:/app/logs # Application logs
```

### Development Mapping

```yaml
# Development with hot reload
services:
  orion-dev:
    volumes:
      - ./src:/app/src # Source code hot reload
      - $HOME/Desktop/orion:/app/orion # User data persistence
      - ./logs:/app/logs # Application logs
```

## Storage Monitoring and Management

### Disk Usage Monitoring

```python
def get_storage_stats(email: str) -> Dict[str, Any]:
    user_base = settings.get_user_base_path(email)

    stats = {}
    for subdir in ["raw_uploads", "processed_text", "raw_chunks", "processed_vectors"]:
        path = user_base / subdir
        if path.exists():
            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            count = len(list(path.rglob('*')))
            stats[subdir] = {"size_bytes": size, "file_count": count}

    return stats
```

### Cleanup Operations

```python
def cleanup_user_data(email: str, older_than_days: int = 30) -> None:
    """Remove old files to manage disk usage."""
    cutoff_time = datetime.now() - timedelta(days=older_than_days)
    user_base = settings.get_user_base_path(email)

    for file_path in user_base.rglob('*'):
        if file_path.is_file():
            if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time:
                file_path.unlink()
```

## Performance Considerations

### Access Patterns

**Upload Phase**:

- Sequential write to `raw_uploads/`
- Streaming to avoid memory pressure

**Processing Phase**:

- Read from `raw_uploads/`
- Write to `processed_text/`
- Read from `processed_text/`
- Write multiple files to `raw_chunks/`
- Read multiple files from `raw_chunks/`
- Write to `processed_vectors/`

**Query Phase**:

- Primary read access to `processed_vectors/`
- Occasional access to `raw_chunks/` for context

### Optimization Strategies

**File System Level**:

- Use SSDs for better random access performance
- Consider separate volumes for different stages
- Monitor inode usage for directories with many files

**Application Level**:

- Batch operations when possible
- Use appropriate buffer sizes for I/O
- Implement file locking for concurrent access

## Security Considerations

### Path Sanitization

```python
def sanitize_email_for_path(email: str) -> str:
    """Ensure email is safe for filesystem use."""
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError("Invalid email format")
    return email
```

### Access Control

- **User Isolation**: Each user can only access their own directories
- **File Permissions**: Appropriate Unix permissions on directories and files
- **Container Security**: Non-root user execution in containers

### Data Privacy

- **Encryption at Rest**: Consider encrypting sensitive file content
- **Audit Logging**: Log all file access and modifications
- **Retention Policies**: Implement data retention and deletion policies

## Backup and Disaster Recovery

### Backup Strategy

**Critical Data**:

- `raw_uploads/`: Source of truth, highest priority
- `processed_vectors/`: Expensive to regenerate, high priority
- `processed_text/`: Can be regenerated from uploads, medium priority
- `raw_chunks/`: Can be regenerated from text, low priority

**Backup Frequency**:

- `raw_uploads/`: Immediate backup after upload
- `processed_vectors/`: Daily incremental backups
- Other directories: Weekly backups or regeneration on demand

### Recovery Procedures

**File Corruption**:

1. Restore from backup if available
2. Regenerate from earlier stage in pipeline
3. Request user to re-upload if necessary

**Directory Structure Issues**:

```python
# Verify and repair user directory structure
def repair_user_directories(email: str) -> None:
    settings.create_user_directories(email)
```

**Batch Recovery**:

```python
# Regenerate all processed files for a user
def regenerate_user_pipeline(email: str) -> None:
    for upload_file in get_user_uploads(email):
        process_file_with_pipeline(upload_file.path, email, ...)
```
