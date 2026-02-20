"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-02-20

"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger, primary_key=True),
        sa.Column("username", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("profile", sa.JSON, server_default="{}", nullable=False),
    )

    op.create_table(
        "google_tokens",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id"),
            primary_key=True,
        ),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "schedules",
        sa.Column(
            "id",
            sa.UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("trigger_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean, server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_schedules_user_sent_trigger",
        "schedules",
        ["user_id", "sent", "trigger_at"],
    )

    op.create_table(
        "memories",
        sa.Column(
            "id",
            sa.UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=False),  # vector(768) — raw SQL
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON, server_default="{}", nullable=False),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    # vector 컬럼은 ALTER TABLE로 타입 변경 후 HNSW 인덱스 생성
    op.execute(
        "ALTER TABLE memories ALTER COLUMN embedding TYPE vector(768) USING embedding::vector"
    )
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("memories")
    op.drop_table("schedules")
    op.drop_table("google_tokens")
    op.drop_table("users")
