"""Run models for tracking pipeline executions."""

from datetime import date, datetime
from typing import Any, Dict, Optional

from pydantic import Field

from .base import DBModel


class Run(DBModel):
    """Pipeline run model."""

    run_date: date = Field(..., description="Logical date of the run")
    started_at: datetime = Field(..., description="When the run started")
    finished_at: Optional[datetime] = Field(None, description="When the run finished")
    status: str = Field("running", description="Run status (success, failed, running)")
    stats_json: Optional[Dict[str, Any]] = Field(None, description="Aggregate run statistics")


class RunArticle(DBModel):
    """Link between runs and articles processed during that run."""

    run_id: int = Field(..., description="Foreign key to runs table")
    article_id: int = Field(..., description="Foreign key to articles table")
    included_in_rank: bool = Field(False, description="Whether article was included in ranking")
    score_json: Optional[Dict[str, Any]] = Field(None, description="Ranking breakdown if evaluated")