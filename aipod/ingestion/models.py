"""Data models for ingestion."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class FeedItem(BaseModel):
    """Parsed RSS feed item."""

    title: str = Field(..., description="Article title")
    link: str = Field(..., description="Article URL")
    published: Optional[datetime] = Field(None, description="Publication date")
    description: Optional[str] = Field(None, description="Article description/summary")
    source_name: str = Field(..., description="Source name")
    source_id: Optional[int] = Field(None, description="Source database ID")


class FeedResult(BaseModel):
    """Result of fetching an RSS feed."""

    source_name: str = Field(..., description="Source name")
    source_url: str = Field(..., description="RSS feed URL")
    success: bool = Field(..., description="Whether fetch was successful")
    items: list[FeedItem] = Field(default_factory=list, description="Parsed feed items")
    error: Optional[str] = Field(None, description="Error message if failed")
    item_count: int = Field(0, description="Number of items fetched")


class ArticleContent(BaseModel):
    """Extracted article content."""

    url: str = Field(..., description="Article URL")
    canonical_url: str = Field(..., description="Canonical URL")
    title: str = Field(..., description="Article title")
    text: str = Field(..., description="Extracted main text")
    outlet: Optional[str] = Field(None, description="Publishing outlet/domain")
    published_at: Optional[datetime] = Field(None, description="Publication date")
    content_hash: str = Field(..., description="Hash of normalized text")
    fetch_success: bool = Field(True, description="Whether fetch was successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    source_name: Optional[str] = Field(None, description="RSS source name")