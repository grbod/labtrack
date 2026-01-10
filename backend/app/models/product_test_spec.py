"""Product test specification model linking products to required/optional tests."""

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, UniqueConstraint
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
    
    # Accepted values for specs starting with "Negative" (case-insensitive)
    NEGATIVE_ACCEPTED_VALUES = ['negative', 'nd', 'not detected', 'bdl']

    # Accepted values for specs starting with "Positive" (case-insensitive)
    POSITIVE_ACCEPTED_VALUES = ['positive', 'detected', 'present', '+']

    @staticmethod
    def _parse_numeric_value(s):
        """
        Parse a numeric value from a string, handling commas as thousands separators
        and stripping any trailing text (like units).

        Args:
            s: The string to parse (e.g., "10,000", "10,000 CFU/g", "10.5")

        Returns:
            float or None if not a valid number
        """
        import re
        # Remove commas (thousands separators) and trim
        cleaned = s.replace(',', '').strip()
        # Extract the numeric part (handles cases like "10000 CFU/g")
        match = re.match(r'^-?[\d.]+', cleaned)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    def matches_result(self, result_value):
        """
        Check if a test result matches this specification.

        Args:
            result_value: The actual test result value

        Returns:
            bool: True if passes, False if fails
        """
        if not result_value:
            return False

        spec = self.specification.strip().lower()
        value = str(result_value).strip().lower()

        # Handle Positive/Negative results (legacy unit-based check)
        if self.test_unit == "Positive/Negative":
            if spec == "negative" and value in self.NEGATIVE_ACCEPTED_VALUES:
                return True
            if spec == "positive" and value in self.POSITIVE_ACCEPTED_VALUES:
                return True
            return False

        # Handle specs starting with "Negative" (e.g., "Negative in 10g")
        if spec.startswith("negative"):
            # Accept: Negative, ND, Not Detected, BDL, or any <X value
            if value in self.NEGATIVE_ACCEPTED_VALUES:
                return True
            # Also accept "<X" values (below detection limit)
            if value.startswith("<"):
                return True
            return False

        # Handle specs starting with "Positive" (e.g., "Positive in 10g")
        if spec.startswith("positive"):
            # Accept: Positive, Detected, Present, +
            return value in self.POSITIVE_ACCEPTED_VALUES

        # Handle "< X" specifications (supports commas and units like "<10,000 CFU/g")
        if spec.startswith("<"):
            spec_limit = self._parse_numeric_value(spec[1:])
            if spec_limit is None:
                return False
            if value.startswith("<"):
                # Both are "less than" values
                return True
            result_val = self._parse_numeric_value(value)
            if result_val is None:
                return False
            return result_val < spec_limit

        # Handle "> X" specifications (supports commas and units)
        if spec.startswith(">"):
            spec_limit = self._parse_numeric_value(spec[1:])
            if spec_limit is None:
                return False
            if value.startswith(">"):
                # Both are "greater than" values
                return True
            result_val = self._parse_numeric_value(value)
            if result_val is None:
                return False
            return result_val > spec_limit

        # Handle range specifications (e.g., "5-10", "1,000-10,000")
        if "-" in spec and not spec.startswith("-"):
            parts = spec.split("-")
            if len(parts) == 2:
                min_val = self._parse_numeric_value(parts[0])
                max_val = self._parse_numeric_value(parts[1])
                result_val = self._parse_numeric_value(value)
                if min_val is not None and max_val is not None and result_val is not None:
                    return min_val <= result_val <= max_val
            return False

        # Handle exact match
        return spec == value
    
    def __repr__(self):
        """String representation."""
        return (
            f"<ProductTestSpecification(product_id={self.product_id}, "
            f"test='{self.test_name}', spec='{self.specification}', "
            f"required={self.is_required})>"
        )