import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import DailyPrice, Stock
from scanner.ingestion import (
    CsvMarketDataProvider,
    IngestionPersistenceError,
    ingest_market_data,
)

SAMPLE_DIR = Path(__file__).parents[2] / "data" / "sample"


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


@pytest.fixture(autouse=True)
def clean_market_data(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE technical_signals, daily_prices, scanner_runs, "
                "signal_definitions, stocks RESTART IDENTITY CASCADE"
            )
        )


@pytest.mark.postgres
def test_sample_import_is_idempotent(migrated_engine: Engine) -> None:
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )
    provider = CsvMarketDataProvider(
        SAMPLE_DIR / "stocks.csv",
        SAMPLE_DIR / "daily_prices.csv",
        "synthetic_csv_v1",
    )

    first_summary = ingest_market_data(
        provider,
        session_factory=session_factory,
    )
    second_summary = ingest_market_data(
        provider,
        session_factory=session_factory,
    )

    assert first_summary.stocks_inserted == 2
    assert first_summary.prices_inserted == 4
    assert second_summary.stocks_updated == 2
    assert second_summary.prices_updated == 4

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Stock)) == 2
        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 4
        assert {
            source for source in session.scalars(select(DailyPrice.source)).all()
        } == {"synthetic_csv_v1"}


@pytest.mark.postgres
def test_persistence_error_rolls_back_whole_batch(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    stocks_file = tmp_path / "stocks.csv"
    stocks_file.write_text(
        (
            "symbol,exchange,name,list_date,delist_date,status\n"
            "609901,SSE,Synthetic Alpha,2020-01-02,,active\n"
        ),
        encoding="utf-8",
    )
    prices_file = tmp_path / "prices.csv"
    prices_file.write_text(
        (
            "symbol,exchange,trade_date,open,high,low,close,volume,amount\n"
            "309999,SZSE,2026-06-12,10,11,9,10,100,1000\n"
        ),
        encoding="utf-8",
    )
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )

    with pytest.raises(IngestionPersistenceError):
        ingest_market_data(
            CsvMarketDataProvider(
                stocks_file,
                prices_file,
                "test_source",
            ),
            session_factory=session_factory,
        )

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Stock)) == 0
        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 0
