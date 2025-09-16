# Orion End-to-End Integration Test

The Orion E2E integration test (`sdk/integration-tests/test_e2e_integration.py`) is a comprehensive automated test that validates the entire document processing and search pipeline from start to finish.

## 🎯 What the E2E Test Does

The integration test simulates a complete user workflow by performing these steps:

### 1. Infrastructure Setup

- **Docker Build**: Compiles the Orion application into a container
- **Docker Start**: Launches the containerized application
- **Health Check**: Verifies the API is responding at `http://localhost:8000/health`

### 2. Document Upload & Processing

- **File Upload**: Uploads 3 PDF files from `$HOME/Desktop/books/` using the SDK
- **Processing Pipeline**: Waits for documents to be fully processed through:
  - PDF → Text conversion (see [File Upload Processing](docs/file-upload-processing.md))
  - Text chunking (see [Processing Pipeline](docs/processing-pipeline.md))
  - Vector embedding generation via Cohere API
  - Storage in JSON/HDF5 format (see [Chunking & Storage](docs/chunking-storage.md))

### 3. Search Algorithm Testing

- **Cosine Similarity Search**: Tests semantic search using vector similarity
- **Hybrid Search**: Tests combined semantic + keyword search (BM25-like)
- **Query Validation**: Runs multiple test queries relevant to religious texts:
  - "artificial intelligence and machine learning"
  - "faith and spirituality in daily life"
  - "historical events and their significance"
  - "wisdom and knowledge from ancient texts"
  - "moral teachings and ethical principles"

### 4. Results Validation

- **Library Statistics**: Verifies document count, chunk count, and embedding status
- **Search Quality**: Validates that queries return relevant results with appropriate scores
- **Performance Metrics**: Measures search response times and processing duration

### 5. Cleanup

- **Container Cleanup**: Properly shuts down Docker containers
- **Resource Cleanup**: Removes temporary files and test data

## 🚀 How to Run the E2E Test

### Prerequisites

1. **PDF Test Files**: Place 3 PDF files in `$HOME/Desktop/books/`

   - Files should be substantial (1MB+) to test real-world processing

2. **Environment Setup**:

   ```bash
   # Required: Cohere API key for embeddings
   export COHERE_API_KEY="your_api_key_here"

   # Optional: Custom timeouts for large files
   export ORION_TIMEOUT=600  # 10 minutes for large files
   ```

3. **Dependencies**:
   - Docker & Docker Compose
   - Python 3.11+
   - Orion SDK installed (`pip install -e sdk/`)

### Running the Test

```bash
# Navigate to integration test directory
cd sdk/integration-tests/

# Run the full E2E test
python test_e2e_integration.py
```

### Alternative: Menu-Driven Interface

For interactive testing, use the menu-driven script:

```bash
# Run the test menu
./scripts/run_test.sh

# Select option 4: "Full E2E Integration Test"
```

## 📊 Monitoring Test Progress

### Real-Time Progress

The E2E test provides detailed logging with timestamps and progress indicators:

```
[19:45:32] 🏗️  Building Docker container...
[19:46:15] ✅ Docker build completed (43.2s)
[19:46:16] 🚀 Starting Docker container...
[19:46:18] ✅ Container started successfully
[19:46:19] 🏥 Checking API health...
[19:46:23] ✅ API is healthy and responding
[19:46:24] 📤 Uploading 3 PDF files...
[19:46:25] 📄 Uploading: The-Holy-Bible-King-James-Version.pdf (8.2MB)
[19:48:41] ✅ Upload completed (2m 16s)
[19:48:42] ⏳ Waiting for processing to complete...
[19:52:15] ✅ Processing completed (3m 33s)
[19:52:16] 🔍 Testing search algorithms...
```

### Monitoring Docker Logs

While the test runs, monitor processing in another terminal:

```bash
# Follow all container logs
docker-compose logs -f

# Follow specific service logs
docker-compose logs -f orion

# Check last 100 lines
docker-compose logs --tail=100 orion
```

### API Status Monitoring

Check system status during the test:

```bash
# API health
curl http://localhost:8000/health

# Library statistics
curl http://localhost:8000/v1/query/library/test@example.com/stats

# Supported algorithms
curl http://localhost:8000/v1/query/algorithms
```

## 📈 Understanding Test Results

### Success Report

A successful test produces a comprehensive report:

```
================================================================================
ORION END-TO-END INTEGRATION TEST REPORT
================================================================================

OVERALL STATUS: 7/7 steps passed

INFRASTRUCTURE:
  Docker Build:     PASS
  Docker Start:     PASS
  API Health:       PASS

FILE UPLOADS:
  Upload Success:   3/3 files
    PASS The-Holy-Bible-King-James-Version.pdf (8,623,104 bytes)
    PASS Quran-English-Translation.pdf (2,156,789 bytes)
    PASS Book-of-Mormon.pdf (3,445,221 bytes)

PROCESSING:
  Processing:       PASS

SEARCH TESTING:
  Cosine Search:    PASS
  Hybrid Search:    PASS

  Cosine Results:
    'artificial intelligence and machine...' → 5 results (score: 0.823)
    'faith and spirituality in daily life...' → 5 results (score: 0.891)

  Hybrid Results:
    'artificial intelligence and machine...' → 5 results (score: 0.756)
    'faith and spirituality in daily life...' → 5 results (score: 0.834)

CLEANUP:
  Cleanup:          PASS

🎉 SUCCESS: All integration tests passed!
```

