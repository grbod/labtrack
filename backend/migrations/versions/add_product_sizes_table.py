"""add_product_sizes_table

Revision ID: d9f0a3c4e5f6
Revises: c8f9a2b3d4e5
Create Date: 2025-01-03

Add product_sizes table to support multiple size variants per product.
Migrates existing single size values from products.size to product_sizes.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9f0a3c4e5f6"
down_revision = "c8f9a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    # Create product_sizes table
    op.create_table(
        "product_sizes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("size", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("product_id", "size", name="uq_product_size"),
    )

    # Create index on product_id for faster lookups
    op.create_index("idx_product_size_product_id", "product_sizes", ["product_id"])

    # Migrate existing size data from products.size to product_sizes
    # Only create records for products that have a non-null, non-empty size
    op.execute("""
        INSERT INTO product_sizes (product_id, size, created_at, updated_at)
        SELECT id, size, NOW(), NOW()
        FROM products
        WHERE size IS NOT NULL AND TRIM(size) != ''
    """)


def downgrade():
    # Note: This will lose multi-size data, keeping only the first size per product
    # Update products.size with the first size from product_sizes (if any)
    op.execute("""
        UPDATE products
        SET size = (
            SELECT ps.size
            FROM product_sizes ps
            WHERE ps.product_id = products.id
            ORDER BY ps.id
            LIMIT 1
        )
    """)

    # Drop the product_sizes table
    op.drop_index("idx_product_size_product_id", "product_sizes")
    op.drop_table("product_sizes")
