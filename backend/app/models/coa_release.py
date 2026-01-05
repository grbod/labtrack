"""COARelease model for tracking COA release workflow."""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum, Index, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.enums import COAReleaseStatus


class COARelease(BaseModel):
    """
    COARelease model for tracking individual COA release workflow.

    For MultiSKU lots, one COARelease is created per product.
    For Standard/Parent lots, one COARelease is created.

    Attributes:
        lot_id: Reference to the parent lot
        product_id: Reference to the specific product (for MultiSKU, each product has own COARelease)
        customer_id: Optional customer for COA delivery
        notes: Optional notes that appear in COA footer
        status: Release workflow status
        released_at: Timestamp when released
        released_by_id: User who approved the release
        coa_file_path: Path to generated COA PDF
        draft_data: Auto-saved draft data (customer_id, notes)
        send_back_reason: Reason if sent back to Sample Tracker
    """

    __tablename__ = "coa_releases"

    # Core fields
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(
        Enum(COAReleaseStatus),
        nullable=False,
        default=COAReleaseStatus.AWAITING_RELEASE
    )
    released_at = Column(DateTime, nullable=True)
    released_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    coa_file_path = Column(String(500), nullable=True)
    draft_data = Column(JSON, nullable=True)  # {customer_id, notes} auto-saved
    send_back_reason = Column(Text, nullable=True)

    # Relationships
    lot = relationship("Lot", back_populates="coa_releases")
    product = relationship("Product")
    customer = relationship("Customer", back_populates="coa_releases")
    released_by = relationship("User")
    email_history = relationship(
        "EmailHistory", back_populates="coa_release", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_coa_release_lot", "lot_id"),
        Index("idx_coa_release_product", "product_id"),
        Index("idx_coa_release_customer", "customer_id"),
        Index("idx_coa_release_status", "status"),
        Index("idx_coa_release_lot_status", "lot_id", "status"),
    )

    @property
    def is_released(self):
        """Check if COA has been released."""
        return self.status == COAReleaseStatus.RELEASED

    @property
    def is_awaiting_release(self):
        """Check if COA is awaiting release."""
        return self.status == COAReleaseStatus.AWAITING_RELEASE

    @property
    def reference_number(self):
        """Get the reference number from the parent lot."""
        return self.lot.reference_number if self.lot else None

    def release(self, user_id: int):
        """Mark COA as released."""
        from datetime import datetime
        self.status = COAReleaseStatus.RELEASED
        self.released_at = datetime.utcnow()
        self.released_by_id = user_id

    def save_draft(self, customer_id: int = None, notes: str = None):
        """Save draft data for auto-restore."""
        self.draft_data = {
            "customer_id": customer_id,
            "notes": notes
        }

    def restore_draft(self):
        """Restore draft data."""
        if self.draft_data:
            if self.draft_data.get("customer_id"):
                self.customer_id = self.draft_data["customer_id"]
            if self.draft_data.get("notes"):
                self.notes = self.draft_data["notes"]

    def __repr__(self):
        """String representation of COARelease."""
        return f"<COARelease(id={self.id}, lot_id={self.lot_id}, product_id={self.product_id}, status='{self.status.value}')>"
