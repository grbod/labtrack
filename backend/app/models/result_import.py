"""Models for the PDF results importer workflow."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.enums import ResultImportStatus


class ResultImport(BaseModel):
    """One uploaded lab-result PDF and its extraction/review state."""

    __tablename__ = "result_imports"

    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=True)
    file_hash = Column(String(64), nullable=False, index=True)
    status = Column(
        Enum(ResultImportStatus),
        nullable=False,
        default=ResultImportStatus.PROCESSING,
        index=True,
    )
    extracted_data = Column(JSON, nullable=True)
    match_candidates = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    selected_lot_id = Column(Integer, ForeignKey("lots.id"), nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    reverted_at = Column(DateTime, nullable=True)
    openrouter_model = Column(String(120), nullable=True)
    usage_metadata = Column(JSON, nullable=True)
    duplicate_of_id = Column(Integer, ForeignKey("result_imports.id"), nullable=True)

    selected_lot = relationship("Lot", foreign_keys=[selected_lot_id])
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
    duplicate_of = relationship("ResultImport", remote_side="ResultImport.id")
    ledgers = relationship(
        "ResultImportLedger",
        back_populates="result_import",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_result_import_hash_status", "file_hash", "status"),
        Index("idx_result_import_created", "created_at"),
    )


class ResultImportLedger(BaseModel):
    """Audit ledger for safely reverting an applied import."""

    __tablename__ = "result_import_ledgers"

    result_import_id = Column(
        Integer,
        ForeignKey("result_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    created_result_ids = Column(JSON, nullable=True)
    updated_results = Column(JSON, nullable=True)
    pdf_attachment = Column(JSON, nullable=True)
    applied_rows = Column(JSON, nullable=True)
    applied_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    result_import = relationship("ResultImport", back_populates="ledgers")
    lot = relationship("Lot")
    applied_by = relationship("User")
