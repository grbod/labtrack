"""Add lab test types and product specifications

Revision ID: lab_test_types_001
Revises: bd6cc08b5c37
Create Date: 2025-01-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "lab_test_types_001"
down_revision: Union[str, Sequence[str], None] = "bd6cc08b5c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create lab_test_types table
    op.create_table(
        "lab_test_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("test_name", sa.String(length=100), nullable=False),
        sa.Column("test_category", sa.String(length=50), nullable=False),
        sa.Column("default_unit", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("test_method", sa.String(length=100), nullable=True),
        sa.Column("abbreviations", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_name")
    )
    
    # Create indexes for lab_test_types
    op.create_index("idx_lab_test_types_name", "lab_test_types", ["test_name"])
    op.create_index("idx_lab_test_types_category", "lab_test_types", ["test_category"])
    op.create_index("idx_lab_test_types_active", "lab_test_types", ["is_active"])

    # Create product_test_specifications table
    op.create_table(
        "product_test_specifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("lab_test_type_id", sa.Integer(), nullable=False),
        sa.Column("specification", sa.String(length=100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, default=True),
        sa.ForeignKeyConstraint(["lab_test_type_id"], ["lab_test_types.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "lab_test_type_id", name="uq_product_test_spec")
    )
    
    # Create indexes for product_test_specifications
    op.create_index("idx_product_test_spec_product", "product_test_specifications", ["product_id"])
    op.create_index("idx_product_test_spec_test_type", "product_test_specifications", ["lab_test_type_id"])
    op.create_index("idx_product_test_spec_required", "product_test_specifications", ["is_required"])

    # Add PARTIAL_RESULTS status to lot_status enum
    # For SQLite, we need to handle enum changes differently
    # Note: This assumes LotStatus enum is implemented as CHECK constraint or similar
    # If using a different database, this would need to be adjusted
    
    # Add new lot status column temporarily
    with op.batch_alter_table("lots") as batch_op:
        # SQLite doesn't support direct enum modification, so we'll handle this at the application level
        # The PARTIAL_RESULTS status is already added to the Python enum
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Drop product_test_specifications table
    op.drop_index("idx_product_test_spec_required", "product_test_specifications")
    op.drop_index("idx_product_test_spec_test_type", "product_test_specifications")
    op.drop_index("idx_product_test_spec_product", "product_test_specifications")
    op.drop_table("product_test_specifications")
    
    # Drop lab_test_types table
    op.drop_index("idx_lab_test_types_active", "lab_test_types")
    op.drop_index("idx_lab_test_types_category", "lab_test_types")
    op.drop_index("idx_lab_test_types_name", "lab_test_types")
    op.drop_table("lab_test_types")
    
    # Note: PARTIAL_RESULTS status removal would need to be handled at application level