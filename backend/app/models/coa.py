"""COA history model for tracking generated certificates."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel


class COAHistory(BaseModel):
    """
    COA history model for tracking all generated Certificates of Analysis.

    Attributes:
        lot_id: Reference to the lot
        filename: Generated COA filename
        file_path: Full path to the generated file
        generated_at: When the COA was generated
        generated_by: Username who generated it
        template_version: Version of the template used
        format: Output format (PDF, DOCX, etc.)
        notes: Any additional notes
    """

    __tablename__ = "coa_history"

    # Override to use custom timestamp field
    created_at = None  # We use generated_at instead
    updated_at = None  # COA history should never be updated

    # Core fields
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    generated_by = Column(String(50), nullable=True)
    template_version = Column(String(20), nullable=True, default="1.0")
    format = Column(String(10), nullable=False, default="PDF")
    notes = Column(Text, nullable=True)

    # Additional metadata
    file_size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA-256 hash

    # Relationships
    lot = relationship("Lot", back_populates="coa_history")

    # Indexes for performance
    __table_args__ = (
        Index("idx_coa_lot", "lot_id"),
        Index("idx_coa_filename", "filename"),
        Index("idx_coa_generated_at", "generated_at"),
        Index("idx_coa_generated_by", "generated_by"),
        Index("idx_coa_lot_generated", "lot_id", "generated_at"),
    )

    # Supported output formats
    SUPPORTED_FORMATS = ["PDF", "DOCX", "HTML"]

    @validates("filename")
    def validate_filename(self, key, value):
        """Validate filename is not empty."""
        if not value or not value.strip():
            raise ValueError("Filename cannot be empty")
        return value.strip()

    @validates("format")
    def validate_format(self, key, value):
        """Validate output format."""
        if not value:
            return "PDF"
        value = value.upper()
        if value not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Format must be one of: {', '.join(self.SUPPORTED_FORMATS)}"
            )
        return value

    @validates("file_size_bytes")
    def validate_file_size(self, key, value):
        """Validate file size is positive."""
        if value is not None and value <= 0:
            raise ValueError("File size must be positive")
        return value

    @property
    def is_pdf(self):
        """Check if COA is PDF format."""
        return self.format == "PDF"

    @property
    def is_docx(self):
        """Check if COA is DOCX format."""
        return self.format == "DOCX"

    def get_file_size_mb(self):
        """Get file size in megabytes."""
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return None

    def calculate_checksum(self):
        """Calculate SHA-256 checksum of the file."""
        import hashlib
        import os

        if not self.file_path or not os.path.exists(self.file_path):
            return None

        sha256_hash = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        self.checksum = sha256_hash.hexdigest()
        return self.checksum

    def update_file_metadata(self):
        """Update file size and checksum from actual file."""
        import os

        if not self.file_path or not os.path.exists(self.file_path):
            return

        self.file_size_bytes = os.path.getsize(self.file_path)
        self.calculate_checksum()

    @classmethod
    def create_for_lot(
        cls,
        session,
        lot,
        filename,
        generated_by=None,
        format="PDF",
        template_version="1.0",
        notes=None,
    ):
        """
        Create a COA history entry for a lot.

        Args:
            session: Database session
            lot: Lot object
            filename: Generated filename
            generated_by: Username who generated it
            format: Output format
            template_version: Template version used
            notes: Additional notes
        """
        coa = cls(
            lot_id=lot.id,
            filename=filename,
            generated_by=generated_by,
            format=format,
            template_version=template_version,
            notes=notes,
        )

        session.add(coa)
        return coa

    def __repr__(self):
        """String representation of COAHistory."""
        return (
            f"<COAHistory(id={self.id}, lot_id={self.lot_id}, "
            f"filename='{self.filename}', format='{self.format}', "
            f"generated_at='{self.generated_at}')>"
        )
