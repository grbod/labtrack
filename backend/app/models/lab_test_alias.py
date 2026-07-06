"""Alias suggestions and approved mappings for imported lab test names."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class LabTestAlias(BaseModel):
    """Operator-reviewed mapping from raw lab wording to a lab test type."""

    __tablename__ = "lab_test_aliases"

    raw_phrase = Column(String(255), nullable=False)
    normalized_key = Column(String(255), nullable=False)
    lab_name = Column(String(255), nullable=True)
    lab_test_type_id = Column(Integer, ForeignKey("lab_test_types.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    source = Column(String(30), nullable=False, default="fuzzy")
    suggestion_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_result_import_id = Column(
        Integer, ForeignKey("result_imports.id"), nullable=True
    )
    last_lot_id = Column(Integer, ForeignKey("lots.id"), nullable=True)
    last_filename = Column(String(255), nullable=True)
    last_suggested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    disabled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    disabled_at = Column(DateTime, nullable=True)
    disable_reason = Column(Text, nullable=True)

    lab_test_type = relationship("LabTestType")
    last_result_import = relationship(
        "ResultImport", foreign_keys=[last_result_import_id]
    )
    last_lot = relationship("Lot", foreign_keys=[last_lot_id])
    last_suggested_by = relationship("User", foreign_keys=[last_suggested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    disabled_by = relationship("User", foreign_keys=[disabled_by_id])

    __table_args__ = (
        Index(
            "idx_lab_test_alias_key_lab_status", "normalized_key", "lab_name", "status"
        ),
        Index("idx_lab_test_alias_type", "lab_test_type_id"),
        Index("idx_lab_test_alias_status_updated", "status", "updated_at"),
    )
