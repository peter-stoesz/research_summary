"""Cluster models for grouping related articles."""

from typing import Any, Dict, Optional

from pydantic import Field

from .base import DBModel


class Cluster(DBModel):
    """Article cluster model."""

    run_id: int = Field(..., description="Foreign key to runs table")
    representative_article_id: int = Field(..., description="Foreign key to representative article")
    title: Optional[str] = Field(None, description="Cluster title")
    cluster_metadata: Optional[Dict[str, Any]] = Field(None, description="Cluster metadata (e.g., embedding centroid)")


class ClusterMember(DBModel):
    """Cluster membership model."""

    cluster_id: int = Field(..., description="Foreign key to clusters table")
    article_id: int = Field(..., description="Foreign key to articles table")