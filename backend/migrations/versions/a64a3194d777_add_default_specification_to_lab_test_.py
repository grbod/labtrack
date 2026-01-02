"""add_default_specification_to_lab_test_types

Revision ID: a64a3194d777
Revises: bf8713feb41a
Create Date: 2025-08-06 00:02:53.557620

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a64a3194d777"
down_revision: Union[str, Sequence[str], None] = "bf8713feb41a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add default_specification column to lab_test_types table
    op.add_column(
        'lab_test_types',
        sa.Column('default_specification', sa.String(100), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove default_specification column from lab_test_types table
    op.drop_column('lab_test_types', 'default_specification')
