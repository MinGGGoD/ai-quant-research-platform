import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database import (
    DailyPrice,
    DocumentChunk,
    KnowledgeDocument,
    ResearchNote,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)

EXPECTED_TABLES = {
    "alembic_version",
    "stocks",
    "daily_prices",
    "document_chunks",
    "knowledge_documents",
    "scanner_runs",
    "research_notes",
    "signal_definitions",
    "technical_signals",
}


@pytest.fixture(scope="module")
def migrated_engine() -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    parsed_url = make_url(database_url)
    if parsed_url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg")
    if parsed_url.database is None or not parsed_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a database ending in _test")

    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.mark.postgres
def test_migration_upgrade_and_downgrade_on_postgresql(
    migrated_engine: Engine,
) -> None:
    assert set(inspect(migrated_engine).get_table_names()) == EXPECTED_TABLES


@pytest.mark.postgres
def test_model_persistence_unique_constraints_and_rollback(
    migrated_engine: Engine,
) -> None:
    signal_date = date(2026, 6, 12)

    with Session(migrated_engine) as session:
        stock = Stock(
            symbol="600519",
            exchange="SSE",
            name="Synthetic Test Stock",
            status="active",
        )
        price = DailyPrice(
            trade_date=signal_date,
            open=Decimal("10.0000"),
            high=Decimal("10.5000"),
            low=Decimal("9.8000"),
            close=Decimal("10.3000"),
            volume=1000,
            amount=Decimal("10250.0000"),
            source="synthetic_fixture",
        )
        scanner_run = ScannerRun(
            status="completed",
            data_date=signal_date,
            universe_name="test_universe",
            parameters={},
            started_at=datetime(2026, 6, 13, tzinfo=UTC),
        )
        definition = SignalDefinition(
            code="ma_cross_up",
            version=1,
            name="Moving Average Upward Cross",
            description="Synthetic rule definition.",
            parameters={"short_window": 5, "long_window": 20},
        )
        signal = TechnicalSignal(
            signal_date=signal_date,
            matched_values={"ma_5": 10.2, "ma_20": 10.1},
            explanation="Synthetic research signal.",
        )
        note = ResearchNote(
            title="Synthetic research observations",
            content="Neutral observations from deterministic fixtures.",
            source_type="ai_generated",
            model_name="synthetic-model",
            prompt_version="research-note-v1",
            generation_metadata={"fixture": True},
        )
        document = KnowledgeDocument(
            document_type="research_note",
            title="Synthetic indexed note",
            source_name="note.txt",
            mime_type="text/plain",
            content_sha256="c" * 64,
            byte_size=64,
            character_count=64,
            embedding_model="local-hash-v1",
            embedding_dimensions=256,
            source_metadata={"fixture": True},
        )
        document.chunks.append(
            DocumentChunk(
                chunk_index=0,
                content="Synthetic indexed research observations.",
                content_sha256="d" * 64,
                start_character=0,
                end_character=40,
                character_count=40,
                embedding=[0.0] * 255 + [1.0],
                chunk_metadata={},
            )
        )

        stock.daily_prices.append(price)
        stock.technical_signals.append(signal)
        scanner_run.technical_signals.append(signal)
        definition.technical_signals.append(signal)
        stock.research_notes.append(note)
        scanner_run.research_notes.append(note)
        stock.knowledge_documents.append(document)
        session.add_all([stock, scanner_run, definition])
        session.commit()

        assert session.scalar(select(func.count()).select_from(Stock)) == 1
        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 1
        assert session.scalar(select(func.count()).select_from(TechnicalSignal)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchNote)) == 1
        assert session.scalar(select(func.count()).select_from(KnowledgeDocument)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentChunk)) == 1

        session.add(
            DailyPrice(
                stock_id=stock.id,
                trade_date=signal_date,
                open=Decimal("10.0000"),
                high=Decimal("10.5000"),
                low=Decimal("9.8000"),
                close=Decimal("10.3000"),
                volume=1000,
                source="duplicate_fixture",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 1
