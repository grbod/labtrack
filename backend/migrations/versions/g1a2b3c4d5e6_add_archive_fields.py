"""add_archive_fields

Revision ID: g1a2b3c4d5e6
Revises: f8a2c5d1e9b3
Create Date: 2026-01-10 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f8a2c5d1e9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add archive fields to products, lab_test_types, and customers.

    Note: SQLite doesn't support adding foreign keys directly, so we skip
    the foreign key constraints. The relationships will work without them.
    """

    # Add archive fields to products table
    # (products doesn't have is_active yet, so add all 4 fields)
    op.add_column(
        "products",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.add_column(
        "products",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("archived_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("archive_reason", sa.String(length=500), nullable=True),
    )
    op.create_index("idx_product_is_active", "products", ["is_active"])

    # Add archive metadata fields to lab_test_types table
    # (already has is_active, just add metadata fields)
    op.add_column(
        "lab_test_types",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "lab_test_types",
        sa.Column("archived_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lab_test_types",
        sa.Column("archive_reason", sa.String(length=500), nullable=True),
    )

    # Add archive metadata fields to customers table
    # (already has is_active, just add metadata fields)
    op.add_column(
        "customers",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("archived_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("archive_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Remove archive fields from products, lab_test_types, and customers."""

    # Remove from customers
    op.drop_column("customers", "archive_reason")
    op.drop_column("customers", "archived_by_id")
    op.drop_column("customers", "archived_at")

    # Remove from lab_test_types
    op.drop_column("lab_test_types", "archive_reason")
    op.drop_column("lab_test_types", "archived_by_id")
    op.drop_column("lab_test_types", "archived_at")

    # Remove from products
    op.drop_index("idx_product_is_active", table_name="products")
    op.drop_column("products", "archive_reason")
    op.drop_column("products", "archived_by_id")
    op.drop_column("products", "archived_at")
    op.drop_column("products", "is_active")
