"""Tests for upload endpoint validation."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import app

client = TestClient(app)


def test_file_size_validation_small_file():
    """Test that small files are accepted.

    Given: A small test file (1KB) within size limits
    When: We upload the small file
    Then: The upload should succeed with 201 status
    """
    test_content = b"A" * 1024

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response = client.post(
                "/v1/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={"email": "test@example.com", "description": "Small test file"},
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["file_size"] == 1024


def test_file_size_validation_large_file():
    """Test that files larger than max_file_size are rejected.

    Given: A file larger than the configured max size (50MB + 1KB)
    When: We attempt to upload the oversized file
    Then: The upload should be rejected with 413 status and appropriate error message
    """
    large_size = settings.max_file_size + 1024  # Just over the limit

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
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
                data={"email": "large@example.com", "description": "Large test file"},
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 413
    data = response.json()
    assert "File too large" in data["detail"]
    assert "50MB" in data["detail"]


def test_configuration_paths():
    """Test that configuration paths are properly set.

    Given: The application configuration is loaded
    When: We check configuration settings and path methods
    Then: All paths should be properly configured and return Path objects
    """
    assert settings.max_file_size == 50 * 1024 * 1024
    assert isinstance(settings.orion_base_path, Path)

    test_email = "config@test.com"
    assert isinstance(settings.get_user_base_path(test_email), Path)
    assert isinstance(settings.get_user_raw_uploads_path(test_email), Path)
