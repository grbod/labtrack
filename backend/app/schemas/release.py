"""Release schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import COAReleaseStatus, LotType, LotStatus


# Release Queue Item schema (Lot+Product pairs, NOT COARelease)
class ReleaseQueueItem(BaseModel):
    """Release queue item based on Lot+Product pair."""

    lot_id: int
    product_id: int
    reference_number: str
    lot_number: str
    product_name: str
    brand: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReleaseQueueResponse(BaseModel):
    """Release queue response with Lot+Product items."""

    items: List[ReleaseQueueItem]
    total: int


# Nested schemas for responses
class ProductInRelease(BaseModel):
    """Product information within a release response."""

    id: int
    brand: str
    product_name: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    display_name: str

    model_config = {"from_attributes": True}


class LotInRelease(BaseModel):
    """Lot information within a release response."""

    id: int
    lot_number: str
    lot_type: LotType
    reference_number: str
    mfg_date: Optional[datetime] = None
    exp_date: Optional[datetime] = None
    status: LotStatus

    model_config = {"from_attributes": True}


class CustomerInRelease(BaseModel):
    """Customer information within a release response."""

    id: int
    company_name: str
    contact_name: str
    email: str

    model_config = {"from_attributes": True}


class UserInRelease(BaseModel):
    """User information within a release response."""

    id: int
    username: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


# Main response schemas
class COAReleaseQueueItem(BaseModel):
    """Simplified COARelease for queue list view."""

    id: int
    reference_number: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    status: COAReleaseStatus
    created_at: datetime
    notes: Optional[str] = None
    send_back_reason: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_release(cls, release) -> "COAReleaseQueueItem":
        """Create queue item from COARelease model."""
        return cls(
            id=release.id,
            reference_number=release.lot.reference_number if release.lot else None,
            product_name=release.product.product_name if release.product else None,
            brand=release.product.brand if release.product else None,
            status=release.status,
            created_at=release.created_at,
            notes=release.notes,
            send_back_reason=release.send_back_reason,
        )


class COAReleaseResponse(BaseModel):
    """Full COARelease details response."""

    id: int
    lot_id: int
    product_id: int
    customer_id: Optional[int] = None
    notes: Optional[str] = None
    status: COAReleaseStatus
    released_at: Optional[datetime] = None
    released_by_id: Optional[int] = None
    coa_file_path: Optional[str] = None
    draft_data: Optional[dict] = None
    send_back_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested relations
    lot: Optional[LotInRelease] = None
    product: Optional[ProductInRelease] = None
    customer: Optional[CustomerInRelease] = None
    released_by: Optional[UserInRelease] = None

    model_config = {"from_attributes": True}


class COAReleaseWithSourcePdfs(COAReleaseResponse):
    """COARelease response with source PDFs list."""

    source_pdfs: List[str] = []


# Request schemas
class DraftSaveRequest(BaseModel):
    """Request to save draft data (auto-saved on blur)."""

    customer_id: Optional[int] = None
    notes: Optional[str] = None


class SendBackRequest(BaseModel):
    """Request to send release back to QC review."""

    reason: str = Field(..., min_length=1, description="Reason for sending back (required)")


class EmailSendRequest(BaseModel):
    """Request to log email sent."""

    recipient_email: str = Field(..., description="Email address the COA was sent to")


# Email history schemas
class EmailHistoryResponse(BaseModel):
    """Email history record response."""

    id: int
    coa_release_id: int
    recipient_email: str
    sent_at: datetime
    sent_by_id: int
    sent_by: Optional[UserInRelease] = None

    model_config = {"from_attributes": True}


class ApproveReleaseResponse(BaseModel):
    """Response after approving a release."""

    id: int
    status: COAReleaseStatus
    released_at: Optional[datetime] = None
    released_by_id: Optional[int] = None
    lot_id: int
    product_id: int

    model_config = {"from_attributes": True}


# Release details by lot+product
class ReleaseDetailsByLotProduct(BaseModel):
    """Response for getting release details by lot_id and product_id."""

    # Top-level IDs (required by frontend)
    lot_id: int
    product_id: int

    # Status (awaiting_release if no COARelease, else from COARelease)
    status: str = "awaiting_release"

    # Draft/release fields
    customer_id: Optional[int] = None
    notes: Optional[str] = None
    released_at: Optional[datetime] = None
    draft_data: Optional[dict] = None

    # Nested objects
    lot: LotInRelease
    product: ProductInRelease
    source_pdfs: List[str] = []
    customer: Optional[CustomerInRelease] = None


# Request for creating/approving release by lot+product
class ApproveByLotProductRequest(BaseModel):
    """Request to approve release by lot_id and product_id."""

    customer_id: Optional[int] = None
    notes: Optional[str] = None


class ApproveByLotProductResponse(BaseModel):
    """Response after approving a release by lot_id and product_id."""

    status: str  # "released"
    coa_release_id: int
    lot_status: LotStatus
    all_products_released: bool

    model_config = {"from_attributes": True}
