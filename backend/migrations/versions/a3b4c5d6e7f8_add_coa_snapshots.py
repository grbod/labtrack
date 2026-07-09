"""Add immutable COA snapshots

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a3b4c5d6e7f8"
down_revision = "w4a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coa_serial_counters",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "coa_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coa_release_id", sa.Integer(), nullable=False),
        sa.Column("coa_serial", sa.String(length=32), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=False),
        sa.Column("context_schema_version", sa.Integer(), nullable=False),
        sa.Column("pdf_storage_key", sa.String(length=500), nullable=False),
        sa.Column("signature_storage_key", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "reconstructed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("voided", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["coa_release_id"], ["coa_releases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["coa_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coa_release_id"),
        sa.UniqueConstraint("coa_serial"),
    )
    op.create_index(
        "idx_coa_snapshot_created_at",
        "coa_snapshots",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_coa_snapshot_release_voided",
        "coa_snapshots",
        ["coa_release_id", "voided"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_coa_snapshot_release_voided", table_name="coa_snapshots")
    op.drop_index("idx_coa_snapshot_created_at", table_name="coa_snapshots")
    op.drop_table("coa_snapshots")
    op.drop_table("coa_serial_counters")
