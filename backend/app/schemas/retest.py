"""Retest schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import RetestStatus


class RetestItemBase(BaseModel):
    """Base retest item schema."""

    test_result_id: int


class RetestItemResponse(BaseModel):
    """Retest item response schema."""

    id: int
    test_result_id: int
    original_value: Optional[str] = None
    current_value: Optional[str] = None  # Current test result value
    test_type: Optional[str] = None  # Denormalized for display

    model_config = {"from_attributes": True}


class CreateRetestRequest(BaseModel):
    """Schema for creating a retest request."""

    test_result_ids: List[int] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=2000)


class RetestRequestResponse(BaseModel):
    """Retest request response schema."""

    id: int
    lot_id: int
    reference_number: str
    retest_number: int
    reason: str
    status: RetestStatus
    requested_by_id: int
    requested_by_name: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    items: List[RetestItemResponse] = []

    model_config = {"from_attributes": True}


class RetestRequestListResponse(BaseModel):
    """List of retest requests response."""

    items: List[RetestRequestResponse]
    total: int


class CompleteRetestRequest(BaseModel):
    """Schema for manually completing a retest."""

    pass  # No additional fields needed, just the action


class RetestOriginalValue(BaseModel):
    """Schema for returning original value info for a test result."""

    test_result_id: int
    original_value: Optional[str] = None
    retest_reference: str
    retest_status: RetestStatus
