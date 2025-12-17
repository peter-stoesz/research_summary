"""Base model class for all database models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DBModel(BaseModel):
    """Base model for all database models."""

    id: Optional[int] = Field(None, description="Primary key")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }