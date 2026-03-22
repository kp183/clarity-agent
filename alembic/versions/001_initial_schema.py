"""Initial schema: incidents and gotchas tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.VARCHAR(), nullable=False),
        sa.Column("incident_id", sa.VARCHAR(), nullable=True),
        sa.Column("summary", sa.TEXT(), nullable=True),
        sa.Column("root_cause", sa.TEXT(), nullable=True),
        sa.Column("confidence_score", sa.FLOAT(), nullable=True),
        sa.Column("created_at", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "gotchas",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("pattern", sa.TEXT(), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("created_at", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("gotchas")
    op.drop_table("incidents")
