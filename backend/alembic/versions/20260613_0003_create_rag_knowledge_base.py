"""Create RAG knowledge base.

Revision ID: 20260613_0003
Revises: 20260613_0002
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0003"
down_revision: str | None = "20260613_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSIONS = 256


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("source_uri", sa.String(length=2048), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "byte_size >= 0 AND character_count > 0",
            name=op.f("ck_knowledge_documents_valid_size"),
        ),
        sa.CheckConstraint(
            f"embedding_dimensions = {EMBEDDING_DIMENSIONS}",
            name=op.f("ck_knowledge_documents_supported_embedding_dimensions"),
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name=op.f("ck_knowledge_documents_valid_page_count"),
        ),
        sa.CheckConstraint(
            "document_type IN ("
            "'company_announcement', 'annual_report', 'research_note', 'other'"
            ")",
            name=op.f("ck_knowledge_documents_valid_document_type"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_knowledge_documents_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint(
            "content_sha256",
            name=op.f("uq_knowledge_documents_content_sha256"),
        ),
    )
    op.create_index(
        "ix_knowledge_documents_stock_id_created_at_desc",
        "knowledge_documents",
        ["stock_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_type_created_at_desc",
        "knowledge_documents",
        ["document_type", sa.literal_column("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("start_character", sa.Integer(), nullable=False),
        sa.Column("end_character", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("embedding", VECTOR(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "start_character >= 0 AND end_character > start_character",
            name=op.f("ck_document_chunks_valid_character_range"),
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f("ck_document_chunks_non_negative_chunk_index"),
        ),
        sa.CheckConstraint(
            "character_count > 0",
            name=op.f("ck_document_chunks_positive_character_count"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            name=op.f("fk_document_chunks_document_id_knowledge_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name=op.f("uq_document_chunks_document_id_chunk_index"),
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunks_embedding_hnsw",
        table_name="document_chunks",
        postgresql_using="hnsw",
    )
    op.drop_index(
        "ix_document_chunks_document_id",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")

    op.drop_index(
        "ix_knowledge_documents_type_created_at_desc",
        table_name="knowledge_documents",
    )
    op.drop_index(
        "ix_knowledge_documents_stock_id_created_at_desc",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
