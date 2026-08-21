"""Application settings, read from environment variables and .env (pydantic-settings)."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent_model: str = Field(default="claude-opus-5", alias="AGENT_MODEL")
    max_turns: int = Field(default=30, alias="MAX_TURNS")

    @field_validator("agent_model")
    @classmethod
    def _anthropic_only(cls, v: str) -> str:
        """This agent is Claude-only (langchain-anthropic). Catch leftover
        non-Claude values in .env early instead of a confusing API 404."""
        if not v.startswith("claude-"):
            raise ValueError(
                f"AGENT_MODEL={v!r} is not an Anthropic model. This agent uses "
                "langchain-anthropic — set it to a Claude model ID such as "
                "claude-opus-5, or remove AGENT_MODEL from .env to use the default."
            )
        return v