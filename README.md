# Orion

Python project with virtual environment setup.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## Development

```bash
# Tests
pytest --cov=src

# Code quality
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

## Structure

```
src/                    # Source code
tests/                  # Unit tests
docs/                   # Documentation
requirements.txt        # Core dependencies
requirements-dev.txt    # Development dependencies
```