"""Release schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import COAReleaseStatus, LotStatus, LotType


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
    # Release status for this member. "forked" members were individualized out
    # of a composite and are not actionable in the queue.
    release_status: str = "awaiting_release"
    forked_to_lot_id: Optional[int] = None
    forked_to_reference: Optional[str] = None

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
    mfg_date: Optional[datetime] = None
    exp_date: Optional[datetime] = None


class SendBackRequest(BaseModel):
    """Request to send release back to QC review."""

    reason: str = Field(
        ..., min_length=1, description="Reason for sending back (required)"
    )


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
    # Fork lineage: set when this member was forked out (status == "forked").
    forked_to_lot_id: Optional[int] = None
    forked_to_reference: Optional[str] = None


# Request for creating/approving release by lot+product
class ApproveByLotProductRequest(BaseModel):
    """Request to approve release by lot_id and product_id."""

    customer_id: Optional[int] = None
    notes: Optional[str] = None
    # Release-gate override: bypass blocking (red) gate items. Requires
    # QC Manager/Admin and a non-empty reason; the reason prints on the COA.
    override: bool = False
    override_reason: Optional[str] = None


class ApproveByLotProductResponse(BaseModel):
    """Response after approving a release by lot_id and product_id."""

    status: str  # "released"
    coa_release_id: int
    lot_status: LotStatus
    all_products_released: bool

    model_config = {"from_attributes": True}


# --- Release gate ---------------------------------------------------------
class GateTestRef(BaseModel):
    """A test row referenced by the gate (failing / indeterminate)."""

    name: str
    result_value: Optional[str] = None
    spec_text: Optional[str] = None


class GateSensoryRow(BaseModel):
    """A sensory/organoleptic panel row requiring attestation."""

    lab_test_type_id: int
    name: str
    spec_text: Optional[str] = None
    attested: bool = False


class ReleaseGateStatus(BaseModel):
    """Green/amber/red gate summary for releasing a (lot, product) COA."""

    lot_id: int
    product_id: int
    is_legacy_import: bool = False
    results_all_approved: bool = True
    # Composite: True when this lot is a multi-SKU composite (member view).
    is_composite: bool = False
    # Red (blocking) items
    missing_tests: List[str] = []
    failing_tests: List[GateTestRef] = []
    # Composite-only: union of ALL (non-forked) member products' required lab
    # panels not yet covered by the lot's shared results. A missing union test
    # blocks EVERY member's release.
    union_missing_tests: List[str] = []
    # Amber (non-blocking) warnings
    indeterminate_tests: List[GateTestRef] = []
    # Sensory attest checklist
    sensory_rows: List[GateSensoryRow] = []
    sensory_all_attested: bool = True
    # Overall
    blocking_reasons: List[str] = []
    can_release: bool = True
    # Re-release notice: populated when a prior release for this pair was voided
    # and had email history.
    prior_email_recipients: List[str] = []
    prior_email_date: Optional[datetime] = None


class SensoryAttestRequest(BaseModel):
    """Request to attest sensory rows for a release."""

    lab_test_type_ids: List[int] = []


class VoidReleaseRequest(BaseModel):
    """Request to void a released COA and return the lot to the queue."""

    reason: str
    # Decision 24: also void these sibling releases (same lot, same shared
    # results). Validated to belong to the same lot and be RELEASED.
    also_void_release_ids: List[int] = []


class ReleaseSibling(BaseModel):
    """A sibling released COA on the same composite lot (for the void prompt)."""

    id: int
    product_id: int
    product_name: Optional[str] = None
    brand: Optional[str] = None
    reference_number: Optional[str] = None


class ForkRequest(BaseModel):
    """Request to fork a product out of a lot into a fresh re-sample lot."""

    product_id: int


class ForkResponse(BaseModel):
    """New lot created by a fork."""

    lot_id: int
    lot_number: str
    reference_number: str
    product_id: int
    status: LotStatus
    forked_from_lot_id: int
    fork_context: Optional[str] = None
    inherited_result_count: int = 0

    model_config = {"from_attributes": True}


# COA Preview Data schemas
class COATestResult(BaseModel):
    """Test result item for COA preview.

    Serialised from a canonical ``coa_context_builder.TestRow``.
    """

    id: Optional[int] = None
    name: str
    method: Optional[str] = None  # TestResult.method, e.g. "USP <2021>"
    result: str
    unit: Optional[str] = None
    specification: Optional[str] = (
        None  # None when no spec exists (render "—"); never fabricated
    )
    status: str  # "Pass", "Fail", or "—"
    verdict: Optional[str] = (
        None  # machine-readable verdict kind (PASS/FAIL/NO_SPEC/INDETERMINATE/…)
    )


class COANotTestedRow(BaseModel):
    """A required panel test with no result — rendered as a "Not Tested" row."""

    name: str
    method: Optional[str] = None
    specification: Optional[str] = None
    status: str = "Not Tested"


class COAPreviewData(BaseModel):
    """COA preview data for frontend rendering."""

    # Company info
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    company_logo_url: Optional[str] = None

    # Product info
    product_name: str
    brand: str

    # Lot info
    lot_number: str
    reference_number: str
    mfg_date: Optional[str] = None  # Formatted date string
    exp_date: Optional[str] = None  # Formatted date string

    # Test results
    tests: List[COATestResult] = []
    not_tested: List[COANotTestedRow] = []

    # Document identity + deviation note (from the release gate override, if any)
    document_id: Optional[str] = None
    deviation_note: Optional[str] = None

    # Notes
    notes: Optional[str] = None

    # Generation info
    generated_date: str
    released_by: Optional[str] = None
    released_by_title: Optional[str] = None
    released_by_email: Optional[str] = None
    signature_url: Optional[str] = None  # URL to signature image for COA
    released_at: Optional[str] = None  # Release date (if different from generated_date)
