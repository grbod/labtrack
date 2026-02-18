"""Daily counter for Daane COC PO numbers."""

from sqlalchemy import Column, Date, Integer, UniqueConstraint, Index
from app.models.base import BaseModel


class DaaneCOCDailyCounter(BaseModel):
    """Track daily sequence for Daane COC PO numbers."""

    __tablename__ = "daane_coc_daily_counters"

    counter_date = Column(Date, nullable=False, unique=True)
    last_sequence = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("counter_date", name="uq_daane_coc_daily_counter_date"),
        Index("idx_daane_coc_daily_counter_date", "counter_date"),
    )

    def __repr__(self):
        return (
            f"<DaaneCOCDailyCounter(date={self.counter_date}, "
            f"last_sequence={self.last_sequence})>"
        )
