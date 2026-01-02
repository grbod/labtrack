"""Test result model with approval workflow."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    Text,
    Date,
    DateTime,
    Numeric,
    Integer,
    ForeignKey,
    Enum,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from app.models.enums import TestResultStatus


class TestResult(BaseModel):
    """
    Test result model for storing lab test data with approval workflow.

    Attributes:
        lot_id: Reference to the lot being tested
        test_type: Type of test performed (e.g., "microbiological", "heavy_metals")
        result_value: Test result value
        unit: Unit of measurement
        test_date: Date test was performed
        pdf_source: Source PDF filename
        confidence_score: AI parsing confidence (0.00-1.00)
        status: Current approval status
        approved_by_id: User who approved the result
        approved_at: Timestamp of approval
        notes: Additional notes or comments
    """

    __tablename__ = "test_results"

    # Core fields
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    test_type = Column(String(100), nullable=False)
    result_value = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    test_date = Column(Date, nullable=True)
    pdf_source = Column(String(255), nullable=True)
    confidence_score = Column(Numeric(3, 2), nullable=True)
    status = Column(
        Enum(TestResultStatus), nullable=False, default=TestResultStatus.DRAFT
    )
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Additional fields for specific test types
    specification = Column(String(100), nullable=True)  # e.g., "<10 CFU/g"
    method = Column(String(100), nullable=True)  # e.g., "USP <2021>"

    # Relationships
    lot = relationship("Lot", back_populates="test_results")
    approved_by_user = relationship(
        "User", back_populates="approved_results", foreign_keys=[approved_by_id]
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_test_result_lot", "lot_id"),
        Index("idx_test_result_status", "status"),
        Index("idx_test_result_type", "test_type"),
        Index("idx_test_result_lot_type", "lot_id", "test_type"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_valid",
        ),
        CheckConstraint(
            "approved_at IS NULL OR approved_by_id IS NOT NULL",
            name="check_approval_valid",
        ),
    )

    # Common test type categories
    TEST_CATEGORIES = {
        "microbiological": [
            "Total Plate Count",
            "Yeast and Mold",
            "E. coli",
            "Salmonella",
            "Staphylococcus aureus",
            "Pseudomonas aeruginosa",
        ],
        "heavy_metals": ["Lead", "Arsenic", "Cadmium", "Mercury", "Total Heavy Metals"],
        "nutritional": ["Protein", "Fat", "Carbohydrates", "Calories", "Moisture"],
        "physical": ["Appearance", "Odor", "Taste", "Particle Size", "Bulk Density"],
    }

    @validates("test_type")
    def validate_test_type(self, key, value):
        """Validate test type is not empty."""
        if not value or not value.strip():
            raise ValueError("Test type cannot be empty")
        return value.strip()

    @validates("confidence_score")
    def validate_confidence_score(self, key, value):
        """Validate confidence score is between 0 and 1."""
        if value is not None and (value < 0 or value > 1):
            raise ValueError("Confidence score must be between 0 and 1")
        return value

    @validates("status")
    def validate_status_transition(self, key, new_status):
        """Validate status transitions follow workflow rules."""
        if not hasattr(self, "status") or self.status is None:
            return new_status

        current_status = self.status

        # Define valid transitions
        valid_transitions = {
            TestResultStatus.DRAFT: [TestResultStatus.APPROVED],
            TestResultStatus.APPROVED: [
                TestResultStatus.DRAFT
            ],  # Only admin can revert
        }

        if new_status == current_status:
            return new_status

        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )

        return new_status

    @property
    def is_approved(self):
        """Check if result is approved."""
        return self.status == TestResultStatus.APPROVED

    @property
    def is_high_confidence(self):
        """Check if AI parsing had high confidence."""
        return self.confidence_score is not None and self.confidence_score >= 0.7

    @property
    def needs_review(self):
        """Check if result needs manual review."""
        return self.status == TestResultStatus.DRAFT and (
            self.confidence_score is None or self.confidence_score < 0.7
        )

    def get_test_category(self):
        """Get the category of this test type."""
        for category, tests in self.TEST_CATEGORIES.items():
            if any(test.lower() in self.test_type.lower() for test in tests):
                return category
        return "other"

    def approve(self, user):
        """Approve this test result."""
        if not user.can_approve:
            raise ValueError("User does not have approval permissions")

        self.status = TestResultStatus.APPROVED
        self.approved_by_id = user.id
        self.approved_at = datetime.utcnow()

    def reject(self, user, reason=None):
        """Reject this test result and revert to draft."""
        if not user.can_approve:
            raise ValueError("User does not have approval permissions")

        self.status = TestResultStatus.DRAFT
        self.approved_by_id = None
        self.approved_at = None
        if reason:
            self.notes = f"Rejected: {reason}\n{self.notes or ''}"

    def can_transition_to(self, new_status):
        """Check if transition to new status is valid."""
        valid_transitions = {
            TestResultStatus.DRAFT: [TestResultStatus.APPROVED],
            TestResultStatus.APPROVED: [
                TestResultStatus.DRAFT
            ],  # Only admin can revert
        }

        return new_status in valid_transitions.get(self.status, [])

    @property
    def test_category(self):
        """Get test category as property."""
        category = self.get_test_category()
        # Convert underscores to spaces and title case
        return category.replace("_", " ").title()

    def __repr__(self):
        """String representation of TestResult."""
        return (
            f"<TestResult(id={self.id}, lot_id={self.lot_id}, "
            f"test_type='{self.test_type}', status='{self.status.value}')>"
        )
