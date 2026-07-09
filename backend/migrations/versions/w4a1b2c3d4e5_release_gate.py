"""Release gate: sensory attests, release deviation/void columns, result created_by

Revision ID: w4a1b2c3d4e5
Revises: z2a3b4c5d6e7
Create Date: 2026-07-09

NOTE (coordination): a parallel worker also chains a migration on z2a3b4c5d6e7.
This revision uses a distinct id; the orchestrator may re-chain one of the two
at merge time. Keep upgrade()/downgrade() idempotent-safe on SQLite batch mode.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "w4a1b2c3d4e5"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # coa_releases: deviation note (override) + void trail
    with op.batch_alter_table("coa_releases") as batch:
        batch.add_column(sa.Column("deviation_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("voided_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("voided_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("voided_by_id", sa.Integer(), nullable=True)
        )

    # test_results: creator (for self-approval detection)
    with op.batch_alter_table("test_results") as batch:
        batch.add_column(
            sa.Column("created_by_id", sa.Integer(), nullable=True)
        )

    # release_sensory_attests
    op.create_table(
        "release_sensory_attests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("lab_test_type_id", sa.Integer(), nullable=False),
        sa.Column("attested_by_id", sa.Integer(), nullable=True),
        sa.Column("attested_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["release_id"], ["coa_releases.id"]),
        sa.ForeignKeyConstraint(["lab_test_type_id"], ["lab_test_types.id"]),
        sa.ForeignKeyConstraint(["attested_by_id"], ["users.id"]),
        sa.UniqueConstraint(
            "release_id",
            "lab_test_type_id",
            name="uq_release_sensory_attest",
        ),
    )
    op.create_index(
        "idx_release_sensory_attest_release",
        "release_sensory_attests",
        ["release_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_release_sensory_attest_release",
        table_name="release_sensory_attests",
    )
    op.drop_table("release_sensory_attests")

    with op.batch_alter_table("test_results") as batch:
        batch.drop_column("created_by_id")

    with op.batch_alter_table("coa_releases") as batch:
        batch.drop_column("voided_by_id")
        batch.drop_column("voided_at")
        batch.drop_column("voided_note")
        batch.drop_column("deviation_note")
