"""Lot and Sublot models for production tracking."""

from datetime import date
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    Date,
    Boolean,
    Enum,
    Text,
    Index,
    Integer,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Numeric,
    JSON,
)
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from app.models.enums import LotType, LotStatus, TestResultStatus


class Lot(BaseModel):
    """
    Main lot model including standard lots, parent lots, and multi-SKU composites.

    Attributes:
        lot_number: Unique lot identifier
        lot_type: Type of lot (standard, parent_lot, multi_sku_composite)
        reference_number: Unique reference for lab communication
        mfg_date: Manufacturing date
        exp_date: Expiration date
        status: Current lot status
        generate_coa: Whether to generate COA for this lot
    """

    __tablename__ = "lots"

    # Core fields
    lot_number = Column(String(50), unique=True, nullable=False)
    lot_type = Column(Enum(LotType), nullable=False, default=LotType.STANDARD)
    reference_number = Column(String(50), unique=True, nullable=False)
    mfg_date = Column(Date, nullable=True)
    exp_date = Column(Date, nullable=True)
    status = Column(Enum(LotStatus), nullable=False, default=LotStatus.AWAITING_RESULTS)
    generate_coa = Column(Boolean, default=True, nullable=False)
    rejection_reason = Column(Text, nullable=True)  # Required when status is REJECTED
    attached_pdfs = Column(JSON, nullable=True, default=list)  # List of uploaded PDF filenames
    has_pending_retest = Column(Boolean, default=False, nullable=False)  # True when retest is pending
    daane_po_number = Column(String(20), nullable=True)  # Daane COC PO number

    # Relationships
    sublots = relationship(
        "Sublot", back_populates="parent_lot", cascade="all, delete-orphan"
    )
    lot_products = relationship(
        "LotProduct", back_populates="lot", cascade="all, delete-orphan"
    )
    test_results = relationship(
        "TestResult", back_populates="lot", cascade="all, delete-orphan"
    )
    coa_history = relationship(
        "COAHistory", back_populates="lot", cascade="all, delete-orphan"
    )
    coa_releases = relationship(
        "COARelease", back_populates="lot", cascade="all, delete-orphan"
    )
    retest_requests = relationship(
        "RetestRequest", back_populates="lot", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_lot_number", "lot_number"),
        Index("idx_lot_reference", "reference_number"),
        Index("idx_lot_status", "status"),
        Index("idx_lot_type_status", "lot_type", "status"),
        CheckConstraint("exp_date >= mfg_date", name="check_dates_valid"),
    )

    @validates("lot_number", "reference_number")
    def validate_required_fields(self, key, value):
        """Validate required string fields are not empty."""
        if not value or not value.strip():
            raise ValueError(f"{key} cannot be empty")
        return value.strip().upper()

    @validates("exp_date")
    def validate_exp_date(self, key, exp_date):
        """Validate expiration date is after manufacturing date."""
        if exp_date and self.mfg_date and exp_date < self.mfg_date:
            raise ValueError("Expiration date must be after manufacturing date")
        return exp_date

    @property
    def products(self):
        """Get associated products."""
        return [lp.product for lp in self.lot_products]

    @property
    def is_composite(self):
        """Check if lot is a multi-SKU composite."""
        return self.lot_type == LotType.MULTI_SKU_COMPOSITE

    @property
    def is_parent_lot(self):
        """Check if lot is a parent lot with sublots."""
        return self.lot_type == LotType.PARENT_LOT

    @property
    def can_generate_coa(self):
        """Check if COA can be generated for this lot."""
        return (
            self.generate_coa
            and self.status
            in [LotStatus.AWAITING_RELEASE, LotStatus.APPROVED, LotStatus.RELEASED]
            and all(tr.status == TestResultStatus.APPROVED for tr in self.test_results)
        )

    def update_status(self, new_status, rejection_reason: str = None, override_reason: str = None):
        """Update lot status with validation."""
        # Valid transitions
        valid_transitions = {
            LotStatus.AWAITING_RESULTS: [LotStatus.PARTIAL_RESULTS, LotStatus.NEEDS_ATTENTION, LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
            LotStatus.PARTIAL_RESULTS: [LotStatus.NEEDS_ATTENTION, LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
            LotStatus.NEEDS_ATTENTION: [LotStatus.UNDER_REVIEW, LotStatus.APPROVED, LotStatus.REJECTED],  # APPROVED requires override_reason
            LotStatus.UNDER_REVIEW: [LotStatus.AWAITING_RELEASE, LotStatus.NEEDS_ATTENTION, LotStatus.REJECTED],
            LotStatus.AWAITING_RELEASE: [LotStatus.APPROVED, LotStatus.REJECTED],
            LotStatus.APPROVED: [LotStatus.RELEASED, LotStatus.REJECTED],
            LotStatus.RELEASED: [],  # Terminal state
            LotStatus.REJECTED: [LotStatus.AWAITING_RELEASE, LotStatus.NEEDS_ATTENTION],  # Can resubmit for QC review
        }

        if new_status not in valid_transitions.get(self.status, []):
            raise ValueError(
                f"Invalid status transition from {self.status.value} to {new_status.value}"
            )

        # Rejection reason is required when transitioning to REJECTED
        if new_status == LotStatus.REJECTED:
            if not rejection_reason or not rejection_reason.strip():
                raise ValueError("Rejection reason is required when rejecting a lot")
            self.rejection_reason = rejection_reason.strip()
        elif new_status == LotStatus.AWAITING_RELEASE and self.status == LotStatus.REJECTED:
            # Clear rejection reason when resubmitting
            self.rejection_reason = None

        # Override reason is required when approving from NEEDS_ATTENTION (QC override)
        if self.status == LotStatus.NEEDS_ATTENTION and new_status == LotStatus.APPROVED:
            if not override_reason or not override_reason.strip():
                raise ValueError("Override justification is required when approving a lot with failing tests")
            # Store override reason in rejection_reason field (reused for override notes)
            self.rejection_reason = f"[QC Override] {override_reason.strip()}"

        self.status = new_status

    def __repr__(self):
        """String representation of Lot."""
        return f"<Lot(id={self.id}, lot_number='{self.lot_number}', type='{self.lot_type.value}', status='{self.status.value}')>"


class Sublot(BaseModel):
    """
    Sublot model for production tracking under parent lots.

    Attributes:
        parent_lot_id: Reference to parent lot
        sublot_number: Unique sublot identifier (e.g., "ABC123-1")
        production_date: Date of sublot production
        quantity_lbs: Quantity in pounds
    """

    __tablename__ = "sublots"

    # Core fields
    parent_lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    sublot_number = Column(String(50), unique=True, nullable=False)
    production_date = Column(Date, nullable=True)
    quantity_lbs = Column(Numeric(10, 2), nullable=True)

    # Relationships
    parent_lot = relationship("Lot", back_populates="sublots")

    # Indexes for performance
    __table_args__ = (
        Index("idx_sublot_number", "sublot_number"),
        Index("idx_sublot_parent", "parent_lot_id"),
    )

    @validates("sublot_number")
    def validate_sublot_number(self, key, value):
        """Validate sublot number format."""
        if not value or not value.strip():
            raise ValueError("Sublot number cannot be empty")
        return value.strip().upper()

    @validates("quantity_lbs")
    def validate_quantity(self, key, value):
        """Validate quantity is positive."""
        if value is not None and value <= 0:
            raise ValueError("Quantity must be positive")
        return value

    def __repr__(self):
        """String representation of Sublot."""
        return f"<Sublot(id={self.id}, sublot_number='{self.sublot_number}', quantity={self.quantity_lbs})>"


class LotProduct(BaseModel):
    """
    Association table linking lots to products with optional percentage for composites.

    Attributes:
        lot_id: Reference to lot
        product_id: Reference to product
        percentage: Percentage for multi-SKU composites
    """

    __tablename__ = "lot_products"

    # Remove the id from BaseModel since we use composite primary key
    id = None

    # Core fields
    lot_id = Column(Integer, ForeignKey("lots.id"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    percentage = Column(Numeric(5, 2), nullable=True)

    # Relationships
    lot = relationship("Lot", back_populates="lot_products")
    product = relationship("Product", back_populates="lot_products")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "percentage >= 0 AND percentage <= 100", name="check_percentage_valid"
        ),
        Index("idx_lot_product_lot", "lot_id"),
        Index("idx_lot_product_product", "product_id"),
    )

    @validates("percentage")
    def validate_percentage(self, key, value):
        """Validate percentage is between 0 and 100."""
        if value is not None and (value < 0 or value > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return value

    def __repr__(self):
        """String representation of LotProduct."""
        return f"<LotProduct(lot_id={self.lot_id}, product_id={self.product_id}, percentage={self.percentage})>"
