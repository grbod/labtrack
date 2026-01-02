"""Lot schemas for request/response validation."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from app.models.enums import LotType, LotStatus


class ProductReference(BaseModel):
    """Reference to a product in a lot."""

    product_id: int
    percentage: Optional[Decimal] = None


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
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LotWithProductsResponse(LotResponse):
    """Lot response with associated products."""

    products: List[ProductInLot] = []


class LotListResponse(BaseModel):
    """Paginated lot list response."""

    items: List[LotResponse]
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


class SublotResponse(SublotBase):
    """Sublot response schema."""

    id: int
    parent_lot_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LotStatusUpdate(BaseModel):
    """Schema for updating lot status."""

    status: LotStatus
