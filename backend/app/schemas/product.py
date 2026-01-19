"""Product schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


# Product Size schemas
class ProductSizeBase(BaseModel):
    """Base schema for product size."""

    size: str = Field(..., min_length=1, max_length=50)


class ProductSizeCreate(ProductSizeBase):
    """Schema for creating a product size."""

    pass


class ProductSizeUpdate(BaseModel):
    """Schema for updating a product size."""

    size: str = Field(..., min_length=1, max_length=50)


class ProductSizeResponse(ProductSizeBase):
    """Product size response schema."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductSizeSimple(BaseModel):
    """Simplified product size for listing (id and size only)."""

    id: int
    size: str

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    """Base product schema."""

    brand: str = Field(..., min_length=1, max_length=100)
    product_name: str = Field(..., min_length=1, max_length=200)
    flavor: Optional[str] = Field(None, max_length=100)
    size: Optional[str] = Field(None, max_length=50)  # Legacy field, kept for backward compatibility
    display_name: str = Field(..., min_length=1)
    serving_size: Optional[str] = Field(None, max_length=50)  # e.g., "30g", "2 capsules"
    expiry_duration_months: int = Field(default=36, gt=0)
    version: Optional[str] = Field(None, max_length=20)  # e.g., "v1", "v2.1"


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
    version: Optional[str] = Field(None, max_length=20)
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
    size: Optional[str] = None  # Legacy field
    sizes: List[ProductSizeSimple] = []  # Multiple size variants
    display_name: str
    serving_size: Optional[str] = None
    expiry_duration_months: int
    version: Optional[str] = None
    is_active: bool = True
    archived_at: Optional[datetime] = None
    archived_by_id: Optional[int] = None
    archive_reason: Optional[str] = None
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
    version: Optional[str] = None

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


class ArchiveRequest(BaseModel):
    """Schema for archiving a product, lab test type, or customer."""

    reason: str = Field(..., min_length=1, max_length=500)
