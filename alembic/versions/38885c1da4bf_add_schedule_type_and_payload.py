"""add schedule type and payload

Revision ID: 38885c1da4bf
Revises: 0001
Create Date: 2026-02-23 12:07:50.211316

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "38885c1da4bf"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "schedules",
        sa.Column("type", sa.String(), nullable=False, server_default="notification"),
    )
    op.add_column("schedules", sa.Column("payload", postgresql.JSONB(), nullable=True))
    op.add_column("schedules", sa.Column("metadata", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("schedules", "metadata")
    op.drop_column("schedules", "payload")
    op.drop_column("schedules", "type")
