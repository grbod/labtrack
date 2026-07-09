"""Immutable COA snapshot models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class COASnapshot(Base):
    """Frozen render context and generated PDF for a released COA."""

    __tablename__ = "coa_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coa_release_id = Column(
        Integer,
        ForeignKey("coa_releases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    coa_serial = Column(String(32), unique=True, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        Integer,
        ForeignKey("coa_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    context_json = Column(Text, nullable=False)
    context_schema_version = Column(Integer, nullable=False)
    pdf_storage_key = Column(String(500), nullable=False)
    signature_storage_key = Column(String(500), nullable=True)
    content_hash = Column(String(64), nullable=False)
    reconstructed = Column(Boolean, nullable=False, default=False)
    voided = Column(Boolean, nullable=False, default=False)
    void_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    coa_release = relationship("COARelease")
    supersedes = relationship("COASnapshot", remote_side=[id])

    __table_args__ = (
        Index("idx_coa_snapshot_release_voided", "coa_release_id", "voided"),
        Index("idx_coa_snapshot_created_at", "created_at"),
    )


class COASerialCounter(Base):
    """Per-year serial issuance counter for immutable COA snapshots."""

    __tablename__ = "coa_serial_counters"

    year = Column(Integer, primary_key=True)
    last_value = Column(Integer, nullable=False, default=0)
