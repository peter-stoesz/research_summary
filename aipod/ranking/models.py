"""Ranking models."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ArticleScore(BaseModel):
    """Individual article score with breakdown."""

    article_id: int = Field(..., description="Article database ID")
    total_score: float = Field(..., description="Total combined score", ge=0.0, le=1.0)
    recency_score: float = Field(0.0, description="Recency score", ge=0.0, le=1.0)
    source_score: float = Field(0.0, description="Source weight score", ge=0.0, le=1.0)
    topic_score: float = Field(0.0, description="Topic relevance score", ge=0.0, le=1.0)
    novelty_score: float = Field(0.0, description="Novelty score", ge=0.0, le=1.0)
    preference_score: float = Field(0.0, description="User preference score", ge=0.0, le=1.0)
    reason: str = Field(..., description="Human-readable scoring reason")
    debug_info: Optional[Dict] = Field(None, description="Additional debug information")


class RankingResult(BaseModel):
    """Result of ranking articles."""

    run_id: int = Field(..., description="Run ID")
    total_articles: int = Field(..., description="Total articles considered")
    ranked_articles: List[ArticleScore] = Field(..., description="Ranked articles with scores")
    ranking_timestamp: datetime = Field(..., description="When ranking was performed")
    config_used: Dict = Field(..., description="Ranking configuration used")