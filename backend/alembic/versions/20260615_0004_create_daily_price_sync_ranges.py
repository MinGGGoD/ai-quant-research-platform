"""Create daily price synchronization coverage ranges.

Revision ID: 20260615_0004
Revises: 20260613_0003
Create Date: 2026-06-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_0004"
down_revision: str | None = "20260613_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_price_sync_ranges",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name=op.f("ck_daily_price_sync_ranges_valid_date_range"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_daily_price_sync_ranges_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_daily_price_sync_ranges"),
        ),
    )
    op.create_index(
        "ix_daily_price_sync_ranges_stock_source_dates",
        "daily_price_sync_ranges",
        ["stock_id", "source", "start_date", "end_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_price_sync_ranges_stock_source_dates",
        table_name="daily_price_sync_ranges",
    )
    op.drop_table("daily_price_sync_ranges")
