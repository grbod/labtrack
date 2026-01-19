"""Add user profile fields for COA signing

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add profile fields to users table
    op.add_column('users', sa.Column('full_name', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('title', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('signature_path', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove profile fields
    op.drop_column('users', 'signature_path')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'title')
    op.drop_column('users', 'full_name')
