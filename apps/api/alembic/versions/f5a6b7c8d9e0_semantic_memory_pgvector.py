"""semantic memory: pgvector embedding on workspace_memories (merges heads)

Adds the `embedding` column + HNSW cosine index for hybrid semantic search.
Also merges the two prior alembic heads (e3f4a5b6c7d8 + d4e5f6a7b8c9) into one.

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8, d4e5f6a7b8c9
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "f5a6b7c8d9e0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    # pgvector extension (image is pgvector/pgvector:pg16, so this just enables it)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "workspace_memories",
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )

    # HNSW index for cosine similarity — good recall, no training step (unlike ivfflat).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workspace_memories_embedding "
        "ON workspace_memories USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_workspace_memories_embedding")
    op.drop_column("workspace_memories", "embedding")
