"""
Thérèse Server - Configuration

Settings with pydantic-settings for type-safe configuration.
Supports PostgreSQL (prod) and SQLite (dev).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Thérèse Server"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./therese.db"
    # PostgreSQL: postgresql+asyncpg://user:pass@host:5432/therese

    # Paths
    data_dir: Path = Path("/var/lib/therese")
    upload_dir: Path | None = None  # Set in model_post_init

    # Auth (JWT)
    secret_key: str = "changeme-generate-with-openssl-rand-hex-32"
    jwt_secret: str = "changeme-generate-with-openssl-rand-hex-32"
    jwt_lifetime_seconds: int = 3600
    jwt_refresh_lifetime_seconds: int = 604800  # 7 jours

    # LLM Configuration
    llm_provider: Literal["claude", "mistral", "ollama", "openai", "gemini"] = "claude"
    anthropic_api_key: str | None = None
    mistral_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    ollama_url: str = "http://localhost:11434"

    # Default models
    claude_model: str = "claude-sonnet-4-6"
    mistral_model: str = "mistral-large-latest"
    ollama_model: str = "mistral:7b"

    # Embeddings
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimensions: int = 768

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "therese-docs"

    # Encryption (Fernet)
    encryption_key: str | None = None

    # Performance
    max_context_tokens: int = 8000
    max_memory_results: int = 10
    chunk_size: int = 500
    chunk_overlap: int = 50

    # RGPD
    data_retention_days: int = 1095  # 3 ans
    audit_log_enabled: bool = True

    # Domain
    domain: str = "localhost"

    @model_validator(mode="after")
    def check_secrets_in_production(self) -> "Settings":
        """Bloquer les secrets par défaut en production."""
        if self.environment == "production":
            if "changeme" in self.jwt_secret:
                raise RuntimeError(
                    "jwt_secret contient 'changeme' - interdit en production. "
                    "Générez une clé avec : openssl rand -hex 32"
                )
            if "changeme" in self.secret_key:
                raise RuntimeError(
                    "secret_key contient 'changeme' - interdit en production. "
                    "Générez une clé avec : openssl rand -hex 32"
                )
        return self

    def model_post_init(self, __context) -> None:
        """Initialize paths after settings are loaded."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.upload_dir is None:
            self.upload_dir = self.data_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
