from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'delisted')",
            name="valid_status",
        ),
        CheckConstraint(
            "delist_date IS NULL OR list_date IS NULL OR delist_date >= list_date",
            name="delist_not_before_list",
        ),
        UniqueConstraint("exchange", "symbol"),
        Index("ix_stocks_name", "name"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    list_date: Mapped[date | None] = mapped_column(Date)
    delist_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    daily_prices: Mapped[list[DailyPrice]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
    technical_signals: Mapped[list[TechnicalSignal]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )


class DailyPrice(TimestampMixin, Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="non_negative_prices",
        ),
        CheckConstraint("volume >= 0", name="non_negative_volume"),
        CheckConstraint(
            "high >= open AND high >= low AND high >= close",
            name="valid_high",
        ),
        CheckConstraint(
            "low <= open AND low <= high AND low <= close",
            name="valid_low",
        ),
        UniqueConstraint("stock_id", "trade_date"),
        Index("ix_daily_prices_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    stock: Mapped[Stock] = relationship(back_populates="daily_prices")


class ScannerRun(TimestampMixin, Base):
    __tablename__ = "scanner_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'pending', 'running', 'completed', "
            "'completed_with_warnings', 'failed'"
            ")",
            name="valid_status",
        ),
        CheckConstraint(
            "total_stocks >= 0 AND processed_stocks >= 0 "
            "AND matched_stocks >= 0 AND warning_count >= 0 "
            "AND error_count >= 0",
            name="non_negative_counts",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="valid_finished_at",
        ),
        Index("ix_scanner_runs_started_at_desc", desc("started_at")),
        Index("ix_scanner_runs_data_date_status", "data_date", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    data_date: Mapped[date] = mapped_column(Date, nullable=False)
    universe_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_stocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    processed_stocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    matched_stocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    technical_signals: Mapped[list[TechnicalSignal]] = relationship(
        back_populates="scanner_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SignalDefinition(TimestampMixin, Base):
    __tablename__ = "signal_definitions"
    __table_args__ = (
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("code", "version"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    technical_signals: Mapped[list[TechnicalSignal]] = relationship(
        back_populates="signal_definition",
        passive_deletes=True,
    )


class TechnicalSignal(TimestampMixin, Base):
    __tablename__ = "technical_signals"
    __table_args__ = (
        UniqueConstraint(
            "scanner_run_id",
            "stock_id",
            "signal_definition_id",
            "signal_date",
        ),
        Index(
            "ix_technical_signals_scanner_run_id_signal_date",
            "scanner_run_id",
            "signal_date",
        ),
        Index(
            "ix_technical_signals_stock_id_signal_date_desc",
            "stock_id",
            desc("signal_date"),
        ),
        Index(
            "ix_technical_signals_signal_definition_id_signal_date_desc",
            "signal_definition_id",
            desc("signal_date"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    scanner_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("scanner_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("signal_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    matched_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    scanner_run: Mapped[ScannerRun] = relationship(back_populates="technical_signals")
    stock: Mapped[Stock] = relationship(back_populates="technical_signals")
    signal_definition: Mapped[SignalDefinition] = relationship(
        back_populates="technical_signals"
    )
