from __future__ import annotations

from enum import Enum
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: LLMProvider = LLMProvider.OPENAI

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    tavily_api_key: str = ""
    serpapi_api_key: str = ""
    google_maps_api_key: str = ""

    openai_model: str = "gpt-5.4-2026-03-05"
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_model: str = "gemini-2.0-flash"

    max_iterations: int = 10
    confidence_threshold: float = 0.8

    tmp_dir: str = "tmp"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm(
    provider: LLMProvider | None = None,
    temperature: float = 0.2,
) -> BaseChatModel:
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    if provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    if provider == LLMProvider.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.google_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")
