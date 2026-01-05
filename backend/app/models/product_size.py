"""ProductSize model for multi-size product variants."""

from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel


class ProductSize(BaseModel):
    """
    ProductSize model representing size variants for a product.

    Each product can have multiple sizes (e.g., 2lb, 5lb, 10lb).
    Test specifications remain at the product level (same specs for all sizes).
    Sizes are primarily used for COA generation.

    Attributes:
        product_id: Foreign key to parent product
        size: Size label (e.g., "2lb", "5lb", "500g")
    """

    __tablename__ = "product_sizes"

    # Core fields
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    size = Column(String(50), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="sizes")

    # Constraints
    __table_args__ = (
        UniqueConstraint("product_id", "size", name="uq_product_size"),
        Index("idx_product_size_product_id", "product_id"),
    )

    @validates("size")
    def validate_size(self, key, value):
        """Validate size is not empty."""
        if not value or not value.strip():
            raise ValueError("Size cannot be empty")
        return value.strip()

    def __repr__(self):
        """String representation of ProductSize."""
        return f"<ProductSize(id={self.id}, product_id={self.product_id}, size='{self.size}')>"
