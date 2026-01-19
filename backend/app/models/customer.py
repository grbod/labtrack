"""Customer model for COA delivery tracking."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Index, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel


class Customer(BaseModel):
    """
    Customer model for tracking COA recipients.

    Attributes:
        company_name: Customer company name
        contact_name: QC contact person name
        email: Primary email for COA delivery
        is_active: Whether customer is active (soft delete)
    """

    __tablename__ = "customers"

    # Core fields
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Archive metadata fields
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    archive_reason = Column(String(500), nullable=True)

    # Relationships
    coa_releases = relationship(
        "COARelease", back_populates="customer", cascade="all, delete-orphan"
    )
    archived_by = relationship("User", foreign_keys=[archived_by_id])

    # Indexes for performance
    __table_args__ = (
        Index("idx_customer_company", "company_name"),
        Index("idx_customer_email", "email"),
        Index("idx_customer_active", "is_active"),
    )

    @validates("company_name", "contact_name")
    def validate_required_fields(self, key, value):
        """Validate required string fields are not empty."""
        if not value or not value.strip():
            raise ValueError(f"{key} cannot be empty")
        return value.strip()

    @validates("email")
    def validate_email(self, key, value):
        """Validate email format."""
        if not value or not value.strip():
            raise ValueError("Email cannot be empty")
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[1]:
            raise ValueError("Invalid email format")
        return value

    def deactivate(self):
        """Deactivate customer (soft delete). Deprecated - use archive() instead."""
        self.is_active = False

    def activate(self):
        """Reactivate customer. Deprecated - use restore() instead."""
        self.is_active = True

    def archive(self, user_id: int, reason: str):
        """
        Archive this customer (soft delete).

        Args:
            user_id: ID of the user performing the archive
            reason: Reason for archiving (required)
        """
        self.is_active = False
        self.archived_at = datetime.utcnow()
        self.archived_by_id = user_id
        self.archive_reason = reason

    def restore(self):
        """Restore an archived customer back to active status."""
        self.is_active = True
        self.archived_at = None
        self.archived_by_id = None
        self.archive_reason = None

    @property
    def is_archived(self) -> bool:
        """Check if this customer is archived."""
        return not self.is_active

    def __repr__(self):
        """String representation of Customer."""
        return f"<Customer(id={self.id}, company='{self.company_name}', email='{self.email}', active={self.is_active})>"
