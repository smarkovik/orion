# Processing Pipeline Architecture

This document describes the complete file processing pipeline in Orion, from raw uploads to vector embeddings storage.

## Pipeline Overview

The Orion processing pipeline transforms uploaded documents into searchable vector embeddings through a series of orchestrated steps. The pipeline is designed to be:

- **Modular**: Each step is independent and can be modified or replaced
- **Resilient**: Built-in retry logic and error handling
- **Observable**: Comprehensive logging and monitoring
- **Scalable**: Background processing doesn't block user interactions

## Pipeline Architecture

### Pipeline Orchestrator

The `Pipeline` class orchestrates the execution of multiple `PipelineStep` instances:

```python
class Pipeline:
    def __init__(self, name: str, steps: Sequence[PipelineStep]):
        self.name = name
        self.steps = steps
        self.status = PipelineStatus.PENDING
```

#### Key Features

- **Sequential Execution**: Steps are executed in order
- **Context Sharing**: Each step can access and modify shared context
- **Failure Handling**: Pipeline stops on first failure
- **Progress Tracking**: Tracks completion status of each step

### Pipeline Context

Shared state between pipeline steps:

```python
@dataclass
class PipelineContext:
    file_id: str              # Unique file identifier
    email: str                # User email for file organization
    original_filename: str    # Original uploaded filename
    file_path: Path          # Path to uploaded file
    metadata: Dict[str, Any] # Shared metadata between steps
    step_results: Dict[str, StepResult]  # Results from each step
```

## Pipeline Steps

### 1. File Conversion Step

**Purpose**: Convert various file formats to plain text

**Input**: Raw uploaded file  
**Output**: Plain text file in `processed_text/` directory

#### Supported Formats

- **PDF**: Uses `pdfplumber` for text extraction
- **DOCX/DOC**: Uses `python-docx` for Microsoft Word documents
- **XLSX/XLS**: Uses `pandas` for Excel spreadsheets
- **CSV**: Converts to readable text format
- **TXT/JSON/XML**: Direct copy to processed directory

#### Implementation

```python
class FileConversionStep(PipelineStep):
    async def execute(self, context: PipelineContext) -> StepResult:
        converter = FileConverter.from_settings(context.email)
        success, converted_path = converter.process_file(
            context.file_path,
            context.original_filename
        )

        if success:
            context.metadata["converted_text_path"] = converted_path
            return StepResult(status=StepStatus.SUCCESS, ...)
```

#### Error Handling

- **Unsupported Formats**: Graceful failure with informative messages
- **Corrupted Files**: Handles parsing errors appropriately
- **Permission Issues**: Proper error reporting

### 2. Text Chunking Step

**Purpose**: Split large text documents into smaller, overlapping chunks

**Input**: Plain text file from conversion step  
**Output**: Multiple chunk files in `raw_chunks/` directory

#### Configuration

```python
chunk_size: int = 512                    # Tokens per chunk
chunk_overlap_percent: float = 0.1       # 10% overlap
tiktoken_encoding: str = "cl100k_base"   # GPT-4 encoding
```

#### Process

1. **Load Text**: Read converted text file
2. **Tokenize**: Convert text to tokens using tiktoken
3. **Chunk Creation**: Create overlapping chunks of specified size
4. **File Storage**: Save each chunk as separate `.txt` file

#### Output Structure

```
/app/orion/{email}/raw_chunks/
├── document_chunk_000.txt
├── document_chunk_001.txt
├── document_chunk_002.txt
└── ...
```

### 3. Embedding Generation Step

**Purpose**: Generate vector embeddings for each text chunk using Cohere API

**Input**: Text chunks from chunking step  
**Output**: Vector embeddings added to pipeline context

#### Configuration

```python
cohere_api_key: str = ""                    # Cohere API key
cohere_model: str = "embed-english-v3.0"    # Embedding model
```

#### Process

1. **Read Chunks**: Load all chunk files from `raw_chunks/`
2. **Prepare Batch**: Collect all chunk texts for batch processing
3. **API Call**: Generate embeddings using Cohere API
4. **Data Assembly**: Combine embeddings with chunk metadata

#### Data Structure

```python
embeddings_data = [
    {
        "filename": "document_chunk_000.txt",
        "text": "chunk text content...",
        "token_count": 487,
        "embedding": [0.123, -0.456, ...],  # 1024-dimensional vector
        "embedding_model": "embed-english-v3.0"
    },
    ...
]
```

### 4. Vector Storage Step

**Purpose**: Store embeddings in persistent vector database

**Input**: Embeddings data from generation step  
**Output**: Stored embeddings in `processed_vectors/` directory

#### Storage Backends

##### JSON Storage (Default)

- **Format**: Human-readable JSON files
- **Use Case**: Development, small datasets, debugging
- **File Format**: `{file_id}_embeddings.json`

```json
{
  "file_id": "uuid-1234-5678-9012",
  "embeddings": [...],
  "metadata": {...},
  "storage_format": "json",
  "embedding_count": 25
}
```

##### HDF5 Storage

- **Format**: Optimized binary format
- **Use Case**: Production, large datasets, performance
- **File Format**: `{file_id}_embeddings.h5`
- **Features**: Compression, checksums, efficient array storage

