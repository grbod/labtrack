"""add_customer_coa_release_email_tables

Revision ID: a6857ee46e33
Revises: d9f0a3c4e5f6
Create Date: 2026-01-04 23:30:14.778053

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6857ee46e33"
down_revision: Union[str, Sequence[str], None] = "d9f0a3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_customer_company", "customers", ["company_name"])
    op.create_index("idx_customer_email", "customers", ["email"])
    op.create_index("idx_customer_active", "customers", ["is_active"])

    # Create email_templates table
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            server_default="coa_email",
        ),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create coa_releases table
    op.create_table(
        "coa_releases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("AWAITING_RELEASE", "RELEASED", name="coareleasestatus"),
            nullable=False,
            server_default="AWAITING_RELEASE",
        ),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("coa_file_path", sa.String(length=500), nullable=True),
        sa.Column("draft_data", sa.JSON(), nullable=True),
        sa.Column("send_back_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["released_by_id"], ["users.id"]),
    )
    op.create_index("idx_coa_release_lot", "coa_releases", ["lot_id"])
    op.create_index("idx_coa_release_product", "coa_releases", ["product_id"])
    op.create_index("idx_coa_release_customer", "coa_releases", ["customer_id"])
    op.create_index("idx_coa_release_status", "coa_releases", ["status"])
    op.create_index(
        "idx_coa_release_lot_status", "coa_releases", ["lot_id", "status"]
    )

    # Create email_history table
    op.create_table(
        "email_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coa_release_id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("sent_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["coa_release_id"], ["coa_releases.id"]),
        sa.ForeignKeyConstraint(["sent_by_id"], ["users.id"]),
    )
    op.create_index(
        "idx_email_history_coa_release", "email_history", ["coa_release_id"]
    )
    op.create_index(
        "idx_email_history_recipient", "email_history", ["recipient_email"]
    )
    op.create_index("idx_email_history_sent_at", "email_history", ["sent_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("email_history")
    op.drop_table("coa_releases")
    op.drop_table("email_templates")
    op.drop_table("customers")
