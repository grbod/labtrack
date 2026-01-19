"""Add city, state, zip_code fields to lab_info

Revision ID: i1j2k3l4m5n6
Revises: h1b2c3d4e5f6
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i1j2k3l4m5n6'
down_revision: Union[str, None] = 'h1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new address fields to lab_info table with defaults for SQLite compatibility
    op.add_column('lab_info', sa.Column('city', sa.String(100), nullable=False, server_default='Lab City'))
    op.add_column('lab_info', sa.Column('state', sa.String(50), nullable=False, server_default='FL'))
    op.add_column('lab_info', sa.Column('zip_code', sa.String(20), nullable=False, server_default='12345'))


def downgrade() -> None:
    # Remove address fields
    op.drop_column('lab_info', 'zip_code')
    op.drop_column('lab_info', 'state')
    op.drop_column('lab_info', 'city')
