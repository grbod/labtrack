"""Add confidence_score to parsing_queue

Revision ID: bd6cc08b5c37
Revises:
Create Date: 2025-08-02 23:25:38.914258

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "bd6cc08b5c37"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if "parsing_queue" in inspect(op.get_bind()).get_table_names():
        op.add_column(
            "parsing_queue",
            sa.Column(
                "confidence_score", sa.Numeric(precision=3, scale=2), nullable=True
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    if "parsing_queue" in inspect(op.get_bind()).get_table_names():
        columns = {
            column["name"]
            for column in inspect(op.get_bind()).get_columns("parsing_queue")
        }
        if "confidence_score" in columns:
            op.drop_column("parsing_queue", "confidence_score")
