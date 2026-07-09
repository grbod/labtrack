"""Replace plain unique(coa_release_id) with partial unique (active snapshots)

The inline UNIQUE from a3b4c5d6e7f8 blocked re-release revisions: after an
admin void, re-releasing the same COARelease must create a second snapshot
row (revision N+1, supersedes link) while the voided row is kept forever.
The model now declares a partial unique index (one ACTIVE snapshot per
release); this migration brings the database in line.

SQLite cannot drop an inline table constraint, so the table is rebuilt.
Safe: coa_snapshots was introduced one revision earlier and holds no data
anywhere (feature unreleased); a guard aborts if rows exist.

Revision ID: b5c6d7e8f9a1
Revises: a3b4c5d6e7f8
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b5c6d7e8f9a1"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _assert_empty() -> None:
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM coa_snapshots")).scalar()
    if count:
        raise RuntimeError(
            f"coa_snapshots has {count} rows; this rebuild migration expects an "
            "empty table. Migrate the data manually before proceeding."
        )


def _drop_all() -> None:
    op.drop_index("idx_coa_snapshot_release_voided", table_name="coa_snapshots")
    op.drop_index("idx_coa_snapshot_created_at", table_name="coa_snapshots")
    op.drop_table("coa_snapshots")


def _create_table(with_plain_unique: bool) -> None:
    constraints = [
        sa.ForeignKeyConstraint(
            ["coa_release_id"], ["coa_releases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["coa_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coa_serial"),
    ]
    if with_plain_unique:
        constraints.append(sa.UniqueConstraint("coa_release_id"))
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
        *constraints,
    )
    op.create_index(
        "idx_coa_snapshot_created_at", "coa_snapshots", ["created_at"], unique=False
    )
    op.create_index(
        "idx_coa_snapshot_release_voided",
        "coa_snapshots",
        ["coa_release_id", "voided"],
        unique=False,
    )


def upgrade() -> None:
    _assert_empty()
    _drop_all()
    _create_table(with_plain_unique=False)
    op.create_index(
        "uq_coa_snapshot_active_release",
        "coa_snapshots",
        ["coa_release_id"],
        unique=True,
        sqlite_where=sa.text("voided = 0"),
        postgresql_where=sa.text("voided = false"),
    )


def downgrade() -> None:
    _assert_empty()
    op.drop_index("uq_coa_snapshot_active_release", table_name="coa_snapshots")
    _drop_all()
    _create_table(with_plain_unique=True)
