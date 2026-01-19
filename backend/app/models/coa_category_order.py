"""COA Category Order model for configuring test category display order in COAs."""

from sqlalchemy import Column, JSON
from app.models.base import BaseModel
from app.models.lab_test_type import LabTestType


class COACategoryOrder(BaseModel):
    """
    Stores the global ordering of test categories for COA generation.

    This is a single-row table that contains a JSON array of category names
    in the desired display order. Categories not in the list will appear
    at the end, sorted alphabetically.

    Attributes:
        category_order: JSON array of category names in display order
                       e.g., ["Microbiological", "Heavy Metals", "Pesticides", ...]
    """

    __tablename__ = "coa_category_orders"

    # JSON array of category names in order
    category_order = Column(JSON, nullable=False, default=list)

    @classmethod
    def get_default_order(cls) -> list[str]:
        """Get the default category order (alphabetical)."""
        return sorted([
            LabTestType.CATEGORY_MICROBIOLOGICAL,
            LabTestType.CATEGORY_HEAVY_METALS,
            LabTestType.CATEGORY_PESTICIDES,
            LabTestType.CATEGORY_NUTRITIONAL,
            LabTestType.CATEGORY_PHYSICAL,
            LabTestType.CATEGORY_CHEMICAL,
            LabTestType.CATEGORY_ALLERGENS,
            LabTestType.CATEGORY_ORGANOLEPTIC,
        ])

    def __repr__(self):
        """String representation of COACategoryOrder."""
        return (
            f"<COACategoryOrder(id={self.id}, "
            f"categories={len(self.category_order) if self.category_order else 0})>"
        )
