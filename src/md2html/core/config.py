"""Application settings.

Single source of truth for runtime configuration. Pydantic-settings reads
from environment variables and an optional `.env` file in the project root.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the MD2HTML service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database (used by the conversion-history persistence added in later
    # scaffold groups). aiosqlite wants a plain filesystem path, NOT a
    # `sqlite:///...` URL.
    database_path: str = Field(
        default="md2html.db",
        description="Filesystem path to the SQLite database file.",
    )

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Origins allowed by CORS. Defaults to wildcard for dev.",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Loguru/logging level (DEBUG, INFO, WARNING, ERROR).",
    )

    # Conversion defaults
    default_doc_title: str = Field(
        default="MD2HTML Output",
        description="Title used when wrapping body HTML in a full document.",
    )

    max_markdown_bytes: int = Field(
        default=1_048_576,
        description="Hard cap on accepted markdown body size (1 MiB).",
    )

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log level: {v}")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        """Accept a comma-separated string or a JSON list."""
        if isinstance(v, str) and not v.startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
