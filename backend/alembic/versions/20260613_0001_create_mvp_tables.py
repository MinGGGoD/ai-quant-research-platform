"""Create MVP database tables.

Revision ID: 20260613_0001
Revises:
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("delist_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
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
            "delist_date IS NULL OR list_date IS NULL OR delist_date >= list_date",
            name=op.f("ck_stocks_delist_not_before_list"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'delisted')",
            name=op.f("ck_stocks_valid_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stocks")),
        sa.UniqueConstraint(
            "exchange",
            "symbol",
            name=op.f("uq_stocks_exchange_symbol"),
        ),
    )
    op.create_index("ix_stocks_name", "stocks", ["name"], unique=False)

    op.create_table(
        "signal_definitions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_signal_definitions_positive_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signal_definitions")),
        sa.UniqueConstraint(
            "code",
            "version",
            name=op.f("uq_signal_definitions_code_version"),
        ),
    )

    op.create_table(
        "scanner_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("universe_name", sa.String(length=128), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "total_stocks",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "processed_stocks",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "matched_stocks",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "warning_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name=op.f("ck_scanner_runs_valid_finished_at"),
        ),
        sa.CheckConstraint(
            "total_stocks >= 0 AND processed_stocks >= 0 "
            "AND matched_stocks >= 0 AND warning_count >= 0 "
            "AND error_count >= 0",
            name=op.f("ck_scanner_runs_non_negative_counts"),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'pending', 'running', 'completed', "
            "'completed_with_warnings', 'failed'"
            ")",
            name=op.f("ck_scanner_runs_valid_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scanner_runs")),
    )
    op.create_index(
        "ix_scanner_runs_data_date_status",
        "scanner_runs",
        ["data_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_scanner_runs_started_at_desc",
        "scanner_runs",
        [sa.literal_column("started_at DESC")],
        unique=False,
    )

    op.create_table(
        "daily_prices",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=24, scale=4), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
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
            "high >= open AND high >= low AND high >= close",
            name=op.f("ck_daily_prices_valid_high"),
        ),
        sa.CheckConstraint(
            "low <= open AND low <= high AND low <= close",
            name=op.f("ck_daily_prices_valid_low"),
        ),
        sa.CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name=op.f("ck_daily_prices_non_negative_prices"),
        ),
        sa.CheckConstraint(
            "volume >= 0",
            name=op.f("ck_daily_prices_non_negative_volume"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_daily_prices_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_prices")),
        sa.UniqueConstraint(
            "stock_id",
            "trade_date",
            name=op.f("uq_daily_prices_stock_id_trade_date"),
        ),
    )
    op.create_index(
        "ix_daily_prices_trade_date",
        "daily_prices",
        ["trade_date"],
        unique=False,
    )

    op.create_table(
        "technical_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scanner_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("signal_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column(
            "matched_values",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["scanner_run_id"],
            ["scanner_runs.id"],
            name=op.f("fk_technical_signals_scanner_run_id_scanner_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["signal_definition_id"],
            ["signal_definitions.id"],
            name=op.f("fk_technical_signals_signal_definition_id_signal_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_technical_signals_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technical_signals")),
        sa.UniqueConstraint(
            "scanner_run_id",
            "stock_id",
            "signal_definition_id",
            "signal_date",
            name=op.f(
                "uq_technical_signals_scanner_run_id_stock_id_"
                "signal_definition_id_signal_date"
            ),
        ),
    )
    op.create_index(
        "ix_technical_signals_scanner_run_id_signal_date",
        "technical_signals",
        ["scanner_run_id", "signal_date"],
        unique=False,
    )
    op.create_index(
        "ix_technical_signals_signal_definition_id_signal_date_desc",
        "technical_signals",
        ["signal_definition_id", sa.literal_column("signal_date DESC")],
        unique=False,
    )
    op.create_index(
        "ix_technical_signals_stock_id_signal_date_desc",
        "technical_signals",
        ["stock_id", sa.literal_column("signal_date DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_technical_signals_stock_id_signal_date_desc",
        table_name="technical_signals",
    )
    op.drop_index(
        "ix_technical_signals_signal_definition_id_signal_date_desc",
        table_name="technical_signals",
    )
    op.drop_index(
        "ix_technical_signals_scanner_run_id_signal_date",
        table_name="technical_signals",
    )
    op.drop_table("technical_signals")

    op.drop_index("ix_daily_prices_trade_date", table_name="daily_prices")
    op.drop_table("daily_prices")

    op.drop_index(
        "ix_scanner_runs_started_at_desc",
        table_name="scanner_runs",
    )
    op.drop_index(
        "ix_scanner_runs_data_date_status",
        table_name="scanner_runs",
    )
    op.drop_table("scanner_runs")

    op.drop_table("signal_definitions")

    op.drop_index("ix_stocks_name", table_name="stocks")
    op.drop_table("stocks")
