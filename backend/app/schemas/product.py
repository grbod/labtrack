"""Product schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class ProductBase(BaseModel):
    """Base product schema."""

    brand: str = Field(..., min_length=1, max_length=100)
    product_name: str = Field(..., min_length=1, max_length=200)
    flavor: Optional[str] = Field(None, max_length=100)
    size: Optional[str] = Field(None, max_length=50)
    display_name: str = Field(..., min_length=1)
    serving_size: Optional[str] = Field(None, max_length=50)  # e.g., "30g", "2 capsules"
    expiry_duration_months: int = Field(default=36, gt=0)


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    brand: Optional[str] = Field(None, min_length=1, max_length=100)
    product_name: Optional[str] = Field(None, min_length=1, max_length=200)
    flavor: Optional[str] = Field(None, max_length=100)
    size: Optional[str] = Field(None, max_length=50)
    display_name: Optional[str] = Field(None, min_length=1)
    serving_size: Optional[str] = Field(None, max_length=50)
    expiry_duration_months: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class TestSpecificationResponse(BaseModel):
    """Test specification within a product response."""

    id: int
    lab_test_type_id: int
    test_name: str
    test_category: Optional[str] = None
    test_method: Optional[str] = None
    test_unit: Optional[str] = None
    specification: str
    is_required: bool

    model_config = {"from_attributes": True}


class TestSpecificationCreate(BaseModel):
    """Schema for creating a test specification."""

    lab_test_type_id: int
    specification: str = Field(..., min_length=1, max_length=100)
    is_required: bool = True


class TestSpecificationUpdate(BaseModel):
    """Schema for updating a test specification."""

    specification: Optional[str] = Field(None, min_length=1, max_length=100)
    is_required: Optional[bool] = None


class ProductResponse(BaseModel):
    """Product response schema."""

    id: int
    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    display_name: str
    serving_size: Optional[str] = None
    expiry_duration_months: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductWithSpecsResponse(ProductResponse):
    """Product response with test specifications."""

    test_specifications: List[TestSpecificationResponse] = []


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductBulkImportRow(BaseModel):
    """Schema for a single row in bulk import."""

    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    display_name: str
    serving_size: Optional[str] = None
    expiry_duration_months: int = 36

    @field_validator("brand", "product_name", "display_name", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class ProductBulkImportResult(BaseModel):
    """Result of bulk import operation."""

    total_rows: int
    imported: int
    skipped: int
    errors: List[str]
