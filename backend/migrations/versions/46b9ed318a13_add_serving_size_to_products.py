"""add_serving_size_to_products

Revision ID: 46b9ed318a13
Revises: fix_prod_test_spec_001
Create Date: 2025-08-05 13:32:41.197231

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "46b9ed318a13"
down_revision: Union[str, Sequence[str], None] = "fix_prod_test_spec_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add serving_size column to products table
    op.add_column(
        "products",
        sa.Column("serving_size", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    
    # Update existing products with random serving sizes between 25-32g
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT id FROM products"))
    product_ids = [row[0] for row in result]
    
    # Use a deterministic approach for reproducibility
    import random
    random.seed(42)  # Fixed seed for consistent results
    
    for product_id in product_ids:
        # Generate random serving size between 25 and 32 grams (to 2 decimal places)
        serving_size = round(random.uniform(25.0, 32.0), 2)
        connection.execute(
            sa.text("UPDATE products SET serving_size = :size WHERE id = :id"),
            {"size": serving_size, "id": product_id}
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove serving_size column from products table
    op.drop_column("products", "serving_size")
