"""Parsing queue model for handling PDF processing."""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Enum, Index, Numeric, Integer
from sqlalchemy.orm import validates
from app.models.base import BaseModel
from app.models.enums import ParsingStatus


class ParsingQueue(BaseModel):
    """
    Parsing queue model for tracking PDF processing and manual review.

    Attributes:
        pdf_filename: Name of the PDF file
        pdf_path: Full path to the PDF file
        reference_number: Extracted or expected reference number
        error_message: Error details if parsing failed
        status: Current processing status
        assigned_to: Username of person assigned to resolve
        notes: Additional notes or manual corrections
        resolved_at: When the item was resolved
        retry_count: Number of parsing attempts
        extracted_data: JSON string of successfully extracted data
        confidence_scores: JSON string of confidence scores for each field
    """

    __tablename__ = "parsing_queue"

    # Core fields
    pdf_filename = Column(String(255), nullable=False)
    pdf_path = Column(Text, nullable=True)
    reference_number = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(Enum(ParsingStatus), nullable=False, default=ParsingStatus.PENDING)
    assigned_to = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    extracted_data = Column(Text, nullable=True)  # JSON format
    confidence_scores = Column(Text, nullable=True)  # JSON format
    confidence_score = Column(Numeric(3, 2), nullable=True)  # Overall confidence 0.0-1.0

    # Indexes for performance
    __table_args__ = (
        Index("idx_parsing_status", "status"),
        Index("idx_parsing_filename", "pdf_filename"),
        Index("idx_parsing_reference", "reference_number"),
        Index("idx_parsing_assigned", "assigned_to"),
        Index("idx_parsing_status_assigned", "status", "assigned_to"),
    )

    # Maximum retry attempts before marking as failed
    MAX_RETRY_COUNT = 3

    @validates("pdf_filename")
    def validate_pdf_filename(self, key, value):
        """Validate PDF filename."""
        if not value or not value.strip():
            raise ValueError("PDF filename cannot be empty")
        value = value.strip()
        if not value.lower().endswith(".pdf"):
            raise ValueError("File must be a PDF")
        return value

    @validates("status")
    def validate_status_transition(self, key, new_status):
        """Validate status transitions."""
        if not hasattr(self, "status") or self.status is None:
            return new_status

        current_status = self.status

        # Define valid transitions
        valid_transitions = {
            ParsingStatus.PENDING: [ParsingStatus.PROCESSING, ParsingStatus.FAILED],
            ParsingStatus.PROCESSING: [
                ParsingStatus.RESOLVED,
                ParsingStatus.FAILED,
                ParsingStatus.PENDING,
            ],
            ParsingStatus.FAILED: [ParsingStatus.PENDING, ParsingStatus.RESOLVED],
            ParsingStatus.RESOLVED: [],  # Terminal state
        }

        if new_status == current_status:
            return new_status

        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )

        # Update resolved_at when moving to resolved status
        if new_status == ParsingStatus.RESOLVED:
            self.resolved_at = datetime.utcnow()

        return new_status

    @validates("retry_count")
    def validate_retry_count(self, key, value):
        """Validate retry count."""
        if value < 0:
            raise ValueError("Retry count cannot be negative")
        return value

    @property
    def is_resolved(self):
        """Check if parsing is resolved."""
        return self.status == ParsingStatus.RESOLVED

    @property
    def is_failed(self):
        """Check if parsing has failed."""
        return self.status == ParsingStatus.FAILED

    @property
    def can_retry(self):
        """Check if parsing can be retried."""
        return (
            self.status in [ParsingStatus.PENDING, ParsingStatus.FAILED]
            and self.retry_count < self.MAX_RETRY_COUNT
        )

    @property
    def needs_manual_review(self):
        """Check if manual review is needed."""
        return self.status == ParsingStatus.FAILED or (
            self.status == ParsingStatus.PENDING
            and self.retry_count >= self.MAX_RETRY_COUNT
        )

    def mark_processing(self):
        """Mark item as being processed."""
        self.status = ParsingStatus.PROCESSING
        self.retry_count += 1

    def mark_failed(self, error_message):
        """Mark item as failed with error message."""
        self.status = ParsingStatus.FAILED
        self.error_message = error_message

        # Auto-fail if max retries reached
        if self.retry_count >= self.MAX_RETRY_COUNT:
            self.error_message = f"Max retries ({self.MAX_RETRY_COUNT}) exceeded. Last error: {error_message}"

    def mark_resolved(self, notes=None, resolved_by=None):
        """Mark item as resolved."""
        self.status = ParsingStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        if notes:
            self.notes = notes
        if resolved_by:
            self.assigned_to = resolved_by

    def assign_to(self, username):
        """Assign item to a user for manual review."""
        self.assigned_to = username

    def get_extracted_data_dict(self):
        """Get extracted data as dictionary."""
        import json

        if not self.extracted_data:
            return {}
        try:
            return json.loads(self.extracted_data)
        except json.JSONDecodeError:
            return {}

    def set_extracted_data(self, data_dict):
        """Set extracted data from dictionary."""
        import json

        if data_dict:
            self.extracted_data = json.dumps(data_dict, default=str)
        else:
            self.extracted_data = None

    def get_confidence_scores_dict(self):
        """Get confidence scores as dictionary."""
        import json

        if not self.confidence_scores:
            return {}
        try:
            return json.loads(self.confidence_scores)
        except json.JSONDecodeError:
            return {}

    def set_confidence_scores(self, scores_dict):
        """Set confidence scores from dictionary."""
        import json

        if scores_dict:
            self.confidence_scores = json.dumps(scores_dict)
        else:
            self.confidence_scores = None

    def __repr__(self):
        """String representation of ParsingQueue."""
        return (
            f"<ParsingQueue(id={self.id}, pdf='{self.pdf_filename}', "
            f"status='{self.status.value}', retries={self.retry_count})>"
        )
