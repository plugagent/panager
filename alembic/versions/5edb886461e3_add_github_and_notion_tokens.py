"""add github and notion tokens

Revision ID: 5edb886461e3
Revises: 38885c1da4bf
Create Date: 2026-02-26 00:01:18.505348

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5edb886461e3"
down_revision: Union[str, Sequence[str], None] = "38885c1da4bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "github_tokens",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "notion_tokens",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("notion_tokens")
    op.drop_table("github_tokens")
