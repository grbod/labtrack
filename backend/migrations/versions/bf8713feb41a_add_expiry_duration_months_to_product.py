"""add_expiry_duration_months_to_product

Revision ID: bf8713feb41a
Revises: 46b9ed318a13
Create Date: 2025-08-05 23:08:22.507148

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bf8713feb41a"
down_revision: Union[str, Sequence[str], None] = "46b9ed318a13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add expiry_duration_months column to products table
    op.add_column(
        'products',
        sa.Column('expiry_duration_months', sa.Integer(), nullable=False, server_default='36')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove expiry_duration_months column from products table
    op.drop_column('products', 'expiry_duration_months')
