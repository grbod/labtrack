"""Lab Test Type model for managing test catalog."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Index,
    CheckConstraint,
    DateTime,
    Integer,
    ForeignKey,
    event
)
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from typing import Optional


class LabTestType(BaseModel):
    """
    Catalog of lab test types that can be performed.
    
    This model represents the master list of all possible tests that
    can be performed on products. Each test type can be linked to
    specific products with their own specifications and requirements.
    
    Attributes:
        test_name: Unique name of the test (e.g., "Total Plate Count", "Lead")
        test_category: Category grouping (e.g., "Microbiological", "Heavy Metals")
        default_unit: Default unit of measurement (e.g., "CFU/g", "ppm", "mg/100g")
        description: Detailed description of what the test measures
        test_method: Standard test method reference (e.g., "USP <2021>", "AOAC 999.11")
        is_active: Whether this test type is currently available for use
    """
    
    __tablename__ = "lab_test_types"
    
    # Core fields
    test_name = Column(String(100), unique=True, nullable=False)
    test_category = Column(String(50), nullable=False)
    default_unit = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    test_method = Column(String(100), nullable=True)
    abbreviations = Column(Text, nullable=True)  # JSON array of alternative names
    default_specification = Column(String(100), nullable=True)  # Default spec like "< 10,000 CFU/g"
    is_active = Column(Boolean, default=True, nullable=False)

    # Archive metadata fields
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    archive_reason = Column(String(500), nullable=True)

    # Relationships
    product_specifications = relationship(
        "ProductTestSpecification",
        back_populates="lab_test_type",
        cascade="all, delete-orphan"
    )
    archived_by = relationship("User", foreign_keys=[archived_by_id])

    # Indexes for performance
    __table_args__ = (
        Index("idx_test_name", "test_name"),
        Index("idx_test_category", "test_category"),
        Index("idx_test_active", "is_active"),
        CheckConstraint(
            "test_name != ''",
            name="check_test_name_not_empty"
        ),
        CheckConstraint(
            "test_category != ''",
            name="check_test_category_not_empty"
        ),
    )
    
    # Common test categories as class constants
    CATEGORY_MICROBIOLOGICAL = "Microbiological"
    CATEGORY_HEAVY_METALS = "Heavy Metals"
    CATEGORY_PESTICIDES = "Pesticides"
    CATEGORY_NUTRITIONAL = "Nutritional"
    CATEGORY_PHYSICAL = "Physical"
    CATEGORY_CHEMICAL = "Chemical"
    CATEGORY_ALLERGENS = "Allergens"
    CATEGORY_ORGANOLEPTIC = "Organoleptic"
    
    @validates("test_name")
    def validate_test_name(self, key, value):
        """Validate test name is not empty and properly formatted."""
        if not value or not value.strip():
            raise ValueError("Test name cannot be empty")
        # Just strip whitespace, don't change case
        return value.strip()
    
    @validates("test_category")
    def validate_test_category(self, key, value):
        """Validate test category is not empty."""
        if not value or not value.strip():
            raise ValueError("Test category cannot be empty")
        # Just strip whitespace, don't change case
        return value.strip()
    
    @validates("default_unit")
    def validate_default_unit(self, key, value):
        """Clean and validate unit."""
        if value:
            return value.strip()
        return value
    
    @validates("default_specification")
    def validate_default_specification(self, key, value):
        """Clean and validate default specification."""
        if value is not None:
            value = value.strip()
            if not value:
                return None
            return value
        return None
    
    @property
    def display_name(self) -> str:
        """Get display name with category."""
        return f"{self.test_name} ({self.test_category})"
    
    @property
    def is_microbiological(self) -> bool:
        """Check if this is a microbiological test."""
        return self.test_category == self.CATEGORY_MICROBIOLOGICAL
    
    @property
    def is_heavy_metal(self) -> bool:
        """Check if this is a heavy metals test."""
        return self.test_category == self.CATEGORY_HEAVY_METALS
    
    def get_products_using_test(self):
        """Get all products that use this test type."""
        return [spec.product for spec in self.product_specifications if spec.product]

    def archive(self, user_id: int, reason: str):
        """
        Archive this lab test type (soft delete).

        Args:
            user_id: ID of the user performing the archive
            reason: Reason for archiving (required)
        """
        self.is_active = False
        self.archived_at = datetime.utcnow()
        self.archived_by_id = user_id
        self.archive_reason = reason

    def restore(self):
        """Restore an archived lab test type back to active status."""
        self.is_active = True
        self.archived_at = None
        self.archived_by_id = None
        self.archive_reason = None

    @property
    def is_archived(self) -> bool:
        """Check if this lab test type is archived."""
        return not self.is_active

    def __repr__(self):
        """String representation of LabTestType."""
        return (
            f"<LabTestType(id={self.id}, "
            f"test_name='{self.test_name}', "
            f"category='{self.test_category}', "
            f"active={self.is_active})>"
        )


# Event listener to prevent deletion of test types in use
@event.listens_for(LabTestType, "before_delete")
def prevent_delete_if_in_use(mapper, connection, target):
    """Prevent deletion of test types that are in use."""
    if target.product_specifications:
        raise ValueError(
            f"Cannot delete test type '{target.test_name}' - "
            f"it is used by {len(target.product_specifications)} products"
        )