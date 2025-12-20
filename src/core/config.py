# -*- coding: utf-8 -*-
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # App
    app_name: str = "Chalssak"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Google Gemini
    google_api_key: str = ""

    # File Search
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = [".pdf", ".txt", ".docx"]

    # Database
    database_url: str = "sqlite:///./data/chalssak.db"

    # Channel Lifecycle
    channel_inactive_days: int = 90  # Days before channel is considered inactive
    max_files_per_channel: int = 100
    max_channel_size_mb: int = 500


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
