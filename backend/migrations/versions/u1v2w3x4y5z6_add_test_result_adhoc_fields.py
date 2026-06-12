"""Add lab_test_type_id and include_on_coa to test_results

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "u1v2w3x4y5z6"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("test_results") as batch_op:
        batch_op.add_column(sa.Column("lab_test_type_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "include_on_coa",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.create_foreign_key(
            "fk_test_results_lab_test_type_id",
            "lab_test_types",
            ["lab_test_type_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("test_results") as batch_op:
        batch_op.drop_constraint("fk_test_results_lab_test_type_id", type_="foreignkey")
        batch_op.drop_column("include_on_coa")
        batch_op.drop_column("lab_test_type_id")
