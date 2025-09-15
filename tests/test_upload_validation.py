"""Tests for upload endpoint validation."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import app

client = TestClient(app)


def test_file_size_validation_small_file():
    """Test that small files are accepted."""
    # Create a small test file (1KB)
    test_content = b"A" * 1024

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response = client.post(
                "/v1/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={"description": "Small test file"},
            )

    # Clean up
    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["file_size"] == 1024


def test_file_size_validation_large_file():
    """Test that files larger than max_file_size are rejected."""
    # Create a file larger than the configured max size
    large_size = settings.max_file_size + 1024  # Just over the limit

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        # Write in chunks to avoid memory issues
        chunk_size = 1024 * 1024  # 1MB chunks
        remaining = large_size

        while remaining > 0:
            chunk = b"A" * min(chunk_size, remaining)
            tmp_file.write(chunk)
            remaining -= len(chunk)

        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response = client.post(
                "/v1/upload",
                files={"file": ("large_test.txt", f, "text/plain")},
                data={"description": "Large test file"},
            )

    # Clean up
    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 413
    data = response.json()
    assert "File too large" in data["detail"]
    assert "50MB" in data["detail"]


def test_configuration_paths():
    """Test that configuration paths are properly set."""
    assert settings.max_file_size == 50 * 1024 * 1024
    assert isinstance(settings.upload_path, Path)
    assert isinstance(settings.converted_path, Path)
