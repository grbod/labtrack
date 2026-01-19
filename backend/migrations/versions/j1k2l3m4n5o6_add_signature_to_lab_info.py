"""Add signature fields to lab_info

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, None] = 'i1j2k3l4m5n6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add signature fields to lab_info table
    op.add_column('lab_info', sa.Column('signature_path', sa.String(500), nullable=True))
    op.add_column('lab_info', sa.Column('signer_name', sa.String(200), nullable=True))


def downgrade() -> None:
    # Remove signature fields
    op.drop_column('lab_info', 'signer_name')
    op.drop_column('lab_info', 'signature_path')
