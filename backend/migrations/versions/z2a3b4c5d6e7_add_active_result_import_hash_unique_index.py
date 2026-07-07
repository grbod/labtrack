"""Add active result import file hash unique index

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_result_import_active_file_hash",
        "result_imports",
        ["file_hash"],
        unique=True,
        sqlite_where=sa.text(
            "status IN ('PROCESSING','NEEDS_CONFIRMATION','CONFIRMED')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_result_import_active_file_hash",
        table_name="result_imports",
    )
