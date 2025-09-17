# Orion

A FastAPI-based file processing system that converts documents to text, generates vector embeddings, and provides intelligent document retrieval capabilities.

## Quick Start

```bash
# 1. Set up environment
export COHERE_API_KEY="your_cohere_api_key_here"

# 2. Start development environment
make dev

# 3. Test the system (uploads Romeo & Juliet and runs search)
make test

# 4. Run full test suite with coverage
make unit-test
```

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
make logs

# Quick system test
make test
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development Tools

### Makefile Commands

```bash
# View all available commands
make help

# Build Docker image
make build

# Run development environment with hot reload
make dev

# Run production environment
make run

# Stop all containers
make stop

# View container logs
make logs

# Open shell in running container
make shell

# Clean up containers and images
make clean

# Check requirements alignment
make check-reqs
```

### Testing Commands

```bash
# Quick comprehensive test (document processing + search)
make test

# Unit tests with coverage analysis
make coverage

# Complete test suite (unit + integration + comprehensive)
make unit-test
```

### Code Quality Tools

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Manual pytest (if needed)
pytest --cov=src
```

## Testing

### Testing Workflow

The project includes three levels of testing for different development needs:

#### 🚀 Quick Test (Recommended for Development)
```bash
# Fast comprehensive test: uploads Romeo & Juliet, processes it, and runs search
make test
```
- ✅ Document upload and processing
- ✅ Vector embedding generation  
- ✅ Semantic search functionality
- ⏱️ ~60 seconds runtime

#### 🧪 Unit Tests with Coverage
```bash
# Run all unit tests with detailed coverage analysis
make coverage
```
- ✅ 154 unit tests across all modules
- ✅ 83%+ code coverage requirement
- ✅ HTML coverage report (opens with `open htmlcov/index.html`)
- ⏱️ ~8 seconds runtime

#### 🎯 Complete Test Suite  
```bash
# Full test suite: unit + integration + comprehensive tests
make unit-test
```
- ✅ Unit tests with coverage
- ✅ SDK integration tests
- ✅ Comprehensive document processing test
- ✅ Full workflow validation
- ⏱️ ~2-3 minutes runtime

### Manual Testing Options

```bash
# Individual test components (if needed)
pytest tests/ -v                    # Unit tests only
pytest --cov=src tests/             # Unit tests with coverage
./scripts/quick_test.sh              # Quick processing test
./scripts/test_full_workflow.sh      # Full workflow test

# SDK tests
cd sdk && python -m pytest tests/ -v
```

### End-to-End Integration Testing

For comprehensive system testing including Docker deployment, file upload, processing, and search functionality:

📖 **[E2E Integration Test Guide](e2e-readme.md)** - Complete guide to running and monitoring the full integration test

## Documentation

For detailed documentation on file processing, chunking, and storage architecture:

- **[End-to-End Testing](e2e-readme.md)**: Complete integration test guide
- **[Scripts Documentation](scripts/README.md)**: Testing and utility scripts
- **[Architecture Documentation](docs/README.md)**: System design and processing pipeline
- **[File Upload Processing](docs/file-upload-processing.md)**: Document upload workflow
- **[Processing Pipeline](docs/processing-pipeline.md)**: Multi-stage document processing
- **[Chunking & Storage](docs/chunking-storage.md)**: Text chunking and vector storage
- **[Disk Storage Organization](docs/disk-storage-organization.md)**: File system layout
