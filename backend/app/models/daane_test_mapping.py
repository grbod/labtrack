"""Daane Labs test mapping model."""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class DaaneTestMapping(BaseModel):
    """
    Mapping from internal lab test types to Daane Labs COC method strings.

    Stores the selected Daane method string and how it was matched.
    """

    __tablename__ = "daane_test_mappings"

    lab_test_type_id = Column(Integer, ForeignKey("lab_test_types.id"), nullable=False, unique=True)
    daane_method = Column(String(255), nullable=True)
    match_type = Column(String(50), nullable=False, default="unmapped")
    match_reason = Column(String(255), nullable=True)

    lab_test_type = relationship("LabTestType")

    __table_args__ = (
        UniqueConstraint("lab_test_type_id", name="uq_daane_test_mapping_lab_test_type_id"),
        Index("idx_daane_test_mapping_lab_test_type_id", "lab_test_type_id"),
    )

    def __repr__(self):
        return (
            f"<DaaneTestMapping(id={self.id}, lab_test_type_id={self.lab_test_type_id}, "
            f"match_type='{self.match_type}')>"
        )
