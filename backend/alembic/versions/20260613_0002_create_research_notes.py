"""Create research notes.

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0002"
down_revision: str | None = "20260613_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "scanner_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
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
            "source_type <> 'ai_generated' "
            "OR (model_name IS NOT NULL AND prompt_version IS NOT NULL)",
            name=op.f("ck_research_notes_generated_metadata_present"),
        ),
        sa.CheckConstraint(
            "stock_id IS NOT NULL OR scanner_run_id IS NOT NULL",
            name=op.f("ck_research_notes_has_context_reference"),
        ),
        sa.CheckConstraint(
            "source_type IN ('manual', 'ai_generated')",
            name=op.f("ck_research_notes_valid_source_type"),
        ),
        sa.ForeignKeyConstraint(
            ["scanner_run_id"],
            ["scanner_runs.id"],
            name=op.f("fk_research_notes_scanner_run_id_scanner_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_research_notes_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_notes")),
    )
    op.create_index(
        "ix_research_notes_scanner_run_id_created_at_desc",
        "research_notes",
        ["scanner_run_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_research_notes_stock_id_created_at_desc",
        "research_notes",
        ["stock_id", sa.literal_column("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_notes_stock_id_created_at_desc",
        table_name="research_notes",
    )
    op.drop_index(
        "ix_research_notes_scanner_run_id_created_at_desc",
        table_name="research_notes",
    )
    op.drop_table("research_notes")
