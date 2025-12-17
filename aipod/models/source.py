"""Source model for RSS feed sources."""

from pydantic import Field

from .base import DBModel


class Source(DBModel):
    """RSS feed source model."""

    name: str = Field(..., description="Source name")
    url: str = Field(..., description="RSS feed URL")
    category: str = Field(..., description="Source category (implementations, concepts, research)")
    weight: float = Field(1.0, description="Source weight for ranking", ge=0.0, le=1.0)
    enabled: bool = Field(True, description="Whether the source is enabled")