"""Configuration settings for the application."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Orion API"
    app_version: str = "0.0.1"
    debug: bool = False
    log_level: str = "INFO"

    # File handling settings
    upload_dir: str = "./uploads"
    converted_dir: str = "./converted"
    max_file_size: int = 50 * 1024 * 1024  # 50MB in bytes

    @property
    def upload_path(self) -> Path:
        """Get upload directory as Path object."""
        return Path(self.upload_dir)

    @property
    def converted_path(self) -> Path:
        """Get converted directory as Path object."""
        return Path(self.converted_dir)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
