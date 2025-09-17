# End-to-End Integration Tests

This directory contains comprehensive integration tests that verify the complete Orion workflow from Docker deployment to API functionality using the SDK.

## Overview

The integration test performs the following workflow:

1. **Build** - Builds the Orion API Docker image
2. **Deploy** - Starts the API container with proper configuration
3. **Upload** - Uploads 3 text files using the SDK
4. **Process** - Waits for document processing (text extraction, chunking, embedding generation)
5. **Search** - Tests both cosine similarity and hybrid search algorithms
6. **Report** - Generates detailed test results and metrics
7. **Cleanup** - Stops containers and cleans up resources

## Prerequisites

### Required Software

- **Docker** - For building and running the Orion API container
- **Python 3.8+** - For running the SDK and test scripts
- **Git** - For repository operations

### Required Environment

- **Cohere API Key** - Set `COHERE_API_KEY` environment variable
- **Text Files** - Sample files provided in `sdk/examples/book-samples/` (or add your own)

### Setup Text Files

The test expects 3 text files in the `sdk/examples/book-samples/` directory.

**Sample Files Provided:**

The repository includes sample text files ready for testing:

- `beowolf.txt` - Classic epic poem
- `frankenstain.txt` - Mary Shelley's novel
- `moby-dick.txt` - Herman Melville's novel
- `romeo-and-juliet.txt` - Shakespeare's play

**Custom Files (Optional):**

To use your own text files instead:

```bash
# From the repository root directory
# Copy your text files (will supplement or replace sample files)
cp /path/to/your-book1.txt sdk/examples/book-samples/
cp /path/to/your-book2.txt sdk/examples/book-samples/
cp /path/to/your-book3.txt sdk/examples/book-samples/
```

**File Requirements:**

- At least 3 text files (.txt extension)
- Maximum 50MB per file (configurable)
- Should contain substantial text content
- Preferably books or documents with meaningful content for search testing

## Running Tests

### Option 1: Local Execution

Run the integration test locally on your machine:

```bash
# From the SDK root directory
export COHERE_API_KEY="your-cohere-api-key"
./integration-tests/run_local_test.sh
```

The script will:

- Check all prerequisites
- Set up Python virtual environment
- Run the complete integration test
- Display results summary

### Option 2: GitHub Actions (Manual Trigger)

Run the test in GitHub Actions with manual workflow dispatch:

1. **Go to Actions tab** in your GitHub repository
2. **Select "🧪 End-to-End Integration Test"** workflow
3. **Click "Run workflow"**
4. **Enter required inputs:**
   - **Cohere API Key**: Your Cohere API key
   - **Test Timeout**: Maximum test duration (default: 30 minutes)
   - **Log Level**: Logging verbosity (DEBUG/INFO/WARN/ERROR)

The workflow will:

- Set up Ubuntu environment with Docker and Python
- Checkout repository code
- Run the integration test
- Upload test results as artifacts
- Clean up all resources

## Test Configuration

### Environment Variables

| Variable         | Required | Description                   | Default |
| ---------------- | -------- | ----------------------------- | ------- |
| `COHERE_API_KEY` | Yes      | Cohere API key for embeddings | None    |
| `LOG_LEVEL`      | No       | Logging verbosity             | INFO    |

### Test Parameters

The test uses these configurations:

```python
# Container settings
CONTAINER_NAME = "orion-e2e-test"
API_PORT = "8002"  # Avoids conflicts with dev instances
API_URL = "http://localhost:8002"

# Test data
TEST_USER_EMAIL = "e2e-test@orion.ai"
TEXT_FILES_COUNT = 3

# Timeouts
DOCKER_BUILD_TIMEOUT = 300  # 5 minutes
API_READY_TIMEOUT = 30      # 30 seconds
PROCESSING_TIMEOUT = 300    # 5 minutes
```

## Test Results

### Success Criteria

The test passes when all of these conditions are met:

- **Docker Build**: Image builds successfully
- **Docker Start**: Container starts and API becomes healthy
- **File Upload**: At least 1 text file uploads successfully
- **Processing**: Documents are processed with >85% embedding coverage
- **Search**: Either cosine or hybrid search returns results

### Output Files

After running, the test generates:

- **`last_test_report.json`** - Detailed JSON report with all metrics
- **Console logs** - Real-time test progress and results

### Sample Report

