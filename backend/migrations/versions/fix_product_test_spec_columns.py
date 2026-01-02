"""Fix missing columns in product_test_specifications table

Revision ID: fix_prod_test_spec_001
Revises: lab_test_types_001
Create Date: 2025-01-16 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fix_prod_test_spec_001"
down_revision: Union[str, Sequence[str], None] = "lab_test_types_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to product_test_specifications table."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('product_test_specifications') as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('min_value', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('max_value', sa.String(20), nullable=True))


def downgrade() -> None:
    """Remove added columns from product_test_specifications table."""
    with op.batch_alter_table('product_test_specifications') as batch_op:
        batch_op.drop_column('max_value')
        batch_op.drop_column('min_value')
        batch_op.drop_column('notes')