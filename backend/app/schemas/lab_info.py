"""Lab info schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LabInfoUpdate(BaseModel):
    """Schema for updating lab info."""

    company_name: str = Field(..., min_length=1, max_length=200)
    address: str = Field("", max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    city: str = Field("", max_length=100)
    state: str = Field("", max_length=50)
    zip_code: str = Field("", max_length=20)
    require_pdf_for_submission: Optional[bool] = None


class LabInfoResponse(BaseModel):
    """Lab info response schema."""

    id: int
    company_name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: str
    email: str
    logo_url: Optional[str] = None  # Computed full URL for frontend
    signature_url: Optional[str] = None  # Computed full URL for signature
    signer_name: Optional[str] = None
    require_pdf_for_submission: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LogoUploadResponse(BaseModel):
    """Response after logo upload."""

    logo_url: str
    filename: str
