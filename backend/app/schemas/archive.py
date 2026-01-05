"""Archive schemas for request/response validation."""

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.enums import COAReleaseStatus, LotType


# Nested schemas for responses
class ProductInArchive(BaseModel):
    """Product information within an archive response."""

    id: int
    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    display_name: str

    model_config = {"from_attributes": True}


class LotInArchive(BaseModel):
    """Lot information within an archive response."""

    id: int
    lot_number: str
    lot_type: LotType
    reference_number: str
    mfg_date: Optional[date] = None
    exp_date: Optional[date] = None

    model_config = {"from_attributes": True}


class CustomerInArchive(BaseModel):
    """Customer information within an archive response."""

    id: int
    company_name: str
    contact_name: str
    email: str

    model_config = {"from_attributes": True}


class UserInArchive(BaseModel):
    """User information within an archive response."""

    id: int
    username: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


# Filter schema
class ArchiveFilters(BaseModel):
    """Filters for searching archived COAs."""

    product_id: Optional[int] = None
    customer_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    lot_number: Optional[str] = None


# Archive item schemas
class ArchiveItem(BaseModel):
    """Archived COA summary for list view."""

    id: int
    lot_number: Optional[str] = None
    reference_number: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    customer_name: Optional[str] = None
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None
    coa_file_path: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_release(cls, release) -> "ArchiveItem":
        """Create archive item from COARelease model."""
        return cls(
            id=release.id,
            lot_number=release.lot.lot_number if release.lot else None,
            reference_number=release.lot.reference_number if release.lot else None,
            product_name=release.product.product_name if release.product else None,
            brand=release.product.brand if release.product else None,
            customer_name=release.customer.company_name if release.customer else None,
            released_at=release.released_at,
            released_by=release.released_by.username if release.released_by else None,
            coa_file_path=release.coa_file_path,
            notes=release.notes,
        )


class ArchiveDetailResponse(BaseModel):
    """Full archived COA details response."""

    id: int
    lot_id: int
    product_id: int
    customer_id: Optional[int] = None
    notes: Optional[str] = None
    status: COAReleaseStatus
    released_at: Optional[datetime] = None
    released_by_id: Optional[int] = None
    coa_file_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested relations
    lot: Optional[LotInArchive] = None
    product: Optional[ProductInArchive] = None
    customer: Optional[CustomerInArchive] = None
    released_by: Optional[UserInArchive] = None

    model_config = {"from_attributes": True}


# Request schemas
class ResendEmailRequest(BaseModel):
    """Request to re-send email to a different recipient."""

    recipient_email: str = Field(..., description="Email address to re-send to")


# Email history schemas
class EmailHistoryInArchive(BaseModel):
    """Email history record for archive view."""

    id: int
    coa_release_id: int
    recipient_email: str
    sent_at: datetime
    sent_by_id: int
    sent_by: Optional[UserInArchive] = None

    model_config = {"from_attributes": True}


# Paginated response
class ArchiveListResponse(BaseModel):
    """Paginated archive list response."""

    items: List[ArchiveItem]
    total: int
    page: int
    page_size: int
    total_pages: int
