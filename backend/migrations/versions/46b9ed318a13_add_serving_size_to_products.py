"""add_serving_size_to_products

Revision ID: 46b9ed318a13
Revises: fix_prod_test_spec_001
Create Date: 2025-08-05 13:32:41.197231

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "46b9ed318a13"
down_revision: Union[str, Sequence[str], None] = "fix_prod_test_spec_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if "products" not in inspect(op.get_bind()).get_table_names():
        return
    # Add serving_size column to products table
    op.add_column(
        "products",
        sa.Column("serving_size", sa.Numeric(precision=5, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove serving_size column from products table
    if "products" in inspect(op.get_bind()).get_table_names():
        columns = {
            column["name"] for column in inspect(op.get_bind()).get_columns("products")
        }
        if "serving_size" in columns:
            op.drop_column("products", "serving_size")
