# Orion SDK - Developer Setup Guide

Python SDK for the Orion document processing and search API.

## 🚀 Quick Setup

This is the developer setup guide for the Orion SDK. For comprehensive usage documentation, API reference, and examples, see the [Complete SDK Documentation](#-documentation).

### Prerequisites

- Python 3.8+
- Git
- Virtual environment tool (venv/conda)
- Running Orion API server (see [Orion API Setup](#-orion-api-setup))

### Development Setup

```bash
# 1. Clone the SDK repository
git clone https://github.com/orion/orion-sdk.git
cd orion-sdk

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install in development mode with dev dependencies
pip install -e .[dev]

# 4. Verify installation
python -c "from orion_sdk import OrionClient; print('✅ SDK installed successfully')"
```

### Quick Test

```bash
# Run the main example (requires Orion API running)
python example.py

# Run basic import tests
python tests/test_sdk_import.py
```

## 📦 Installation Options

### For End Users

```bash
# Install from PyPI (when published)
pip install orion-sdk

# Or install from source
pip install git+https://github.com/orion/orion-sdk.git
```

### For Developers

```bash
# Clone and install in development mode
git clone https://github.com/orion/orion-sdk.git
cd orion-sdk
pip install -e .[dev]
```

### Dependencies

- **Core**: Python 3.8+, requests >= 2.28.0, urllib3 >= 1.26.0
- **Development**: pytest, black, mypy, flake8, isort
- **Future**: aiohttp (for async support)

## ⚡ Quick Start

```python
from orion_sdk import OrionClient

# Initialize the client
client = OrionClient(base_url="http://localhost:8000")

# Upload a document
document = client.upload_document(
    file_path="./report.pdf",
    user_email="user@example.com"
)

# Search for content
response = client.search(
    query="machine learning",
    user_email="user@example.com"
)

print(f"Found {len(response.results)} results")
client.close()
```

For detailed examples and complete API documentation, see the [SDK Documentation](#-documentation).

## 🏗️ Development Workflow

### Project Structure

```
orion-sdk/
├── orion_sdk/              # Main SDK package
│   ├── client.py          # Main OrionClient
│   ├── models/            # Data models
│   ├── services/          # Service layer
│   ├── utils/             # Utilities
│   └── exceptions.py      # Error handling
├── examples/              # Usage examples
├── tests/                 # Test suite
├── docs/                  # Documentation
└── example.py            # Main example
```

### Development Commands

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
python tests/test_sdk_import.py

# Run examples
python example.py
python examples/basic_usage.py
python examples/upload_and_search.py
python examples/error_handling.py

# Code formatting
black orion_sdk/
isort orion_sdk/
flake8 orion_sdk/
mypy orion_sdk/
```

### Testing Your Changes

```bash
# 1. Basic import test
python -c "from orion_sdk import OrionClient; print('✅ Imports working')"

# 2. Client creation test
python -c "from orion_sdk import OrionClient; c = OrionClient(); c.close(); print('✅ Client creation working')"

# 3. Full workflow test (requires API)
python example.py
```

## 🏃‍♂️ Orion API Setup

The SDK requires the Orion API to be running. Here's how to set it up:

### Option 1: Docker (Recommended)

```bash
# From the main Orion project directory
cd /path/to/orion
export COHERE_API_KEY="your-cohere-api-key"
make dev
# API available at http://localhost:8001
```

### Option 2: Local Development

```bash
# From the main Orion project directory
cd /path/to/orion
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export COHERE_API_KEY="your-cohere-api-key"
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
# API available at http://localhost:8000
```

### Verify API is Running

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

## 📚 Documentation

### 📖 Complete SDK Documentation

For comprehensive usage documentation, API reference, examples, and advanced features:

**➡️ [Complete SDK Documentation](docs/README.md)**

This includes:

- Complete API reference with all methods and parameters
- Comprehensive examples and usage patterns
- Error handling guide with all exception types
- Configuration options and environment variables
- Performance optimization and best practices
- Troubleshooting guide for common issues
- Advanced usage patterns and integrations

### 🏗️ Orion System Architecture

To understand how the Orion system works under the hood:

**➡️ [Orion System Documentation](../docs/README.md)**

This includes:

- [Processing Pipeline Architecture](../docs/processing-pipeline.md) - How documents are processed
- [File Upload Processing](../docs/file-upload-processing.md) - Upload workflow and validation
- [Text Chunking & Storage](../docs/chunking-storage.md) - How text is chunked for search
- [Disk Storage Organization](../docs/disk-storage-organization.md) - File system layout
- [Developer Notes](../docs/Notes.md) - Development thoughts and considerations

### 🎯 Quick Navigation

Choose your path based on what you want to do:

| **I want to...**                 | **Go to**                                                    |
| -------------------------------- | ------------------------------------------------------------ |
| **Use the SDK in my project**    | [Complete SDK Documentation](docs/README.md)                 |
| **Run the examples**             | [`examples/`](examples/) directory                           |
| **Understand the API endpoints** | [Complete SDK Documentation](docs/README.md#api-reference)   |
| **Handle errors properly**       | [Complete SDK Documentation](docs/README.md#error-handling)  |
| **Contribute to the SDK**        | Continue reading this README                                 |
| **Understand how Orion works**   | [Orion System Documentation](../docs/README.md)              |
| **See the processing pipeline**  | [Processing Pipeline](../docs/processing-pipeline.md)        |
| **Understand file storage**      | [Storage Organization](../docs/disk-storage-organization.md) |

## 🧪 Running Examples

The SDK includes several examples to demonstrate different use cases:

### Main Example

```bash
# Complete workflow with document upload and search
python example.py
```

### Specific Examples

```bash
cd examples/

# Basic operations and library exploration
python basic_usage.py

# Upload multiple documents and search
python upload_and_search.py

# Comprehensive error handling patterns
python error_handling.py
```

### Example Requirements

- Orion API running on `http://localhost:8000`
- Cohere API key configured in the Orion API
- Python 3.8+ with SDK installed

## 🤝 Contributing

### Development Setup

1. **Fork and clone**:

   ```bash
   git clone https://github.com/your-username/orion-sdk.git
   cd orion-sdk
   ```

2. **Setup environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e .[dev]
   ```

3. **Make changes** and test:

   ```bash
   # Test imports
   python tests/test_sdk_import.py

   # Test with live API
   python example.py
   ```

4. **Format code**:

   ```bash
   black orion_sdk/
   isort orion_sdk/
   flake8 orion_sdk/
   ```

5. **Submit PR** with description of changes

### Guidelines

- Follow existing code style (black, isort, flake8)
- Add tests for new functionality
- Update documentation for API changes
- Test with both development and production setups

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support & Issues

- **🐛 Bug Reports**: [GitHub Issues](https://github.com/orion/orion-sdk/issues)
- **💡 Feature Requests**: [GitHub Issues](https://github.com/orion/orion-sdk/issues)
- **📧 Questions**: support@orion.ai
- **📚 Documentation**: [Complete SDK Docs](docs/README.md)