### Failure Analysis

If tests fail, the report shows specific failure points:

```
INFRASTRUCTURE:
  Docker Build:     FAIL - Container failed to build
  Docker Start:     SKIP - Previous step failed
  API Health:       SKIP - Previous step failed

📋 FAILURE SUMMARY:
- Docker build failed with exit code 1
- Check Docker logs: docker-compose logs --tail=50
- Verify Dockerfile syntax and dependencies
```

## 🔧 Timeout Configuration

The E2E test is configured for large file processing:

- **Upload Timeout**: 5 minutes (300s)
- **Processing Timeout**: 15 minutes (900s)
- **Health Check Timeout**: 1 minute
- **Search Query Timeout**: 30 seconds

### Adjusting Timeouts for Very Large Files

For exceptionally large documents (50MB+), you may need to increase timeouts:

```python
# In test_e2e_integration.py, modify these values:
client = OrionClient(base_url=self.api_url, timeout=600)  # 10 minutes
max_wait_time = 1800  # 30 minutes for very large processing
```

## 🧪 Test Data Organization

The E2E test organizes data according to Orion's [disk storage structure](docs/disk-storage-organization.md):

```
$HOME/Desktop/orion/test@example.com/
├── raw_uploads/           # Original uploaded PDFs
├── processed_text/        # Converted text files
├── raw_chunks/           # Split text chunks
└── processed_vectors/    # Vector embeddings (JSON/HDF5)
```

## 🔗 Related Documentation

- **[Main README](README.md)**: Project overview and quick start
- **[File Upload Processing](docs/file-upload-processing.md)**: Document upload and conversion pipeline
- **[Processing Pipeline](docs/processing-pipeline.md)**: Multi-stage document processing
- **[Chunking & Storage](docs/chunking-storage.md)**: Text chunking and vector storage
- **[Disk Storage Organization](docs/disk-storage-organization.md)**: File system layout
- **[Scripts README](scripts/README.md)**: Additional testing scripts

## 🛠️ Troubleshooting

### Common Issues

**Upload Timeouts**

```
ERROR: Upload failed after 300s: Read timeout
```

- **Solution**: Files are too large for default timeout
- **Fix**: Increase `ORION_TIMEOUT` environment variable
- **Alternative**: Use smaller test files first

**Processing Stuck**

```
WARN: Processing timeout reached, but continuing...
```

- **Cause**: Large documents take time to process
- **Check**: `docker-compose logs -f` for processing progress
- **Normal**: Bible PDF can take 10+ minutes to fully process

**Cohere API Errors**

```
ERROR: Failed to generate embeddings: API key invalid
```

- **Solution**: Verify `COHERE_API_KEY` is set correctly
- **Check**: API key has sufficient credits
- **Test**: `curl` Cohere API directly to verify access

**Docker Build Failures**

```
ERROR: Docker build failed with exit code 1
```

- **Check**: `docker-compose logs --tail=50`
- **Common**: Missing dependencies or network issues
- **Fix**: `docker-compose build --no-cache`

### Debug Commands

```bash
# Full system status
./scripts/check_status.sh

# Manual API testing
curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","query":"test","algorithm":"cosine","limit":5}' \
  http://localhost:8000/v1/query

# Check file system state
ls -la $HOME/Desktop/orion/test@example.com/*/

# Monitor processing logs
docker-compose logs -f --tail=100 orion
```

## 🎯 Expected Performance

Based on typical hardware and document sizes:

| Document Size | Upload Time | Processing Time | Total Time    |
| ------------- | ----------- | --------------- | ------------- |
| 1-2 MB PDF    | 10-30s      | 2-5 minutes     | 3-6 minutes   |
| 5-10 MB PDF   | 30-60s      | 5-10 minutes    | 6-11 minutes  |
| 10+ MB PDF    | 1-3 minutes | 10-20 minutes   | 12-23 minutes |

**Note**: Processing time includes PDF conversion, chunking (typically 500-2000 chunks per document), embedding generation via Cohere API, and vector storage.

## 🎉 Success Criteria

The E2E test passes when:

✅ **Infrastructure**: Docker builds and starts successfully  
✅ **Uploads**: All 3 PDFs upload without timeout  
✅ **Processing**: Documents convert to searchable chunks with embeddings  
✅ **Search**: Both cosine and hybrid algorithms return relevant results  
✅ **Performance**: Search queries complete in <2 seconds  
✅ **Cleanup**: Resources are properly cleaned up

This comprehensive test validates that Orion can handle real-world document processing and search workloads end-to-end.
