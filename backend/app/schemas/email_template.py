"""Email template schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EmailTemplateVariable(BaseModel):
    """Schema for a single template variable."""

    key: str
    description: str


class EmailTemplateVariablesResponse(BaseModel):
    """Response schema for available template variables."""

    variables: List[EmailTemplateVariable]


class EmailTemplateBase(BaseModel):
    """Base email template schema."""

    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)


class EmailTemplateUpdate(EmailTemplateBase):
    """Schema for updating an email template."""

    pass


class EmailTemplateResponse(BaseModel):
    """Email template response schema."""

    id: int
    name: str
    subject: str
    body: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmailTemplatePreview(BaseModel):
    """Preview of rendered email template."""

    subject: str
    body: str
