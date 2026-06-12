"""Product test specification model linking products to required/optional tests."""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel


class ProductTestSpecification(BaseModel):
    """
    Links products to lab test types with specifications.

    This model defines the testing requirements for each product,
    including the acceptance criteria and whether tests are required
    or optional.

    Example:
    - Product: "Organic Whey Protein"
    - Test: "E. coli"
    - Specification: "< 10"
    - Required: True

    Attributes:
        product_id: Reference to the product
        lab_test_type_id: Reference to the lab test type
        specification: Acceptance criteria (e.g., "< 10", "Negative")
        is_required: Whether this test is mandatory for lot approval
        notes: Additional notes or conditions for this test
        min_value: For range specifications (optional)
        max_value: For range specifications (optional)
    """

    __tablename__ = "product_test_specifications"

    # Foreign keys
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    lab_test_type_id = Column(Integer, ForeignKey("lab_test_types.id"), nullable=False)

    # Specification details
    specification = Column(String(100), nullable=False)  # "< 10", "Negative", etc.
    is_required = Column(Boolean, default=True, nullable=False)

    # Additional fields
    notes = Column(Text, nullable=True)  # "Test only on first batch of year"
    min_value = Column(String(20), nullable=True)  # For range specs
    max_value = Column(String(20), nullable=True)  # For range specs

    # Relationships
    product = relationship("Product", back_populates="test_specifications")
    lab_test_type = relationship("LabTestType", back_populates="product_specifications")

    # Unique constraint - one spec per product/test combination
    __table_args__ = (
        UniqueConstraint("product_id", "lab_test_type_id", name="uq_product_test"),
    )

    @validates("specification")
    def validate_specification(self, key, value):
        """Validate specification format."""
        if not value or not value.strip():
            raise ValueError("Specification cannot be empty")
        return value.strip()

    @property
    def test_name(self):
        """Get test name from related lab test type."""
        return self.lab_test_type.test_name if self.lab_test_type else None

    @property
    def test_unit(self):
        """Get test unit from related lab test type."""
        return self.lab_test_type.default_unit if self.lab_test_type else None

    @property
    def test_category(self):
        """Get test category from related lab test type."""
        return self.lab_test_type.test_category if self.lab_test_type else None

    # Class-level aliases pointing at module constants in spec_matcher.
    # Kept so any code referencing ProductTestSpecification.NEGATIVE_ACCEPTED_VALUES
    # or POSITIVE_ACCEPTED_VALUES directly continues to work unchanged.
    from app.utils import spec_matcher as _sm  # noqa: E402

    NEGATIVE_ACCEPTED_VALUES = _sm.NEGATIVE_ACCEPTED_VALUES
    POSITIVE_ACCEPTED_VALUES = _sm.POSITIVE_ACCEPTED_VALUES
    del _sm

    def matches_result(self, result_value):
        """
        Check if a test result matches this specification.

        Args:
            result_value: The actual test result value

        Returns:
            bool: True if passes, False if fails
        """
        from app.utils.spec_matcher import specification_matches

        # ProductTestSpecification.specification is NOT NULL (validated non-empty),
        # so the None→True shortcut in specification_matches will never trigger here;
        # behaviour is identical to the original implementation.
        return specification_matches(self.specification, self.test_unit, result_value)

    def __repr__(self):
        """String representation."""
        return (
            f"<ProductTestSpecification(product_id={self.product_id}, "
            f"test='{self.test_name}', spec='{self.specification}', "
            f"required={self.is_required})>"
        )
