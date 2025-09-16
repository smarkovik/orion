# Orion

A FastAPI-based file processing system that converts documents to text, generates vector embeddings, and provides intelligent document retrieval capabilities.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- Cohere API key for embeddings

### Local Development

```bash
# 1. Clone and setup environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Set up environment variables
export COHERE_API_KEY="your_cohere_api_key_here"
export ORION_BASE_DIR="./orion"  # Optional: default storage location

# 3. Start development server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Verify the API is running
curl http://localhost:8000/health
```

### Docker Development (Recommended)

```bash
# 1. Set up environment variables
export COHERE_API_KEY="your_cohere_api_key_here"

# 2. Start development with hot reload
make dev
# OR: docker-compose --profile dev up -d orion-dev

# 3. API available at http://localhost:8001
# 4. View logs: make logs
# 5. Stop: make stop
```

## Production Deployment

### Docker Production

```bash
# 1. Set up environment variables
export COHERE_API_KEY="your_cohere_api_key_here"

# 2. Build production image
make build
# OR: docker-compose build

# 3. Deploy production container
make run
# OR: docker-compose up -d orion-api

# 4. API available at http://localhost:8000
# 5. Monitor with: make logs
```

### Production Environment Variables

| Variable              | Required | Default      | Description                       |
| --------------------- | -------- | ------------ | --------------------------------- |
| `COHERE_API_KEY`      | Yes      | -            | API key for Cohere embeddings     |
| `ORION_BASE_DIR`      | No       | `/app/orion` | Base directory for user data      |
| `LOG_LEVEL`           | No       | `INFO`       | Logging level                     |
| `MAX_FILE_SIZE`       | No       | `52428800`   | Max upload size (50MB)            |
| `VECTOR_STORAGE_TYPE` | No       | `json`       | Storage backend: `json` or `hdf5` |

### Health Checks & Monitoring

```bash
# Health check
curl http://localhost:8000/health

# API documentation
curl http://localhost:8000/docs

# Container logs
docker-compose logs -f orion-api

# Test endpoints
make test
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development Tools

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Run tests
pytest --cov=src
```

## Testing

### End-to-End Integration Testing

For comprehensive system testing including Docker deployment, file upload, processing, and search functionality:

📖 **[E2E Integration Test Guide](e2e-readme.md)** - Complete guide to running and monitoring the full integration test

### Development Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest --cov=src tests/

# Run specific test files
pytest tests/test_pipeline.py -v

# Quick workflow test
./scripts/quick_test.sh
```

## Documentation

For detailed documentation on file processing, chunking, and storage architecture:

- **[End-to-End Testing](e2e-readme.md)**: Complete integration test guide
- **[Scripts Documentation](scripts/README.md)**: Testing and utility scripts
- **[Architecture Documentation](docs/README.md)**: System design and processing pipeline
- **[File Upload Processing](docs/file-upload-processing.md)**: Document upload workflow
- **[Processing Pipeline](docs/processing-pipeline.md)**: Multi-stage document processing
- **[Chunking & Storage](docs/chunking-storage.md)**: Text chunking and vector storage
- **[Disk Storage Organization](docs/disk-storage-organization.md)**: File system layout
