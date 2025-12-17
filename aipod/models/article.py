"""Article model for storing fetched and processed articles."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from .base import DBModel


class Article(DBModel):
    """Article model."""

    source_id: int = Field(..., description="Foreign key to sources table")
    canonical_url: str = Field(..., description="Canonical URL of the article")
    title: str = Field(..., description="Article title")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    outlet: Optional[str] = Field(None, description="Publishing outlet/domain")
    content_hash: str = Field(..., description="Hash of normalized article text")
    extracted_path: str = Field(..., description="File path to extracted text")
    first_seen_at: datetime = Field(..., description="When we first saw this article")
    last_seen_at: datetime = Field(..., description="Last run where it appeared")