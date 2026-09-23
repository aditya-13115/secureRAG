from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class LLMSettings(BaseSettings):
    """
    Runtime configuration for SecureRAG's Groq layer.

    Multiple keys are configured through:

        GROQ_API_KEYS=key1,key2,key3

    A single GROQ_API_KEY is also supported as a fallback.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    groq_api_keys: str = Field(
        default="",
    )

    groq_api_key: str = Field(
        default="",
    )

    groq_model: str = Field(
        default="openai/gpt-oss-120b",
    )

    groq_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
    )

    groq_max_tokens: int = Field(
        default=1200,
        gt=0,
    )

    groq_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
    )

    groq_transient_cooldown_seconds: float = Field(
        default=3.0,
        ge=0.0,
    )

    rag_top_k: int = Field(
        default=8,
        ge=1,
        le=20,
    )

    rag_candidate_k: int = Field(
        default=30,
        ge=1,
        le=100,
    )

    rag_max_context_chars: int = Field(
        default=28000,
        gt=1000,
    )

    def get_groq_keys(self) -> tuple[str, ...]:
        """
        Return configured Groq keys in deterministic order.

        GROQ_API_KEYS takes precedence over GROQ_API_KEY.
        """

        keys: list[str] = []

        if self.groq_api_keys:
            keys.extend(
                key.strip()
                for key in self.groq_api_keys.split(",")
                if key.strip()
            )

        if not keys and self.groq_api_key.strip():
            keys.append(
                self.groq_api_key.strip()
            )

        # Remove duplicates while preserving order.
        unique_keys = tuple(
            dict.fromkeys(keys)
        )

        if not unique_keys:
            raise ValueError(
                "No Groq API keys configured. "
                "Set GROQ_API_KEYS in .env."
            )

        return unique_keys


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    return LLMSettings()