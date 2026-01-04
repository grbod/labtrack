"""Product model for standardized product catalog."""

from sqlalchemy import Column, String, Text, Index, Integer
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel


class Product(BaseModel):
    """
    Product model representing standardized product catalog.

    Attributes:
        brand: Product brand name (e.g., "Truvani")
        product_name: Base product name (e.g., "Organic Whey Protein")
        flavor: Product flavor variant (e.g., "Vanilla", "Chocolate")
        size: Product size/weight (e.g., "2.5 lbs", "500g")
        display_name: Standardized display name for COAs
        serving_size: Serving size (e.g., "30g", "2 capsules", "1 tsp")
    """

    __tablename__ = "products"

    # Core fields
    brand = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    flavor = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)
    display_name = Column(Text, nullable=False)
    serving_size = Column(String(50), nullable=True)  # e.g., "30g", "2 capsules", "1 tsp"
    expiry_duration_months = Column(Integer, nullable=False, default=36)  # Default 3 years

    # Relationships
    lot_products = relationship(
        "LotProduct", back_populates="product", cascade="all, delete-orphan"
    )
    test_specifications = relationship(
        "ProductTestSpecification",
        back_populates="product", 
        cascade="all, delete-orphan",
        order_by="ProductTestSpecification.lab_test_type_id"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_product_brand", "brand"),
        Index("idx_product_name", "product_name"),
        Index("idx_product_brand_name", "brand", "product_name"),
    )

    @validates("brand", "product_name", "display_name")
    def validate_required_fields(self, key, value):
        """Validate required string fields are not empty."""
        if not value or not value.strip():
            raise ValueError(f"{key} cannot be empty")
        return value.strip()

    @validates("flavor", "size")
    def validate_optional_fields(self, key, value):
        """Clean optional string fields."""
        return value.strip() if value else None

    @validates("serving_size")
    def validate_serving_size(self, key, value):
        """Clean serving size string if provided."""
        return value.strip() if value else None

    @validates("expiry_duration_months")
    def validate_expiry_duration(self, key, value):
        """Validate expiry duration is positive."""
        if value is not None and value <= 0:
            raise ValueError("Expiry duration must be positive")
        return value

    def __repr__(self):
        """String representation of Product."""
        return f"<Product(id={self.id}, brand='{self.brand}', name='{self.product_name}', flavor='{self.flavor}')>"

    def get_full_name(self):
        """Get full product name including all attributes."""
        parts = [self.brand, self.product_name]
        if self.flavor:
            parts.append(self.flavor)
        if self.size:
            parts.append(self.size)
        return " - ".join(parts)

    @property
    def required_tests(self):
        """Get list of required test specifications."""
        return [spec for spec in self.test_specifications if spec.is_required]

    @property
    def optional_tests(self):
        """Get list of optional test specifications."""
        return [spec for spec in self.test_specifications if not spec.is_required]

    @property
    def has_test_specifications(self):
        """Check if product has any test specifications."""
        return len(self.test_specifications) > 0

    def get_specification_for_test(self, test_name):
        """Get specification for a specific test by name."""
        for spec in self.test_specifications:
            if spec.lab_test_type.test_name.lower() == test_name.lower():
                return spec
        return None

    def get_required_test_names(self):
        """Get list of required test names."""
        return [spec.test_name for spec in self.required_tests]

    def get_all_test_names(self):
        """Get list of all test names (required and optional)."""
        return [spec.test_name for spec in self.test_specifications]
    
    @property
    def expiry_duration_display(self):
        """Get expiry duration in user-friendly format."""
        if not self.expiry_duration_months:
            return "Not set"
        
        years = self.expiry_duration_months // 12
        months = self.expiry_duration_months % 12
        
        if years > 0 and months == 0:
            return f"{years} year{'s' if years != 1 else ''}"
        elif years == 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
