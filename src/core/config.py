"""Configuration settings for the application."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Orion API"
    app_version: str = "0.0.1"
    debug: bool = False
    log_level: str = "INFO"

    # File handling settings
    orion_base_dir: str = "./orion"  # Base directory for all user data
    max_file_size: int = 50 * 1024 * 1024  # 50MB in bytes

    # Text processing settings
    chunk_size: int = 512  # Number of tokens per chunk
    chunk_overlap_percent: float = 0.1  # 10% overlap between chunks
    tiktoken_encoding: str = "cl100k_base"  # GPT-4 encoding

    # Cohere API settings
    cohere_api_key: str = ""  # Set via environment variable
    cohere_model: str = "embed-english-v3.0"  # Cohere embedding model

    # Storage settings
    vector_storage_type: str = "json"  # "json", "hdf5" - HDF5 is more efficient for large datasets

    @property
    def orion_base_path(self) -> Path:
        """Get orion base directory as Path object."""
        return Path(self.orion_base_dir)

    def get_user_base_path(self, email: str) -> Path:
        """Get user's base directory path."""
        return self.orion_base_path / email

    def get_user_raw_uploads_path(self, email: str) -> Path:
        """Get user's raw uploads directory path."""
        return self.get_user_base_path(email) / "raw_uploads"

    def get_user_processed_text_path(self, email: str) -> Path:
        """Get user's processed text directory path."""
        return self.get_user_base_path(email) / "processed_text"

    def get_user_raw_chunks_path(self, email: str) -> Path:
        """Get user's raw chunks directory path."""
        return self.get_user_base_path(email) / "raw_chunks"

    def get_user_processed_vectors_path(self, email: str) -> Path:
        """Get user's processed vectors directory path."""
        return self.get_user_base_path(email) / "processed_vectors"

    def create_user_directories(self, email: str) -> None:
        """Create all necessary directories for a user."""
        directories = [
            self.get_user_raw_uploads_path(email),
            self.get_user_processed_text_path(email),
            self.get_user_raw_chunks_path(email),
            self.get_user_processed_vectors_path(email),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
