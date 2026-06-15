"""Lot schemas for request/response validation."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import LotStatus, LotType


class ProductReference(BaseModel):
    """Reference to a product in a lot."""

    product_id: int
    percentage: Optional[Decimal] = None
    batch_number: Optional[str] = Field(None, max_length=50)


class LotBase(BaseModel):
    """Base lot schema."""

    lot_number: str = Field(..., min_length=1, max_length=50)
    lot_type: LotType = LotType.STANDARD
    mfg_date: Optional[date] = None
    exp_date: Optional[date] = None
    generate_coa: bool = True


class LotCreate(LotBase):
    """Schema for creating a lot."""

    products: List[ProductReference] = Field(default_factory=list)
    reference_number: Optional[str] = None  # Auto-generated if not provided


class LotUpdate(BaseModel):
    """Schema for updating a lot."""

    lot_number: Optional[str] = Field(None, min_length=1, max_length=50)
    mfg_date: Optional[date] = None
    exp_date: Optional[date] = None
    generate_coa: Optional[bool] = None
    status: Optional[LotStatus] = None


class ProductInLot(BaseModel):
    """Product information within a lot response."""

    id: int
    display_name: str
    brand: str
    percentage: Optional[Decimal] = None
    batch_number: Optional[str] = None

    model_config = {"from_attributes": True}


class ProductSummary(BaseModel):
    """Minimal product info for lot list responses (used in Kanban cards)."""

    id: int
    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    percentage: Optional[Decimal] = None
    batch_number: Optional[str] = None

    model_config = {"from_attributes": True}


class SublotSummary(BaseModel):
    """Minimal sublot info for parent-lot list/card responses."""

    sublot_number: str
    production_date: Optional[date] = None

    model_config = {"from_attributes": True}


class LotResponse(BaseModel):
    """Lot response schema."""

    id: int
    lot_number: str
    lot_type: LotType
    reference_number: str
    mfg_date: Optional[date] = None
    exp_date: Optional[date] = None
    status: LotStatus
    generate_coa: bool
    rejection_reason: Optional[str] = None
    attached_pdfs: Optional[List[str]] = None  # List of uploaded PDF filenames
    has_pending_retest: bool = False  # True when retest is pending
    coc_storage_key: Optional[str] = None  # Archived COC PDF
    return_reason: Optional[str] = None
    return_response_note: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LotWithProductsResponse(LotResponse):
    """Lot response with associated products (full detail)."""

    products: List[ProductInLot] = []


class LotWithProductSummaryResponse(LotResponse):
    """Lot response with minimal product info for list views."""

    products: List[ProductSummary] = []
    sublots: List[SublotSummary] = []  # Parent-lot sublots (empty for other lot types)
    tests_entered: int = 0  # Count of test results with values entered
    tests_total: int = 0  # Total expected tests from product specs
    tests_failed: int = 0  # Count of test results that failed specification


class LotListResponse(BaseModel):
    """Paginated lot list response."""

    items: List[LotWithProductSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SublotBase(BaseModel):
    """Base sublot schema."""

    sublot_number: str = Field(..., min_length=1, max_length=50)
    production_date: Optional[date] = None
    quantity_lbs: Optional[Decimal] = Field(None, gt=0)


class SublotCreate(SublotBase):
    """Schema for creating a sublot."""

    pass


class SublotBulkCreate(BaseModel):
    """Schema for creating multiple sublots at once."""

    sublots: List[SublotCreate] = Field(..., min_length=1)


class SublotResponse(SublotBase):
    """Sublot response schema."""

    id: int
    parent_lot_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LotReturnRequest(BaseModel):
    """Request body for returning an awaiting-release lot for review."""

    reason: str


class LotSubmitRequest(BaseModel):
    """Optional request body for submit-for-review (carries return response)."""

    return_response_note: Optional[str] = None


class LotStatusUpdate(BaseModel):
    """Schema for updating lot status."""

    status: LotStatus
    rejection_reason: Optional[str] = None  # Required when status is 'rejected'
    override_reason: Optional[str] = (
        None  # Required when approving from 'needs_attention'
    )


class LotStatusRecalculationChange(BaseModel):
    """A lot status change found by status recalculation."""

    lot_id: int
    reference_number: str
    lot_number: str
    old_status: LotStatus
    new_status: LotStatus
    reason: str
    missing_tests: List[str] = Field(default_factory=list)
    failing_tests: List[str] = Field(default_factory=list)


class LotStatusRecalculationResponse(BaseModel):
    """Result of a preview or apply lot status recalculation run."""

    mode: str
    scanned_count: int
    changed_count: int
    changes: List[LotStatusRecalculationChange] = Field(default_factory=list)


# Extended schemas for modal with test specifications
class TestSpecInProduct(BaseModel):
    """Test specification details for modal display."""

    id: int
    lab_test_type_id: int
    test_name: str
    test_category: Optional[str] = None
    test_method: Optional[str] = None
    test_unit: Optional[str] = None
    specification: str
    is_required: bool

    model_config = {"from_attributes": True}


class ProductInLotWithSpecs(BaseModel):
    """Product with test specifications for modal display."""

    id: int
    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    display_name: str
    serving_size: Optional[str] = None
    percentage: Optional[Decimal] = None
    batch_number: Optional[str] = None
    test_specifications: List[TestSpecInProduct] = []

    model_config = {"from_attributes": True}


class LotWithProductSpecsResponse(LotResponse):
    """Lot response with full product details and test specifications."""

    products: List[ProductInLotWithSpecs] = []


class ReviewThreadEvent(BaseModel):
    """A single event in the lot's return/resolution conversation thread."""

    type: str  # "return" | "resolution"
    message: str
    author: Optional[str] = None
    author_role: Optional[str] = None
    at: datetime


class ReviewThreadResponse(BaseModel):
    """Full return/resolution conversation thread derived from the audit log."""

    events: List[ReviewThreadEvent]
    return_count: int
