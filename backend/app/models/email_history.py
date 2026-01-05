"""EmailHistory model for tracking COA email deliveries."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class EmailHistory(BaseModel):
    """
    EmailHistory model for tracking emails sent for COAs.

    Attributes:
        coa_release_id: Reference to the COARelease
        recipient_email: Email address the COA was sent to
        sent_at: Timestamp when email was sent
        sent_by_id: User who sent the email
    """

    __tablename__ = "email_history"

    # Core fields
    coa_release_id = Column(Integer, ForeignKey("coa_releases.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    sent_at = Column(DateTime, nullable=False)
    sent_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    coa_release = relationship("COARelease", back_populates="email_history")
    sent_by = relationship("User")

    # Indexes for performance
    __table_args__ = (
        Index("idx_email_history_coa_release", "coa_release_id"),
        Index("idx_email_history_recipient", "recipient_email"),
        Index("idx_email_history_sent_at", "sent_at"),
    )

    def __repr__(self):
        """String representation of EmailHistory."""
        return f"<EmailHistory(id={self.id}, coa_release_id={self.coa_release_id}, recipient='{self.recipient_email}')>"