```json
{
  "docker_build": true,
  "docker_start": true,
  "api_health": true,
  "file_uploads": [
    {
      "filename": "book1.txt",
      "document_id": "uuid-123",
      "file_size": 1024576,
      "status": "uploaded",
      "error": null
    }
  ],
  "processing_complete": true,
  "cosine_search": true,
  "hybrid_search": true,
  "search_results": {
    "cosine": [
      {
        "query": "artificial intelligence",
        "results_count": 5,
        "execution_time": 0.234,
        "top_score": 0.876
      }
    ]
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails

**Problem**: Docker image build fails

**Solutions**:

- Check Docker is running: `docker --version`
- Ensure sufficient disk space (>2GB)
- Verify Dockerfile exists in parent directory
- Check network connectivity for package downloads

#### 2. No Text Files Found

**Problem**: `Need at least 3 text files in sdk/examples/book-samples/`

**Solutions**:

```bash
# Check directory exists (from repository root)
ls -la sdk/examples/book-samples/

# Add text files
cp /path/to/*.txt sdk/examples/book-samples/

# Verify files
find sdk/examples/book-samples -name "*.txt" | wc -l
```

#### 3. Cohere API Key Issues

**Problem**: `Cohere API key is required but not configured`

**Solutions**:

```bash
# Set environment variable
export COHERE_API_KEY="your-key-here"

# Verify it's set
echo $COHERE_API_KEY

# For GitHub Actions, add as repository secret
```

#### 4. Processing Timeout

**Problem**: Documents don't finish processing within timeout

**Solutions**:

- Check Cohere API key is valid and has quota
- Reduce text file sizes (large files take longer)
- Increase processing timeout in the test
- Check container logs: `docker logs orion-e2e-test`

#### 5. Search Returns No Results

**Problem**: Search queries return empty results

**Solutions**:

- Verify processing completed (check embedding coverage)
- Try broader search terms
- Check text files contain meaningful content for search
- Verify API endpoints are responding

### Debugging Commands

```bash
# Check container status
docker ps -a

# View container logs
docker logs orion-e2e-test

# Connect to container
docker exec -it orion-e2e-test /bin/bash

# Check API health
curl http://localhost:8002/health

# View test logs
tail -f integration-tests/test.log

# Check text file content (from repository root)
file sdk/examples/book-samples/*.txt
head -n 20 sdk/examples/book-samples/*.txt
```

## Development

### Modifying the Test

To customize the integration test:

1. **Edit test parameters** in `test_e2e_integration.py`:

   ```python
   # Change test queries
   test_queries = [
       "your custom query",
       "another search term"
   ]

   # Adjust timeouts
   max_wait_time = 600  # 10 minutes
   ```

2. **Add new test steps** by extending the `IntegrationTestRunner` class

3. **Modify search algorithms** by updating the algorithm list

### Adding New Checks

To add additional verification steps:

```python
def test_custom_feature(self) -> bool:
    """Test a custom feature."""
    self.log("🔧 Testing custom feature...")

    try:
        # Your test logic here
        result = self.client.custom_operation()

        self.test_results["custom_feature"] = True
        return True

    except Exception as e:
        self.log(f"❌ Custom feature test failed: {e}", "ERROR")
        return False
```

## CI/CD Integration

### GitHub Actions

The workflow file `.github/workflows/e2e-integration-test.yml` provides:

- **Manual triggering** with input parameters
- **Artifact upload** for test results
- **Proper cleanup** of Docker resources
- **Detailed logging** and error reporting

### Other CI Systems

To adapt for other CI systems:

1. **Jenkins**: Use similar Docker and Python setup steps
2. **GitLab CI**: Adapt the YAML structure for GitLab format
3. **Travis CI**: Use the script commands in `.travis.yml`

## Performance Metrics

### Typical Execution Times

| Phase           | Duration      | Notes                        |
| --------------- | ------------- | ---------------------------- |
| Docker Build    | 2-5 minutes   | Depends on network and cache |
| Container Start | 10-30 seconds | API initialization time      |
| File Upload     | 5-15 seconds  | Per file, depends on size    |
| Processing      | 1-5 minutes   | Depends on content and API   |
| Search Tests    | 5-10 seconds  | Multiple queries             |

### Resource Usage

- **CPU**: Moderate during processing phase
- **Memory**: ~2GB for Docker container
- **Disk**: ~1GB for Docker image
- **Network**: API calls to Cohere for embeddings

## Support

For issues with the integration tests:

1. **Check logs** in the console output and test report
2. **Verify prerequisites** are properly installed and configured
3. **Test components individually** (Docker, SDK, API endpoints)
4. **Report issues** with full logs and error messages

The integration test is designed to be comprehensive and reliable, providing confidence that the entire Orion system works correctly from end to end.
