"""Configuration management using pydantic-settings.

Loads from environment variables and .env files.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    agent_model: str = "gpt-4o"

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "my-code-agent"

    # Logging
    log_level: str = "INFO"


@lru_cache
def load_config() -> Settings:
    """Load and cache the application settings."""
    return Settings()
