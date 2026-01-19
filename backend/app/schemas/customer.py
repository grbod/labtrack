"""Customer schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator


class CustomerBase(BaseModel):
    """Base schema for customer data."""

    company_name: str = Field(..., min_length=1, max_length=255)
    contact_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""

    @field_validator("company_name", "contact_name", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class CustomerUpdate(BaseModel):
    """Schema for updating a customer. All fields are optional."""

    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None

    @field_validator("company_name", "contact_name", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class CustomerResponse(CustomerBase):
    """Customer response schema with all fields."""

    id: int
    is_active: bool
    archived_at: Optional[datetime] = None
    archived_by_id: Optional[int] = None
    archive_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    """Paginated customer list response."""

    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
