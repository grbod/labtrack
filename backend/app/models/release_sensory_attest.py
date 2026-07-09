"""ReleaseSensoryAttest model.

Records a QC attestation that a sensory/organoleptic test row passed for a
specific COA release. The release gate requires every sensory row of the
product's panel to be attested on that release before it can move to RELEASED
(legacy-import lots are exempt). Attested rows print "Pass" on the COA.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ReleaseSensoryAttest(BaseModel):
    """One QC sign-off of a sensory test row for a given release."""

    __tablename__ = "release_sensory_attests"

    release_id = Column(Integer, ForeignKey("coa_releases.id"), nullable=False)
    lab_test_type_id = Column(Integer, ForeignKey("lab_test_types.id"), nullable=False)
    attested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    attested_at = Column(DateTime, nullable=True)

    release = relationship("COARelease", back_populates="sensory_attests")
    lab_test_type = relationship("LabTestType")
    attested_by = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "lab_test_type_id",
            name="uq_release_sensory_attest",
        ),
    )

    def __repr__(self):  # pragma: no cover - trivial
        return (
            f"<ReleaseSensoryAttest(release_id={self.release_id}, "
            f"lab_test_type_id={self.lab_test_type_id})>"
        )
