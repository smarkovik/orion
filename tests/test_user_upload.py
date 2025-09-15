"""Tests for user-based upload functionality."""

import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import app

client = TestClient(app)


def test_user_upload_creates_directories():
    """Test that uploading creates user directories.

    Given: A user uploads a file for the first time
    When: The upload API is called with a valid email and file
    Then: User-specific directories should be created and file saved in raw_uploads
    """
    test_email = f"upload_test_{uuid.uuid4().hex[:8]}@example.com"
    test_content = b"Test file content"

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response = client.post(
                "/v1/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={
                    "email": test_email,
                    "description": "Test file for user directories",
                },
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["file_size"] == len(test_content)
    assert test_email in data["message"]

    user_base = settings.get_user_base_path(test_email)
    assert user_base.exists()
    assert settings.get_user_raw_uploads_path(test_email).exists()
    assert settings.get_user_processed_text_path(test_email).exists()
    assert settings.get_user_raw_chunks_path(test_email).exists()
    assert settings.get_user_processed_vectors_path(test_email).exists()

    raw_uploads_dir = settings.get_user_raw_uploads_path(test_email)
    uploaded_files = list(raw_uploads_dir.glob("*_test.txt"))
    assert len(uploaded_files) == 1

    uploaded_file = uploaded_files[0]
    assert uploaded_file.read_bytes() == test_content


def test_invalid_email_format():
    """Test that invalid email formats are rejected.

    Given: A file upload request with an invalid email format
    When: The upload API is called with the malformed email
    Then: The request should be rejected with 400 status and appropriate error message
    """
    test_content = b"Test content"

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response = client.post(
                "/v1/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={"email": "invalid-email", "description": "Test file"},
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    assert response.status_code == 400
    data = response.json()
    assert "Invalid email format" in data["detail"]


def test_multiple_users_separate_folders():
    """Test that different users get separate folders.

    Given: Two different users upload files
    When: Both users upload files with their respective email addresses
    Then: Each user should have separate directory structures and files
    """
    user1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    test_content = b"Test content"

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response1 = client.post(
                "/v1/upload",
                files={"file": ("user1_file.txt", f, "text/plain")},
                data={"email": user1_email},
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            response2 = client.post(
                "/v1/upload",
                files={"file": ("user2_file.txt", f, "text/plain")},
                data={"email": user2_email},
            )

    Path(tmp_file.name).unlink(missing_ok=True)

    assert response1.status_code == 201
    assert response2.status_code == 201

    user1_dir = settings.get_user_raw_uploads_path(user1_email)
    user2_dir = settings.get_user_raw_uploads_path(user2_email)

    assert user1_dir.exists()
    assert user2_dir.exists()
    assert user1_dir != user2_dir

    user1_files = list(user1_dir.glob("*_user1_file.txt"))
    user2_files = list(user2_dir.glob("*_user2_file.txt"))

    assert len(user1_files) == 1
    assert len(user2_files) == 1


def test_configuration_user_paths():
    """Test that configuration user path methods work correctly.

    Given: A user email and the configuration system
    When: We call user path methods and create directories
    Then: All paths should be correctly formatted and directories should be created
    """
    test_email = "config@test.com"

    user_base = settings.get_user_base_path(test_email)
    raw_uploads = settings.get_user_raw_uploads_path(test_email)
    processed_text = settings.get_user_processed_text_path(test_email)
    raw_chunks = settings.get_user_raw_chunks_path(test_email)
    processed_vectors = settings.get_user_processed_vectors_path(test_email)

    assert str(user_base).endswith(test_email)
    assert str(raw_uploads).endswith(f"{test_email}/raw_uploads")
    assert str(processed_text).endswith(f"{test_email}/processed_text")
    assert str(raw_chunks).endswith(f"{test_email}/raw_chunks")
    assert str(processed_vectors).endswith(f"{test_email}/processed_vectors")

    settings.create_user_directories(test_email)

    assert user_base.exists()
    assert raw_uploads.exists()
    assert processed_text.exists()
    assert raw_chunks.exists()
    assert processed_vectors.exists()
