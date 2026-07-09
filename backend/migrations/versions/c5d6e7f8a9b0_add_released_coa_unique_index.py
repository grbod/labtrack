"""Add partial unique index enforcing one RELEASED COA per (lot, product)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # At most one RELEASED COARelease per (lot_id, product_id). The status enum
    # is NAME-stored, so the predicate matches on the uppercase 'RELEASED'.
    # Both sqlite_where and postgresql_where are supplied so the partial index
    # applies on either backend.
    op.create_index(
        "uq_release_released",
        "coa_releases",
        ["lot_id", "product_id"],
        unique=True,
        sqlite_where=sa.text("status = 'RELEASED'"),
        postgresql_where=sa.text("status = 'RELEASED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_release_released",
        table_name="coa_releases",
    )
