# -*- coding: utf-8 -*-
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Application settings.

    Settings are loaded from environment variables with optional .env file support.
    Environment-specific settings are automatically applied based on APP_ENV.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    app_env: Environment = Environment.DEVELOPMENT

    # App
    app_name: str = "Chalssak"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Google Gemini
    google_api_key: str = ""

    # Google Drive Integration (OAuth)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:3000/integrations/google-drive/callback"

    # File Search
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = [".pdf", ".txt", ".docx"]

    # Database
    database_url: str = "sqlite:///./data/chalssak.db"

    # Channel Lifecycle
    channel_inactive_days: int = 90  # Days before channel is considered inactive
    max_files_per_channel: int = 100
    max_channel_size_mb: int = 500

    # CORS (comma-separated origins for production)
    cors_origins: str = "*"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" for production, "console" for development

    # Sentry (Error Tracking)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.1

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.app_env == Environment.TEST

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
