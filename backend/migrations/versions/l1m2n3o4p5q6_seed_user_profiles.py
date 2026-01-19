"""Seed user profiles for Greg Simek and Tatyana Villegas

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l1m2n3o4p5q6'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update admin user profile
    op.execute(
        """
        UPDATE users
        SET full_name = 'Greg Simek', title = 'President'
        WHERE username = 'admin'
        """
    )

    # Update qcmanager user profile
    op.execute(
        """
        UPDATE users
        SET full_name = 'Tatyana Villegas', title = 'Quality Assurance Manager'
        WHERE username = 'qcmanager'
        """
    )


def downgrade() -> None:
    # Clear profile data
    op.execute(
        """
        UPDATE users
        SET full_name = NULL, title = NULL
        WHERE username IN ('admin', 'qcmanager')
        """
    )
