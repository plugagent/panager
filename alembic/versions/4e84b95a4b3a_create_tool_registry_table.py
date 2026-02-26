"""create tool_registry table

Revision ID: 4e84b95a4b3a
Revises: 5edb886461e3
Create Date: 2026-02-27 02:05:07.415118

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e84b95a4b3a"
down_revision: Union[str, Sequence[str], None] = "5edb886461e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tool_registry",
        sa.Column("name", sa.Text, primary_key=True),
        sa.Column("domain", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("schema", sa.JSON, nullable=False),
        sa.Column("embedding", sa.Text, nullable=False),
    )
    op.execute(
        "ALTER TABLE tool_registry ALTER COLUMN embedding TYPE vector(768) USING embedding::vector"
    )
    op.execute(
        "CREATE INDEX ix_tool_registry_embedding ON tool_registry "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tool_registry")
