"""Product model for standardized product catalog."""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.orm import relationship, validates
from src.models.base import BaseModel


class Product(BaseModel):
    """
    Product model representing standardized product catalog.

    Attributes:
        brand: Product brand name (e.g., "Truvani")
        product_name: Base product name (e.g., "Organic Whey Protein")
        flavor: Product flavor variant (e.g., "Vanilla", "Chocolate")
        size: Product size/weight (e.g., "2.5 lbs", "500g")
        display_name: Standardized display name for COAs
    """

    __tablename__ = "products"

    # Core fields
    brand = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    flavor = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)
    display_name = Column(Text, nullable=False)

    # Relationships
    lot_products = relationship(
        "LotProduct", back_populates="product", cascade="all, delete-orphan"
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
