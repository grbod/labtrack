"""Test Result schemas for request/response validation."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.enums import TestResultStatus


class TestResultBase(BaseModel):
    """Base test result schema."""

    test_type: str = Field(..., min_length=1, max_length=100)
    result_value: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    test_date: Optional[date] = None
    specification: Optional[str] = Field(None, max_length=100)
    method: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class TestResultCreate(TestResultBase):
    """Schema for creating a test result."""

    lot_id: int
    pdf_source: Optional[str] = None
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)


class TestResultUpdate(BaseModel):
    """Schema for updating a test result."""

    test_type: Optional[str] = Field(None, min_length=1, max_length=100)
    result_value: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    test_date: Optional[date] = None
    specification: Optional[str] = Field(None, max_length=100)
    method: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class TestResultResponse(BaseModel):
    """Test result response schema."""

    id: int
    lot_id: int
    test_type: str
    result_value: Optional[str] = None
    unit: Optional[str] = None
    test_date: Optional[date] = None
    pdf_source: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    status: TestResultStatus
    specification: Optional[str] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TestResultWithLotResponse(TestResultResponse):
    """Test result response with lot information."""

    lot_number: Optional[str] = None
    lot_reference: Optional[str] = None


class TestResultListResponse(BaseModel):
    """Paginated test result list response."""

    items: List[TestResultResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TestResultBulkCreate(BaseModel):
    """Schema for bulk creating test results."""

    lot_id: int
    results: List[TestResultBase]
    pdf_source: Optional[str] = None


class TestResultApproval(BaseModel):
    """Schema for approving/rejecting test results."""

    status: TestResultStatus
    notes: Optional[str] = None


class TestResultBulkApproval(BaseModel):
    """Schema for bulk approving test results."""

    result_ids: List[int]
    status: TestResultStatus
