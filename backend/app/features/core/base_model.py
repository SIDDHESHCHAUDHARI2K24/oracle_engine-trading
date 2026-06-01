"""Shared Pydantic base schemas for API models.

These classes provide common configuration and timestamp fields that
can be reused across feature-specific request and response models.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema configured for ORM-style objects (`from_attributes=True`)."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(BaseSchema):
    """Schema mixin that adds optional creation and update timestamps."""

    created_at: datetime | None = None
    updated_at: datetime | None = None

