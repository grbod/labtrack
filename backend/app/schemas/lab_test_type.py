"""Lab Test Type schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class LabTestTypeBase(BaseModel):
    """Base lab test type schema."""

    test_name: str = Field(..., min_length=1, max_length=100)
    test_category: str = Field(..., min_length=1, max_length=50)
    default_unit: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    test_method: Optional[str] = Field(None, max_length=100)
    abbreviations: Optional[str] = None
    default_specification: Optional[str] = Field(None, max_length=100)


class LabTestTypeCreate(LabTestTypeBase):
    """Schema for creating a lab test type."""

    pass


class LabTestTypeUpdate(BaseModel):
    """Schema for updating a lab test type."""

    test_name: Optional[str] = Field(None, min_length=1, max_length=100)
    test_category: Optional[str] = Field(None, min_length=1, max_length=50)
    default_unit: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    test_method: Optional[str] = Field(None, max_length=100)
    abbreviations: Optional[str] = None
    default_specification: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class LabTestTypeResponse(BaseModel):
    """Lab test type response schema."""

    id: int
    test_name: str
    test_category: str
    default_unit: Optional[str] = None
    description: Optional[str] = None
    test_method: Optional[str] = None
    abbreviations: Optional[str] = None
    default_specification: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LabTestTypeListResponse(BaseModel):
    """Paginated lab test type list response."""

    items: List[LabTestTypeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabTestTypeCategoryCount(BaseModel):
    """Category with count of test types."""

    category: str
    count: int


class LabTestTypeBulkImportRow(BaseModel):
    """Schema for a single row in bulk import."""

    test_name: str
    test_category: str
    default_unit: Optional[str] = None
    description: Optional[str] = None
    test_method: Optional[str] = None
    abbreviations: Optional[str] = None
    default_specification: Optional[str] = None


class LabTestTypeBulkImportResult(BaseModel):
    """Result of bulk import operation."""

    total_rows: int
    imported: int
    skipped: int
    errors: List[str]
