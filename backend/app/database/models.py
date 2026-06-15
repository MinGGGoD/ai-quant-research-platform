from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
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
from rag import EMBEDDING_DIMENSIONS


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
    price_sync_ranges: Mapped[list[DailyPriceSyncRange]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
    technical_signals: Mapped[list[TechnicalSignal]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
    research_notes: Mapped[list[ResearchNote]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
    knowledge_documents: Mapped[list[KnowledgeDocument]] = relationship(
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


class DailyPriceSyncRange(TimestampMixin, Base):
    __tablename__ = "daily_price_sync_ranges"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="valid_date_range"),
        Index(
            "ix_daily_price_sync_ranges_stock_source_dates",
            "stock_id",
            "source",
            "start_date",
            "end_date",
        ),
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
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    stock: Mapped[Stock] = relationship(back_populates="price_sync_ranges")


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
    research_notes: Mapped[list[ResearchNote]] = relationship(
        back_populates="scanner_run",
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


class ResearchNote(TimestampMixin, Base):
    __tablename__ = "research_notes"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('manual', 'ai_generated')",
            name="valid_source_type",
        ),
        CheckConstraint(
            "stock_id IS NOT NULL OR scanner_run_id IS NOT NULL",
            name="has_context_reference",
        ),
        CheckConstraint(
            "source_type <> 'ai_generated' "
            "OR (model_name IS NOT NULL AND prompt_version IS NOT NULL)",
            name="generated_metadata_present",
        ),
        Index(
            "ix_research_notes_stock_id_created_at_desc",
            "stock_id",
            desc("created_at"),
        ),
        Index(
            "ix_research_notes_scanner_run_id_created_at_desc",
            "scanner_run_id",
            desc("created_at"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("stocks.id", ondelete="RESTRICT"),
    )
    scanner_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("scanner_runs.id", ondelete="RESTRICT"),
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    stock: Mapped[Stock | None] = relationship(back_populates="research_notes")
    scanner_run: Mapped[ScannerRun | None] = relationship(
        back_populates="research_notes"
    )


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ("
            "'company_announcement', 'annual_report', 'research_note', 'other'"
            ")",
            name="valid_document_type",
        ),
        CheckConstraint("byte_size >= 0 AND character_count > 0", name="valid_size"),
        CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="valid_page_count",
        ),
        CheckConstraint(
            f"embedding_dimensions = {EMBEDDING_DIMENSIONS}",
            name="supported_embedding_dimensions",
        ),
        UniqueConstraint("content_sha256"),
        Index(
            "ix_knowledge_documents_stock_id_created_at_desc",
            "stock_id",
            desc("created_at"),
        ),
        Index(
            "ix_knowledge_documents_type_created_at_desc",
            "document_type",
            desc("created_at"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("stocks.id", ondelete="RESTRICT"),
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    source_name: Mapped[str] = mapped_column(String(512), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    stock: Mapped[Stock | None] = relationship(back_populates="knowledge_documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="non_negative_chunk_index"),
        CheckConstraint(
            "start_character >= 0 AND end_character > start_character",
            name="valid_character_range",
        ),
        CheckConstraint("character_count > 0", name="positive_character_count"),
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    start_character: Mapped[int] = mapped_column(Integer, nullable=False)
    end_character: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(EMBEDDING_DIMENSIONS),
        nullable=False,
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
