# Orion

FastAPI backend with mock file upload and query endpoints.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Build and run with Docker Compose
make build
make run

# Or run development version with hot reload
make dev

# Test the API
make test

# View logs
make logs

# Stop containers
make stop
```

### Option 2: Local Development

```bash
# 1. Setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Start local without docker
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Verify stuff works
curl http://localhost:8000/
```

### Docker

```bash
# Build image
docker-compose build

# Run production
docker-compose up -d orion-api

# Run development (with hot reload)
docker-compose --profile dev up -d orion-dev

# View logs
docker-compose logs -f

# Stop all
docker-compose down

# Clean up
make clean
```

## API Endpoints

### Root Endpoint

```bash
# Get API information
curl http://localhost:8000/

# Health check
curl http://localhost:8000/health
```

### File Upload - POST /v1/upload

Upload a file using multipart/form-data (mock implementation)

**Request:** `multipart/form-data`

- `file`: File to upload (required)
- `description`: Optional file description (optional)

**Examples:**

```bash
# Upload a text file
curl -X POST http://localhost:8000/v1/upload \
  -F "file=@example.txt" \
  -F "description=Sample text file"

# Upload a PDF file
curl -X POST http://localhost:8000/v1/upload \
  -F "file=@document.pdf" \
  -F "description=Important document"

# Upload without description
curl -X POST http://localhost:8000/v1/upload \
  -F "file=@image.jpg"
```

**Response:**

```json
{
  "message": "File uploaded successfully",
  "filename": "example.txt",
  "file_id": "uuid-1234-5678-9012",
  "file_size": 1024,
  "content_type": "text/plain"
}
```

### Query - POST /v1/query

Execute a query (mock implementation)

**Request:** `application/json`

```bash
# Basic query
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "query": "SELECT * FROM users",
      "filters": {"status": "active"}
    }
  }'

# Complex query with multiple filters
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "query": "SELECT id, name, email FROM users WHERE active = true",
      "filters": {
        "status": "active",
        "department": "engineering"
      },
      "limit": 50,
      "offset": 0
    }
  }'
```

**Response:**

```json
{
  "result": "{\"data\": [{\"id\": 1, \"name\": \"John Doe\", \"status\": \"active\"}], \"total\": 1}",
  "status": "success",
  "execution_time_ms": 101
}
```

## Development

### Code Quality

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

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🐳 Docker Setup

### Prerequisites

- **Docker Desktop** installed and running
- **Docker Compose** available
- **Make** (optional, for convenience commands)

### Quick Start with Docker

```bash
# 1. Validate Docker setup
./docker-test.sh

# 2. Build the Docker image
make build

# 3. Run production container
make run

# 4. Test the API
make test

# 5. View logs
make logs

# 6. Stop when done
make stop
```

### Validate Docker Setup

Before running, validate your Docker environment:

```bash
# Run the validation script
./docker-test.sh

# Or manually check
docker --version
docker-compose --version
docker info
```

### Development with Docker

```bash
# Run development container with hot reload
make dev

# The API will be available at http://localhost:8001
# Files are automatically reloaded
```

### Available Commands

| Command      | Description                                           |
| ------------ | ----------------------------------------------------- |
| `make build` | Build the Docker image                                |
| `make run`   | Run production container (port 8000)                  |
| `make dev`   | Run development container with hot reload (port 8001) |
| `make logs`  | View container logs                                   |
| `make test`  | Test all API endpoints                                |
| `make shell` | Open shell in running container                       |
| `make stop`  | Stop all containers                                   |
| `make clean` | Remove containers, images, and volumes                |

### Docker Features

#### 🔒 Security

- **Non-root user** - Runs as `orion` user for security
- **Minimal base image** - Python 3.11-slim for smaller attack surface
- **No unnecessary packages** - Only required dependencies

#### ⚡ Performance

- **Multi-stage build** - Optimized production image size
- **Layer caching** - Faster rebuilds
- **Production-ready** - Optimized for production workloads

#### 🛠 Development

- **Hot reload** - Automatic code reloading in dev mode
- **Volume mounts** - Live code changes without rebuilds
- **Debugging** - Easy access to logs and shell

#### 📊 Monitoring

- **Health checks** - Automatic container health monitoring
- **Structured logging** - JSON-formatted logs
- **Metrics** - Built-in FastAPI metrics

### Container Configuration

#### Production Container (`orion-api`)

- **Port**: 8000
- **User**: `orion` (non-root)
- **Volumes**:
  - `./uploads:/app/uploads` - File storage
  - `./logs:/app/logs` - Application logs
- **Health Check**: HTTP GET `/health`
- **Restart Policy**: `unless-stopped`

#### Development Container (`orion-dev`)

- **Port**: 8001
- **Features**: Hot reload, file watching
- **Volumes**: Source code mounted for live updates
- **Profile**: `dev` (use `--profile dev` to run)

### Environment Variables

| Variable                  | Default                                          | Description                       |
| ------------------------- | ------------------------------------------------ | --------------------------------- |
| `PYTHONPATH`              | `/app`                                           | Python path                       |
| `LOG_LEVEL`               | `INFO`                                           | Logging level                     |
| `PYTHONDONTWRITEBYTECODE` | `1`                                              | Disable .pyc files                |
| `PYTHONUNBUFFERED`        | `1`                                              | Unbuffered output                 |
| `UPLOAD_DIR`              | `./uploads` (local), `/app/uploads` (Docker)     | Directory for uploaded files      |
| `CONVERTED_DIR`           | `./converted` (local), `/app/converted` (Docker) | Directory for converted files     |
| `MAX_FILE_SIZE`           | `52428800`                                       | Maximum file size in bytes (50MB) |

### Troubleshooting

#### Container won't start

```bash
# Check Docker is running
docker info

# Check logs
make logs

# Rebuild from scratch
make clean && make build
```

#### Port already in use

```bash
# Check what's using port 8000
lsof -i :8000

# Use different port
docker-compose up -d -p 8002:8000
```

#### Permission issues

```bash
# Fix volume permissions
sudo chown -R $USER:$USER uploads/ logs/
```

### Deployment Options

#### Local Development

```bash
make dev  # Hot reload on port 8001
```

#### Production Server

```bash
make build && make run  # Production on port 8000
```

## Dependencies

- **FastAPI** 0.116.1 - Modern web framework
- **Uvicorn** 0.35.0 - ASGI server
- **Pydantic** 2.11.9 - Data validation
- **python-multipart** 0.0.20 - File upload support
