"""Retest request models for tracking retest workflow."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    Enum,
    Index,
)
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from app.models.enums import RetestStatus


class RetestRequest(BaseModel):
    """
    Retest request model for tracking lab retest requests.

    Attributes:
        lot_id: Reference to the lot being retested
        reference_number: Unique reference for lab communication (e.g., "250129-001-R1")
        retest_number: Sequential retest number (1 for R1, 2 for R2, etc.)
        reason: Why retest was requested
        status: Current retest status (pending, completed)
        requested_by_id: User who requested the retest
        completed_at: Timestamp when retest was completed
    """

    __tablename__ = "retest_requests"

    # Core fields
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    reference_number = Column(String(50), unique=True, nullable=False)
    retest_number = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        Enum(RetestStatus), nullable=False, default=RetestStatus.PENDING
    )
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    daane_po_number = Column(String(20), nullable=True)  # Daane COC PO number

    # Relationships
    lot = relationship("Lot", back_populates="retest_requests")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    items = relationship(
        "RetestItem", back_populates="retest_request", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_retest_request_lot", "lot_id"),
        Index("idx_retest_request_status", "status"),
        Index("idx_retest_request_reference", "reference_number"),
    )

    @validates("reference_number")
    def validate_reference_number(self, key, value):
        """Validate reference number is not empty."""
        if not value or not value.strip():
            raise ValueError("Reference number cannot be empty")
        return value.strip().upper()

    @validates("reason")
    def validate_reason(self, key, value):
        """Validate reason is not empty."""
        if not value or not value.strip():
            raise ValueError("Reason cannot be empty")
        return value.strip()

    @validates("retest_number")
    def validate_retest_number(self, key, value):
        """Validate retest number is positive."""
        if value is None or value < 1:
            raise ValueError("Retest number must be at least 1")
        return value

    @property
    def is_pending(self):
        """Check if retest is still pending."""
        return self.status == RetestStatus.PENDING

    @property
    def is_completed(self):
        """Check if retest is completed."""
        return self.status == RetestStatus.COMPLETED

    def complete(self):
        """Mark retest as completed."""
        self.status = RetestStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def __repr__(self):
        """String representation of RetestRequest."""
        return (
            f"<RetestRequest(id={self.id}, reference='{self.reference_number}', "
            f"status='{self.status.value}')>"
        )


class RetestItem(BaseModel):
    """
    Retest item model for tracking which tests are being retested.

    Attributes:
        retest_request_id: Reference to the parent retest request
        test_result_id: Reference to the test result being retested
        original_value: Snapshot of the test value at time of retest request
    """

    __tablename__ = "retest_items"

    # Core fields
    retest_request_id = Column(
        Integer, ForeignKey("retest_requests.id"), nullable=False
    )
    test_result_id = Column(Integer, ForeignKey("test_results.id"), nullable=False)
    original_value = Column(Text, nullable=True)

    # Relationships
    retest_request = relationship("RetestRequest", back_populates="items")
    test_result = relationship("TestResult")

    # Indexes for performance
    __table_args__ = (
        Index("idx_retest_item_request", "retest_request_id"),
        Index("idx_retest_item_test_result", "test_result_id"),
    )

    def __repr__(self):
        """String representation of RetestItem."""
        return (
            f"<RetestItem(id={self.id}, retest_request_id={self.retest_request_id}, "
            f"test_result_id={self.test_result_id})>"
        )
