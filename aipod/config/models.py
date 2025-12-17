"""Configuration models."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PostgresConfig(BaseModel):
    """Postgres configuration."""

    host: str = Field("localhost", description="Database host")
    port: int = Field(5432, description="Database port")
    database: str = Field("aipod", description="Database name")
    user: str = Field("aipod_user", description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    password_env: Optional[str] = Field(None, description="Environment variable for password")


class RunDefaults(BaseModel):
    """Default run parameters."""

    minutes: int = Field(12, description="Default target minutes", ge=1, le=60)
    max_items: int = Field(150, description="Max RSS items to process", ge=1, le=1000)
    max_stories: int = Field(20, description="Max stories for output", ge=1, le=100)


class RankingConfig(BaseModel):
    """Ranking configuration."""

    recency_weight: float = Field(0.3, ge=0.0, le=1.0)
    source_weight: float = Field(0.2, ge=0.0, le=1.0)
    topic_weight: float = Field(0.3, ge=0.0, le=1.0)
    novelty_weight: float = Field(0.2, ge=0.0, le=1.0)
    novelty_window_runs: int = Field(4, ge=1, le=10)

    @field_validator("recency_weight", "source_weight", "topic_weight", "novelty_weight")
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        """Validate that weights sum to 1.0."""
        if info.field_name == "novelty_weight":
            # Last weight, check sum
            total = (
                info.data.get("recency_weight", 0.3)
                + info.data.get("source_weight", 0.2)
                + info.data.get("topic_weight", 0.3)
                + v
            )
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class PreferencesConfig(BaseModel):
    """User preferences for content."""

    boost_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to boost in ranking"
    )
    suppress_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to suppress in ranking"
    )


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field("openai", description="LLM provider (openai, ollama)")
    model: str = Field("gpt-4o-mini", description="Model name")
    api_key_env: Optional[str] = Field(None, description="Environment variable for API key")
    api_key: Optional[str] = Field(None, description="API key (prefer api_key_env)")
    base_url: Optional[str] = Field(None, description="Base URL for API (e.g., for Ollama)")


class ConfigModel(BaseModel):
    """Main configuration model."""

    workspace_root: str = Field("~/AI-Podcast", description="Root directory for outputs")
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    run_defaults: RunDefaults = Field(default_factory=RunDefaults)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    preferences: PreferencesConfig = Field(default_factory=PreferencesConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


class SourceConfig(BaseModel):
    """Source configuration from sources.yaml."""

    name: str = Field(..., description="Source name")
    url: str = Field(..., description="RSS feed URL")
    category: str = Field(..., description="Source category")
    weight: float = Field(1.0, description="Source weight", ge=0.0, le=1.0)
    enabled: bool = Field(True, description="Whether source is enabled")