#### Storage Process

```python
class VectorStorageStep(PipelineStep):
    async def execute(self, context: PipelineContext) -> StepResult:
        storage = StorageFactory.create_storage(
            storage_type=settings.vector_storage_type,
            storage_path=vectors_dir
        )

        saved_path = storage.save_embeddings(
            file_id=context.file_id,
            embeddings_data=embeddings_data,
            metadata=file_metadata
        )
```

## Pipeline Factory

Pre-configured pipeline templates for different use cases:

### Full Processing Pipeline

```python
def create_full_processing_pipeline() -> Pipeline:
    steps = [
        FileConversionStep(),
        TextChunkingStep(),
        EmbeddingGenerationStep(),
        VectorStorageStep(),
    ]
    return Pipeline(name="full_file_processing", steps=steps)
```

### Text-Only Pipeline

```python
def create_text_only_pipeline() -> Pipeline:
    steps = [FileConversionStep()]
    return Pipeline(name="text_conversion_only", steps=steps)
```

### Embedding Pipeline

```python
def create_embedding_pipeline() -> Pipeline:
    # Assumes text conversion already done
    steps = [
        TextChunkingStep(),
        EmbeddingGenerationStep(),
        VectorStorageStep(),
    ]
    return Pipeline(name="embedding_generation", steps=steps)
```

## Error Handling and Resilience

### Step-Level Retry Logic

Each step can be configured with retry behavior:

```python
class PipelineStep:
    def __init__(self, name: str, description: str = "", retry_count: int = 0):
        self.retry_count = retry_count

    def can_retry(self, attempt: int, error: Exception) -> bool:
        return attempt < self.retry_count
```

#### Retry Strategy

- **Exponential Backoff**: `sleep(2^attempt)` between retries
- **Configurable Attempts**: Each step can have different retry counts
- **Error-Specific Logic**: Steps can implement custom retry logic

### Pipeline-Level Error Handling

```python
async def execute(self, context: PipelineContext) -> Dict[str, Any]:
    try:
        for step in self.steps:
            if step.should_skip(context):
                # Skip step based on context
                continue

            result = await self._execute_step_with_retry(step, context)

            if result.status == StepStatus.FAILED:
                self.status = PipelineStatus.FAILED
                break

    except Exception as e:
        self.status = PipelineStatus.FAILED
        logger.error(f"Pipeline failed: {str(e)}")
        raise
```

### Step Skipping Logic

Steps can be conditionally skipped based on context:

```python
def should_skip(self, context: PipelineContext) -> bool:
    # Example: Skip chunking if no converted text
    return "converted_text_path" not in context.metadata
```

## Performance Characteristics

### Background Processing

- **Non-Blocking**: Upload returns immediately
- **Async Execution**: All steps are async-compatible
- **Resource Management**: Controlled memory and CPU usage

### Scalability Considerations

- **Batch Processing**: Embeddings generated in batches
- **File Streaming**: Large files handled efficiently
- **Storage Optimization**: HDF5 for large-scale deployments

### Monitoring and Observability

#### Execution Tracking

```python
{
    "pipeline_name": "full_file_processing",
    "status": "success",
    "file_id": "uuid-1234-5678-9012",
    "start_time": "2024-01-01T12:00:00",
    "end_time": "2024-01-01T12:02:30",
    "total_execution_time": 150.5,
    "steps_completed": 4,
    "steps_failed": 0
}
```

#### Step-Level Metrics

```python
"step_results": {
    "file_conversion": {
        "status": "success",
        "message": "PDF converted successfully",
        "execution_time": 12.3,
        "error": null
    },
    "text_chunking": {
        "status": "success",
        "message": "Text chunked into 25 pieces",
        "execution_time": 2.1,
        "error": null
    }
}
```

## Configuration

### Pipeline Configuration

```python
# Retry settings
file_conversion_retries: int = 1
text_chunking_retries: int = 1
embedding_retries: int = 2
storage_retries: int = 2

# Processing settings
enable_background_processing: bool = True
pipeline_timeout: int = 300  # 5 minutes
```

### Step Configuration

```python
# File conversion
supported_formats: List[str] = ["pdf", "docx", "xlsx", "txt"]

# Text chunking
chunk_size: int = 512
chunk_overlap_percent: float = 0.1

# Embeddings
cohere_model: str = "embed-english-v3.0"
batch_size: int = 96  # Max texts per API call

# Storage
vector_storage_type: str = "json"  # or "hdf5"
```

## Best Practices

### Pipeline Design

- **Atomic Steps**: Each step should be independently testable
- **Idempotent Operations**: Steps should be safely repeatable
- **Clear Interfaces**: Use well-defined input/output contracts
- **Comprehensive Logging**: Log important events and errors

### Error Recovery

- **Graceful Degradation**: Continue processing when possible
- **User Notification**: Inform users of processing failures
- **Retry Logic**: Implement appropriate retry strategies
- **Cleanup**: Clean up partial results on failure

### Performance Optimization

- **Batch Operations**: Process multiple items together when possible
- **Resource Limits**: Set appropriate memory and time limits
- **Monitoring**: Track performance metrics and bottlenecks
- **Caching**: Cache expensive operations when appropriate
