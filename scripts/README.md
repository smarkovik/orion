# Orion Test Scripts

This directory contains shell scripts for testing the complete Orion document processing and query pipeline.

## Scripts Overview

### 🚀 `test_full_workflow.sh`

**Complete end-to-end test of the entire Orion system**

This is the main test script that:

1. Builds and starts the Docker container
2. Uploads 3 text files from `sdk/examples/book-samples`
3. Waits for document processing to complete
4. Verifies the documents were processed correctly
5. Performs multiple search queries using both algorithms
6. Displays comprehensive results and statistics

**Usage:**

```bash
./scripts/test_full_workflow.sh
```

**What it tests:**

- Docker container build and startup
- File upload API (`POST /v1/upload`)
- Document processing pipeline (conversion, chunking, embedding)
- Library statistics API (`GET /v1/query/library/{email}/stats`)
- Search query API (`POST /v1/query`) with both cosine and hybrid algorithms
- Multiple test queries relevant to religious texts

### ⚡ `quick_test.sh`

**Quick test for development**

A simplified version for rapid testing during development:

1. Checks if API is running
2. Uploads one PDF file
3. Waits briefly for processing
4. Performs one test query

**Usage:**

```bash
./scripts/quick_test.sh
```

### 🔍 `check_status.sh`

**System status checker**

Comprehensive status check without making changes:

- Docker container status
- API health and endpoint availability
- File system structure and file counts
- Recent logs
- Library statistics

**Usage:**

```bash
./scripts/check_status.sh
```

## Prerequisites

### Required Files

- Text files in `sdk/examples/book-samples/` directory
- Docker and Docker Compose installed
- `jq` command-line JSON processor (optional, for pretty output)

### Environment Setup

Make sure you have a `.env` file with your Cohere API key:

```bash
COHERE_API_KEY=your_api_key_here
```

## Usage Examples

### Full Test Workflow

```bash
# Run the complete test
./scripts/test_full_workflow.sh

# Check status after test
./scripts/check_status.sh
```

### Development Workflow

```bash
# Start the system
docker-compose up -d

# Quick test during development
./scripts/quick_test.sh

# Check what's happening
./scripts/check_status.sh

# Stop the system
docker-compose down
```

### Troubleshooting

```bash
# Check system status
./scripts/check_status.sh

# View logs
docker-compose logs

# Restart system
docker-compose down
docker-compose up --build -d
```

## Expected Output

### Successful Full Test

```
🚀 Starting Orion Full Workflow Test
====================================
[INFO] Checking prerequisites...
[SUCCESS] Found 3 PDF files to test with
[INFO] Building and starting Docker container...
[SUCCESS] Docker container started successfully
[INFO] Waiting for API to be ready...
[SUCCESS] API is ready!
[INFO] Uploading PDF files...
[SUCCESS] Successfully uploaded 3 out of 3 files
[INFO] Waiting for document processing to complete...
[SUCCESS] Document processing completed!
[SUCCESS] Found 5 results in 0.234s using cosine algorithm
🎉 Full workflow test completed successfully!
```

### Test Queries

The script tests various queries relevant to the religious texts:

- "God creation heaven earth"
- "prayer worship faith"
- "commandments law righteousness"
- "wisdom knowledge understanding"
- "love compassion mercy"

Each query is tested with both `cosine` and `hybrid` algorithms.

## File Structure After Testing

After successful execution, you'll have:

```
$HOME/Desktop/orion/test@example.com/
├── raw_uploads/          # Original text files
├── processed_text/       # Extracted text files
├── raw_chunks/          # Text chunks (many files)
└── processed_vectors/   # Vector embeddings (JSON/HDF5)
```

## Troubleshooting

### Common Issues

1. **API not starting**: Check Docker logs with `docker-compose logs`
2. **No text files**: Ensure text files exist in `sdk/examples/book-samples/`
3. **Upload failures**: Check file permissions and API logs
4. **Processing timeout**: Large files may take longer; increase wait time
5. **Query failures**: Ensure documents are fully processed first

### Debug Commands

```bash
# Check API health
curl http://localhost:8000/health

# Check library stats
curl http://localhost:8000/v1/query/library/test@example.com/stats

# Manual upload test
curl -X POST -F "file=@/path/to/file.pdf" -F "email=test@example.com" http://localhost:8000/v1/upload

# Manual query test
curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","query":"test","algorithm":"cosine","limit":5}' \
  http://localhost:8000/v1/query
```

## Notes

- The full test script takes several minutes to complete due to document processing time
- Processing time depends on document size and system performance
- The script uses `test@example.com` as the test user email
- All scripts include colored output for better readability
- Scripts are designed to be idempotent (safe to run multiple times)
