"""Application configuration and environment settings for MBI Labs Oracle Engine.

This module centralizes configuration using `pydantic-settings`. It
reads values from the process environment and the local `.env` file
in the backend directory. Use the `settings` singleton or the
`get_settings()` helper in dependencies instead of instantiating
`Settings` directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed configuration model for the MBI Oracle Engine backend."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "MBI Labs Oracle Engine"
    environment: str = "local"
    log_level: str = "INFO"

    # Database
    database_url: str

    # JWT Auth
    jwt_secret: str
    jwt_access_ttl_minutes: int = 1440
    jwt_refresh_ttl_days: int = 30

    # Admin seed
    admin_email: str = "admin@mbilabs.io"
    admin_password: str = "change-me-on-first-login"

    # MinIO (artifact storage)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    # Artifact store path
    artifact_store_path: str = "~/.mbi/artifacts"

    # CORS
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    def get_artifact_store_path(self) -> Path:
        """Return the resolved artifact store path, expanding ~."""
        return Path(self.artifact_store_path).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of `Settings` loaded from the environment."""
    return Settings()


settings = get_settings()
