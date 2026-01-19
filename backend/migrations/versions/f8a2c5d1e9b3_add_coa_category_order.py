"""add_coa_category_order

Revision ID: f8a2c5d1e9b3
Revises: eeda354a06d5
Create Date: 2026-01-10 21:30:00.000000

"""

from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a2c5d1e9b3"
down_revision: Union[str, Sequence[str], None] = "eeda354a06d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create coa_category_orders table
    op.create_table(
        "coa_category_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category_order", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default row with alphabetically sorted categories
    default_order = [
        "Allergens",
        "Chemical",
        "Heavy Metals",
        "Microbiological",
        "Nutritional",
        "Organoleptic",
        "Pesticides",
        "Physical",
    ]

    op.execute(
        sa.text(
            """
            INSERT INTO coa_category_orders (category_order, created_at, updated_at)
            VALUES (:order, :now, :now)
            """
        ).bindparams(
            order=str(default_order).replace("'", '"'),  # Convert to JSON string
            now=datetime.utcnow(),
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("coa_category_orders")
