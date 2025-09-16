# Orion SDK Documentation

Welcome to the Orion SDK documentation. This guide provides comprehensive information on how to use the Python SDK for the Orion document processing and search API.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Authentication](#authentication)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Error Handling](#error-handling)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Quick Start

Get started with the Orion SDK in just a few lines of code:

```python
from orion_sdk import OrionClient

# Initialize the client
client = OrionClient(base_url="http://localhost:8000")

# Upload a document
document = client.upload_document(
    file_path="./document.pdf",
    user_email="user@example.com",
    description="Important document"
)

# Search for content
response = client.search(
    query="machine learning",
    user_email="user@example.com",
    limit=5
)

# Display results
for result in response.results:
    print(f"Score: {result.similarity_score:.3f}")
    print(f"Text: {result.text[:100]}...")

# Clean up
client.close()
```

### From Source

```bash
git clone https://github.com/orion/orion-sdk.git
cd orion-sdk
pip install -e .
```

### Dependencies

- Python 3.8+
- requests >= 2.28.0
- urllib3 >= 1.26.0

### Direct Configuration

```python
from orion_sdk import OrionClient

client = OrionClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)
```

### Configuration Object

```python
from orion_sdk import OrionConfig, OrionClient

config = OrionConfig(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    timeout=60,
    retry_attempts=5
)

client = OrionClient.from_config(config)  # Coming soon
```

## Core Concepts

### Documents

Documents represent files uploaded to the Orion system. Each document goes through a processing pipeline:

1. **Upload** - File is uploaded and stored
2. **Conversion** - File is converted to plain text
3. **Chunking** - Text is split into overlapping chunks
4. **Embedding** - Vector embeddings are generated for each chunk
5. **Storage** - Embeddings are stored for search

### Libraries

A library is a collection of documents for a specific user, identified by email address. Each user has their own isolated library.

### Search

Orion supports semantic search using vector embeddings. Search algorithms include:

- **Cosine Similarity** - Direct vector similarity matching
- **Hybrid Search** - Combines multiple search techniques

### Chunks

Documents are automatically split into smaller chunks for better search precision. Each chunk:

- Contains ~512 tokens (configurable)
- Has 10% overlap with adjacent chunks
- Includes metadata linking back to the source document

## API Reference

### OrionClient

The main client class for interacting with the Orion API.

#### Constructor

```python
OrionClient(
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None,
    timeout: int = 30,
    max_file_size: int = 50*1024*1024,
    retry_attempts: int = 3,
    verify_ssl: bool = True
)
```

**Parameters:**

- `base_url`: Orion API base URL
- `api_key`: Optional API key for authentication
- `timeout`: Request timeout in seconds
- `max_file_size`: Maximum file size for uploads (bytes)
- `retry_attempts`: Number of retry attempts for failed requests
- `verify_ssl`: Whether to verify SSL certificates

#### Document Operations

##### upload_document()

Upload a document for processing.

```python
document = client.upload_document(
    file_path: Union[str, Path],
    user_email: str,
    description: Optional[str] = None,
    wait_for_processing: bool = False,
    processing_timeout: int = 300
) -> Document
```

**Parameters:**

- `file_path`: Path to the file to upload
- `user_email`: Email identifying the user's library
- `description`: Optional description for the document
- `wait_for_processing`: Whether to wait for processing completion
- `processing_timeout`: Maximum time to wait for processing (seconds)

**Returns:** `Document` object with upload information

**Supported Formats:**

- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Microsoft Excel (`.xlsx`, `.xls`)
- Text files (`.txt`, `.json`, `.xml`, `.csv`)

**Example:**

```python
document = client.upload_document(
    file_path="./report.pdf",
    user_email="analyst@company.com",
    description="Q3 Financial Report",
    wait_for_processing=True
)

print(f"Document ID: {document.id}")
print(f"Status: {document.processing_status.value}")
print(f"Is processed: {document.is_processed}")
```

#### Search Operations

##### search()

Search for relevant document chunks.

```python
response = client.search(
    query: str,
    user_email: str,
    algorithm: str = "cosine",
    limit: int = 10
) -> SearchResponse
```

**Parameters:**

- `query`: Search query text
- `user_email`: Email identifying the user's library
- `algorithm`: Search algorithm ("cosine" or "hybrid")
- `limit`: Maximum number of results (1-100)

**Returns:** `SearchResponse` object with results and metadata

**Example:**

```python
response = client.search(
    query="revenue growth trends",
    user_email="analyst@company.com",
    algorithm="cosine",
    limit=10
)

print(f"Found {len(response.results)} results in {response.execution_time:.3f}s")
print(f"Algorithm used: {response.algorithm_used}")

for i, result in enumerate(response.results, 1):
    print(f"{i}. Score: {result.similarity_score:.3f}")
    print(f"   File: {result.original_filename}")
    print(f"   Text: {result.text[:100]}...")
```

##### get_supported_algorithms()

Get list of supported search algorithms.

```python
algorithms = client.get_supported_algorithms() -> List[str]
```

**Returns:** List of algorithm names

**Example:**

```python
algorithms = client.get_supported_algorithms()
print(f"Available algorithms: {', '.join(algorithms)}")
# Output: Available algorithms: cosine, hybrid
```

#### Library Operations

##### get_library_stats()

Get statistics about a user's document library.

```python
stats = client.get_library_stats(user_email: str) -> LibraryStats
```

**Parameters:**

- `user_email`: Email identifying the user's library

**Returns:** `LibraryStats` object with library information

**Example:**

```python
stats = client.get_library_stats("analyst@company.com")

print(f"Library exists: {stats.exists}")
print(f"Documents: {stats.document_count}")
print(f"Total chunks: {stats.chunk_count}")
print(f"Chunks with embeddings: {stats.chunks_with_embeddings}")
print(f"Embedding coverage: {stats.embedding_coverage:.1f}%")
print(f"Total size: {stats.total_file_size_mb:.1f}MB")
```

### Data Models

#### Document

Represents a document in the Orion system.

```python
@dataclass
class Document:
    id: str                           # Unique document ID
    filename: str                     # Original filename
    user_email: str                   # Owner email
    file_size: int                    # File size in bytes
    content_type: str                 # MIME type
    upload_timestamp: datetime        # Upload time
    processing_status: ProcessingStatus # Current status
    description: Optional[str] = None # Description
    error_message: Optional[str] = None # Error message (if any)
```

**Properties:**

- `is_processed: bool` - Whether processing is complete
- `has_error: bool` - Whether processing failed
- `is_processing: bool` - Whether currently processing

#### QueryResult

Represents a single search result.

```python
@dataclass
class QueryResult:
    text: str                         # Chunk text content
    similarity_score: float           # Similarity score (0.0-1.0)
    document_id: str                  # Source document ID
    original_filename: str            # Source filename
    chunk_index: int                  # Chunk position in document
    rank: int                         # Result rank (1-based)
    chunk_filename: str               # Chunk filename
```

#### SearchResponse

Complete search response with metadata.

```python
@dataclass
class SearchResponse:
    results: List[QueryResult]        # Search results
    algorithm_used: str               # Algorithm used
    total_documents_searched: int     # Documents searched
    total_chunks_searched: int        # Chunks searched
    execution_time: float             # Execution time in seconds
    query_text: str                   # Original query
```

**Methods:**

- `get_top_results(n: int)` - Get top N results by rank
- `result_count: int` - Number of results returned

#### LibraryStats

Statistics about a user's document library.

```python
@dataclass
class LibraryStats:
    exists: bool                      # Library exists
    document_count: int               # Number of documents
    chunk_count: int                  # Number of chunks
    chunks_with_embeddings: int       # Chunks with embeddings
    total_file_size: int              # Total size in bytes
```

**Properties:**

- `total_file_size_mb: float` - Total size in megabytes
- `avg_chunks_per_document: float` - Average chunks per document
- `embedding_coverage: float` - Percentage of chunks with embeddings

#### ProcessingStatus

Enumeration of document processing statuses.

```python
class ProcessingStatus(Enum):
    PENDING = "pending"        # Queued for processing
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"    # Successfully processed
    FAILED = "failed"          # Processing failed
```

## Examples

### Basic Upload and Search

```python
from orion_sdk import OrionClient

client = OrionClient(base_url="http://localhost:8000")
user_email = "user@example.com"

# Upload document
document = client.upload_document(
    file_path="./research_paper.pdf",
    user_email=user_email,
    description="Machine Learning Research Paper"
)

print(f"Uploaded: {document.filename}")

# Wait for processing (optional)
import time
print("Waiting for processing...")
time.sleep(30)  # Wait 30 seconds

# Search for content
response = client.search(
    query="neural networks deep learning",
    user_email=user_email,
    limit=5
)

print(f"Found {len(response.results)} results:")
for result in response.results:
    print(f"- {result.original_filename}: {result.similarity_score:.3f}")

client.close()
```

### Batch Upload with Progress Tracking

```python
from pathlib import Path
from orion_sdk import OrionClient, ValidationError, DocumentUploadError

client = OrionClient(base_url="http://localhost:8000")
user_email = "researcher@university.edu"

# Find all PDF files in a directory
pdf_files = list(Path("./papers").glob("*.pdf"))
uploaded_docs = []

print(f"Uploading {len(pdf_files)} documents...")

for i, pdf_file in enumerate(pdf_files, 1):
    try:
        print(f"[{i}/{len(pdf_files)}] Uploading {pdf_file.name}...")

        document = client.upload_document(
            file_path=pdf_file,
            user_email=user_email,
            description=f"Research paper: {pdf_file.stem}"
        )

        uploaded_docs.append(document)
        print(f"  ✅ Success: {document.id}")

    except ValidationError as e:
        print(f"  ❌ Validation error: {e}")
    except DocumentUploadError as e:
        print(f"  ❌ Upload error: {e}")

print(f"\nUploaded {len(uploaded_docs)} documents successfully")

# Wait for processing
print("Waiting for processing to complete...")
import time

for attempt in range(12):  # Wait up to 2 minutes
    stats = client.get_library_stats(user_email)
    coverage = stats.embedding_coverage

    print(f"  Processing progress: {coverage:.1f}% complete")

    if coverage > 90:  # Consider complete when >90% have embeddings
        print("  ✅ Processing appears complete!")
        break

    time.sleep(10)

client.close()
```

### Advanced Search with Multiple Queries

```python
from orion_sdk import OrionClient

client = OrionClient(base_url="http://localhost:8000")
user_email = "analyst@company.com"

# Define search queries with expected relevance
search_queries = [
    ("financial performance Q3 2023", "Should find quarterly reports"),
    ("machine learning artificial intelligence", "Should find AI-related content"),
    ("market trends competition analysis", "Should find market research"),
    ("revenue growth profit margins", "Should find financial analysis"),
]

print("Performing multiple searches...")

for query, description in search_queries:
    print(f"\n🔍 Query: '{query}'")
    print(f"   Expected: {description}")

    try:
        response = client.search(
            query=query,
            user_email=user_email,
            algorithm="cosine",
            limit=3
        )

        print(f"   Results: {len(response.results)} found in {response.execution_time:.3f}s")

        if response.results:
            best_result = response.results[0]
            print(f"   Best match: {best_result.original_filename}")
            print(f"   Score: {best_result.similarity_score:.3f}")
            print(f"   Preview: {best_result.text[:80]}...")
        else:
            print("   No results found")

    except Exception as e:
        print(f"   ❌ Search failed: {e}")

client.close()
```

### Context Manager Usage

```python
from orion_sdk import OrionClient

user_email = "user@example.com"

# Use context manager for automatic cleanup
with OrionClient(base_url="http://localhost:8000") as client:
    # Get library stats
    stats = client.get_library_stats(user_email)
    print(f"Library has {stats.document_count} documents")

    if stats.document_count > 0:
        # Perform search
        response = client.search(
            query="important findings",
            user_email=user_email,
            limit=5
        )

        print(f"Search found {len(response.results)} results")

        # Show top result
        if response.results:
            top_result = response.results[0]
            print(f"Top result: {top_result.original_filename}")
            print(f"Score: {top_result.similarity_score:.3f}")

# Client is automatically closed when exiting the context
```

## Error Handling

The Orion SDK provides a comprehensive exception hierarchy for robust error handling:

### Exception Hierarchy

```
OrionSDKError (base)
├── ValidationError         # Input validation failures
├── DocumentUploadError     # Upload-specific errors
├── ProcessingTimeoutError  # Processing timeout errors
├── QueryError             # Search-specific errors
├── APIError              # API errors with status codes
│   ├── AuthenticationError # 401 Authentication failed
│   ├── NotFoundError      # 404 Resource not found
│   └── RateLimitError     # 429 Rate limit exceeded
└── NetworkError          # Connection/network errors
```

### Handling Specific Errors

```python
from orion_sdk import (
    OrionClient,
    ValidationError,
    DocumentUploadError,
    QueryError,
    APIError,
    NetworkError,
    OrionSDKError
)

client = OrionClient(base_url="http://localhost:8000")

try:
    # Upload document
    document = client.upload_document(
        file_path="./document.pdf",
        user_email="user@example.com"
    )

    # Search for content
    response = client.search(
        query="search query",
        user_email="user@example.com"
    )

except ValidationError as e:
    print(f"Invalid input: {e}")
    # Handle validation errors (fix input and retry)

except DocumentUploadError as e:
    print(f"Upload failed: {e}")
    # Handle upload failures (check file, network, etc.)

except QueryError as e:
    print(f"Search failed: {e}")
    # Handle search failures (check library exists, etc.)

except APIError as e:
    print(f"API error {e.status_code}: {e}")
    # Handle API errors (check authentication, server status, etc.)

except NetworkError as e:
    print(f"Network error: {e}")
    # Handle network issues (check connectivity, DNS, etc.)

except OrionSDKError as e:
    print(f"SDK error: {e}")
    # Handle any other SDK-specific errors

except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors

finally:
    client.close()
```

### Retry Logic

The SDK includes automatic retry logic for transient failures:

```python
from orion_sdk import OrionConfig, OrionClient

# Configure retry behavior
config = OrionConfig(
    base_url="http://localhost:8000",
    retry_attempts=5,      # Retry up to 5 times
    retry_delay=2.0,       # Wait 2 seconds between retries
    timeout=60             # 60 second timeout per request
)

client = OrionClient(
    base_url=config.base_url,
    timeout=config.timeout,
    # retry configuration is handled internally
)
```

### Safe Operation Pattern

```python
def safe_operation(operation_name, operation_func):
    """Safely execute an operation with comprehensive error handling."""
    try:
        result = operation_func()
        print(f"✅ {operation_name}: Success")
        return result
    except ValidationError as e:
        print(f"❌ {operation_name}: Validation error - {e}")
    except APIError as e:
        print(f"❌ {operation_name}: API error {e.status_code} - {e}")
    except NetworkError as e:
        print(f"❌ {operation_name}: Network error - {e}")
    except OrionSDKError as e:
        print(f"❌ {operation_name}: SDK error - {e}")
    except Exception as e:
        print(f"❌ {operation_name}: Unexpected error - {e}")
    return None

# Usage
client = OrionClient(base_url="http://localhost:8000")

# Safe operations
stats = safe_operation(
    "Get library stats",
    lambda: client.get_library_stats("user@example.com")
)

algorithms = safe_operation(
    "Get algorithms",
    lambda: client.get_supported_algorithms()
)

client.close()
```

## Configuration

### Environment Variables

The SDK automatically reads configuration from environment variables:

```bash
# API Configuration
export ORION_BASE_URL="http://localhost:8000"
export ORION_API_KEY="your-api-key-here"
export ORION_TIMEOUT="30"

# File Upload Configuration
export ORION_MAX_FILE_SIZE="52428800"  # 50MB in bytes

# SSL Configuration
export ORION_VERIFY_SSL="true"
```

### Configuration Class

```python
from orion_sdk import OrionConfig

# Create configuration
config = OrionConfig(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    timeout=30,
    max_file_size=50*1024*1024,  # 50MB
    retry_attempts=3,
    retry_delay=1.0,
    verify_ssl=True,
    user_agent="my-app/1.0"
)

# Access configuration properties
print(f"API URL: {config.base_url}")
print(f"Headers: {config.headers}")
print(f"Full URL: {config.get_url('/v1/upload')}")
```

### Client Configuration

```python
from orion_sdk import OrionClient

# Configure via constructor
client = OrionClient(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    timeout=60,
    max_file_size=100*1024*1024,  # 100MB
    retry_attempts=5,
    verify_ssl=True
)

# Access client properties
print(f"Base URL: {client.base_url}")
print(f"Timeout: {client.timeout}")
```

## Best Practices

### Resource Management

Always close the client to free up resources:

```python
# Option 1: Manual cleanup
client = OrionClient(base_url="http://localhost:8000")
try:
    # Use client
    pass
finally:
    client.close()

# Option 2: Context manager (recommended)
with OrionClient(base_url="http://localhost:8000") as client:
    # Use client
    pass
# Automatically closed
```

### File Upload Guidelines

1. **Check file size before upload:**

```python
from pathlib import Path
from orion_sdk import ValidationError

file_path = Path("./large_document.pdf")
max_size = 50 * 1024 * 1024  # 50MB

if file_path.stat().st_size > max_size:
    print(f"File too large: {file_path.stat().st_size / (1024*1024):.1f}MB")
else:
    # Safe to upload
    document = client.upload_document(file_path, user_email)
```

2. **Validate file format:**

```python
from orion_sdk.utils import FileValidator

validator = FileValidator()
if validator.is_supported_file(file_path):
    document = client.upload_document(file_path, user_email)
else:
    print(f"Unsupported file format: {file_path.suffix}")
```

3. **Handle upload progress for large files:**

```python
import time
from orion_sdk import DocumentUploadError

try:
    print("Starting upload...")
    document = client.upload_document(
        file_path="./large_file.pdf",
        user_email=user_email,
        wait_for_processing=False
    )
    print(f"Upload complete: {document.id}")

    # Monitor processing
    print("Monitoring processing...")
    for i in range(30):  # Check for up to 5 minutes
        stats = client.get_library_stats(user_email)
        print(f"Processing... ({stats.embedding_coverage:.1f}% complete)")

        if stats.embedding_coverage > 90:
            print("Processing complete!")
            break

        time.sleep(10)

except DocumentUploadError as e:
    print(f"Upload failed: {e}")
```

### Search Optimization

1. **Use appropriate query length:**

```python
# Good: Specific, focused queries
good_queries = [
    "machine learning algorithms",
    "quarterly revenue growth",
    "risk management strategies"
]

# Avoid: Too short or too long
avoid_queries = [
    "ML",  # Too short, ambiguous
    "What are the detailed implications of machine learning algorithms on business processes and how do they affect quarterly revenue growth in the context of modern enterprise risk management strategies?"  # Too long
]
```

2. **Choose the right algorithm:**

```python
# Get available algorithms
algorithms = client.get_supported_algorithms()

# Choose based on use case
algorithm = "cosine"    # For semantic similarity
# algorithm = "hybrid"  # For combined semantic + keyword search
```

3. **Set appropriate result limits:**

```python
# For quick overviews
response = client.search(query, user_email, limit=5)

# For comprehensive analysis
response = client.search(query, user_email, limit=20)

# Avoid very large limits (impacts performance)
# response = client.search(query, user_email, limit=100)  # Usually unnecessary
```

### Performance Tips

1. **Reuse client instances:**

```python
# Good: Reuse client
client = OrionClient(base_url="http://localhost:8000")
for query in queries:
    response = client.search(query, user_email)
client.close()

# Avoid: Creating new clients for each operation
for query in queries:
    client = OrionClient(base_url="http://localhost:8000")
    response = client.search(query, user_email)
    client.close()
```

2. **Batch operations when possible:**

```python
# Upload multiple files
files = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
uploaded_docs = []

for file_path in files:
    try:
        doc = client.upload_document(file_path, user_email)
        uploaded_docs.append(doc)
    except Exception as e:
        print(f"Failed to upload {file_path}: {e}")

# Wait for all to process
print("Waiting for batch processing...")
# ... wait and check stats
```

3. **Monitor library statistics:**

```python
def wait_for_processing(client, user_email, timeout=300):
    """Wait for document processing to complete."""
    import time

    start_time = time.time()
    while time.time() - start_time < timeout:
        stats = client.get_library_stats(user_email)

        if stats.embedding_coverage > 95:  # 95% complete
            return True

        print(f"Processing: {stats.embedding_coverage:.1f}% complete")
        time.sleep(10)

    return False  # Timeout

# Usage
if wait_for_processing(client, user_email):
    print("Ready for search!")
else:
    print("Processing taking longer than expected")
```

## Troubleshooting

### Common Issues

#### 1. Connection Errors

**Problem:** Cannot connect to Orion API

**Solutions:**

```python
# Check if API is running
import requests
try:
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"API Status: {response.status_code}")
except requests.exceptions.ConnectionError:
    print("❌ API is not running")
    print("Start with: uvicorn src.main:app --host 0.0.0.0 --port 8000")
```

#### 2. File Upload Failures

**Problem:** File upload fails with validation errors

**Solutions:**

```python
from orion_sdk.utils import FileValidator

# Check file before upload
validator = FileValidator()
file_info = validator.get_file_info(Path("./document.pdf"))

print(f"File size: {file_info['size_mb']:.1f}MB")
print(f"MIME type: {file_info['mime_type']}")
print(f"Supported: {file_info['is_supported']}")

if not file_info['is_supported']:
    print(f"Supported formats: {validator.get_supported_extensions()}")
```

#### 3. Search Returns No Results

**Problem:** Search queries return empty results

**Solutions:**

```python
# Check library status
stats = client.get_library_stats(user_email)
print(f"Documents: {stats.document_count}")
print(f"Chunks with embeddings: {stats.chunks_with_embeddings}")

if stats.document_count == 0:
    print("No documents in library - upload some first")
elif stats.chunks_with_embeddings == 0:
    print("Documents not yet processed - wait for processing")
else:
    # Try broader queries
    broad_queries = ["document", "text", "content"]
    for query in broad_queries:
        response = client.search(query, user_email, limit=5)
        if response.results:
            print(f"Found results for: '{query}'")
            break
```

#### 4. Processing Takes Too Long

**Problem:** Document processing seems stuck

**Solutions:**

```python
import time

def monitor_processing(client, user_email, max_wait=600):
    """Monitor processing with detailed status."""
    start_time = time.time()
    last_coverage = 0

    while time.time() - start_time < max_wait:
        stats = client.get_library_stats(user_email)
        current_coverage = stats.embedding_coverage

        print(f"Time: {int(time.time() - start_time)}s")
        print(f"Documents: {stats.document_count}")
        print(f"Total chunks: {stats.chunk_count}")
        print(f"Chunks with embeddings: {stats.chunks_with_embeddings}")
        print(f"Coverage: {current_coverage:.1f}%")

        if current_coverage > 95:
            print("✅ Processing complete!")
            return True

        if current_coverage > last_coverage:
            print("📈 Progress detected")
            last_coverage = current_coverage
        else:
            print("⏳ No progress yet")

        print("-" * 40)
        time.sleep(15)

    print("⏰ Timeout reached")
    return False
```

### Debug Mode

Enable detailed logging for debugging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Create client with debug info
client = OrionClient(
    base_url="http://localhost:8000",
    timeout=30
)

# Operations will now show detailed logs
```

### API Health Check

```python
def check_api_health(base_url="http://localhost:8000"):
    """Check if Orion API is healthy."""
    import requests

    try:
        # Check basic health
        health_response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health check: {health_response.status_code}")

        # Check API info
        root_response = requests.get(f"{base_url}/", timeout=5)
        if root_response.status_code == 200:
            info = root_response.json()
            print(f"API Version: {info.get('version', 'unknown')}")
            print(f"Status: {info.get('status', 'unknown')}")

        # Check if we can get algorithms
        algorithms_response = requests.get(f"{base_url}/v1/query/algorithms", timeout=5)
        print(f"Algorithms endpoint: {algorithms_response.status_code}")

        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API")
        return False
    except requests.exceptions.Timeout:
        print("❌ API response timeout")
        return False
    except Exception as e:
        print(f"❌ API check failed: {e}")
        return False

# Usage
if check_api_health():
    print("✅ API is healthy")
    client = OrionClient()
else:
    print("❌ API is not available")
```

## Advanced Usage

### Custom HTTP Configuration

```python
from orion_sdk import OrionConfig, OrionClient

# Advanced HTTP configuration
config = OrionConfig(
    base_url="http://localhost:8000",
    timeout=60,
    retry_attempts=5,
    retry_delay=2.0,
    verify_ssl=False,  # For development only
    user_agent="MyApp/1.0 (company@example.com)"
)

client = OrionClient(
    base_url=config.base_url,
    timeout=config.timeout,
    verify_ssl=config.verify_ssl
)
```

### Async Usage (Coming Soon)

```python
import asyncio
from orion_sdk import AsyncOrionClient

async def async_example():
    async with AsyncOrionClient(base_url="http://localhost:8000") as client:
        # Upload multiple documents concurrently
        upload_tasks = [
            client.upload_document(f"doc{i}.pdf", "user@example.com")
            for i in range(1, 6)
        ]

        documents = await asyncio.gather(*upload_tasks)
        print(f"Uploaded {len(documents)} documents")

        # Search concurrently
        search_tasks = [
            client.search(query, "user@example.com")
            for query in ["AI", "ML", "data"]
        ]

        responses = await asyncio.gather(*search_tasks)
        for query, response in zip(["AI", "ML", "data"], responses):
            print(f"Query '{query}': {len(response.results)} results")

# Run async example
# asyncio.run(async_example())
```

### Integration with Data Science Workflows

```python
import pandas as pd
from orion_sdk import OrionClient

def create_search_results_dataframe(response):
    """Convert search results to pandas DataFrame."""
    data = []
    for result in response.results:
        data.append({
            'rank': result.rank,
            'filename': result.original_filename,
            'similarity_score': result.similarity_score,
            'chunk_index': result.chunk_index,
            'text_preview': result.text[:100],
            'text_length': len(result.text)
        })

    return pd.DataFrame(data)

# Usage
client = OrionClient(base_url="http://localhost:8000")
response = client.search("machine learning", "researcher@university.edu")

# Convert to DataFrame for analysis
df = create_search_results_dataframe(response)
print(df.head())

# Analyze results
print(f"Average similarity score: {df['similarity_score'].mean():.3f}")
print(f"Files with results: {df['filename'].nunique()}")

client.close()
```

### Batch Processing Pipeline

```python
from pathlib import Path
from orion_sdk import OrionClient, DocumentUploadError
import time
import json

def batch_process_documents(documents_dir, user_email, output_file=None):
    """Process a directory of documents and track results."""
    client = OrionClient(base_url="http://localhost:8000")

    # Find all supported files
    file_extensions = ['.pdf', '.docx', '.txt', '.json']
    files = []
    for ext in file_extensions:
        files.extend(Path(documents_dir).glob(f"*{ext}"))

    results = {
        'uploaded': [],
        'failed': [],
        'processing_stats': []
    }

    print(f"Found {len(files)} documents to process")

    # Upload phase
    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Processing {file_path.name}")

        try:
            document = client.upload_document(
                file_path=file_path,
                user_email=user_email,
                description=f"Batch upload: {file_path.stem}"
            )

            results['uploaded'].append({
                'filename': file_path.name,
                'document_id': document.id,
                'file_size': document.file_size,
                'upload_time': document.upload_timestamp.isoformat()
            })

            print(f"  ✅ Uploaded: {document.id}")

        except DocumentUploadError as e:
            results['failed'].append({
                'filename': file_path.name,
                'error': str(e)
            })
            print(f"  ❌ Failed: {e}")

    # Wait for processing
    print("\nWaiting for processing to complete...")
    start_time = time.time()

    for check in range(60):  # Check for up to 10 minutes
        stats = client.get_library_stats(user_email)

        results['processing_stats'].append({
            'timestamp': time.time(),
            'documents': stats.document_count,
            'chunks': stats.chunk_count,
            'embeddings': stats.chunks_with_embeddings,
            'coverage': stats.embedding_coverage
        })

        print(f"  Processing: {stats.embedding_coverage:.1f}% complete")

        if stats.embedding_coverage > 95:
            print("  ✅ Processing complete!")
            break

        time.sleep(10)

    # Final results
    results['summary'] = {
        'total_files': len(files),
        'uploaded_successfully': len(results['uploaded']),
        'upload_failures': len(results['failed']),
        'processing_time': time.time() - start_time,
        'final_stats': client.get_library_stats(user_email).__dict__
    }

    # Save results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {output_file}")

    client.close()
    return results

# Usage
results = batch_process_documents(
    documents_dir="./research_papers",
    user_email="researcher@university.edu",
    output_file="batch_results.json"
)

print(f"\nBatch processing summary:")
print(f"Files processed: {results['summary']['total_files']}")
print(f"Upload success rate: {results['summary']['uploaded_successfully'] / results['summary']['total_files'] * 100:.1f}%")
```

This comprehensive documentation should help users understand and effectively use the Orion SDK. The documentation covers everything from basic usage to advanced patterns and troubleshooting common issues.
