"""Data models for generation."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ArticleSummary(BaseModel):
    """Summary of a single article."""

    article_id: int = Field(..., description="Article database ID")
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    outlet: str = Field(..., description="Publishing outlet")
    published_date: Optional[str] = Field(None, description="Publication date (formatted)")
    bullet_points: List[str] = Field(..., description="Summary bullet points")
    category: str = Field(..., description="Article category")


class ShowNotesSection(BaseModel):
    """Section in show notes."""

    title: str = Field(..., description="Section title")
    articles: List[ArticleSummary] = Field(..., description="Articles in this section")


class ShowNotes(BaseModel):
    """Complete show notes."""

    run_date: str = Field(..., description="Run date")
    sections: List[ShowNotesSection] = Field(..., description="Show notes sections")
    total_articles: int = Field(..., description="Total number of articles")
    generation_timestamp: str = Field(..., description="When notes were generated")


class Script(BaseModel):
    """Generated narration script."""

    run_date: str = Field(..., description="Run date")
    target_minutes: int = Field(..., description="Target reading time in minutes")
    content: str = Field(..., description="Full script content")
    estimated_words: int = Field(..., description="Estimated word count")
    estimated_minutes: float = Field(..., description="Estimated reading time")
    generation_timestamp: str = Field(..., description="When script was generated")


class GenerationStats(BaseModel):
    """Statistics for generation process."""

    articles_processed: int = Field(..., description="Number of articles processed")
    tokens_used: int = Field(0, description="Total tokens used")
    api_calls: int = Field(0, description="Number of API calls made")
    cost_estimate: float = Field(0.0, description="Estimated cost in USD")
    processing_time: float = Field(0.0, description="Processing time in seconds")