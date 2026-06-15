import os
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import (
    DailyPrice,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)
from scanner.scanning import ScanExecutionError, run_scan

DATA_DATE = date(2026, 6, 12)


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
def clean_scanner_data(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE technical_signals, daily_prices, scanner_runs, "
                "signal_definitions, stocks RESTART IDENTITY CASCADE"
            )
        )


def add_price_history(
    session: Session,
    stock: Stock,
    *,
    complete: bool,
) -> None:
    closes = [10] * 15 + [9] * 5 + [20] if complete else [10]
    start_date = DATA_DATE - timedelta(days=len(closes) - 1)
    for index, close in enumerate(closes):
        close_value = Decimal(close)
        stock.daily_prices.append(
            DailyPrice(
                trade_date=start_date + timedelta(days=index),
                open=close_value,
                high=close_value + Decimal("0.5"),
                low=max(close_value - Decimal("0.5"), Decimal()),
                close=close_value,
                volume=250 if index == len(closes) - 1 else 100,
                amount=None,
                source="synthetic_scanner_fixture",
            )
        )
    session.add(stock)


@pytest.mark.postgres
def test_scan_persists_run_definitions_signals_and_warnings(
    migrated_engine: Engine,
) -> None:
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )
    with session_factory() as session:
        add_price_history(
            session,
            Stock(
                symbol="600001",
                exchange="SSE",
                name="Synthetic Complete",
                status="active",
            ),
            complete=True,
        )
        add_price_history(
            session,
            Stock(
                symbol="000002",
                exchange="SZSE",
                name="Synthetic Short History",
                status="active",
            ),
            complete=False,
        )
        session.commit()

    first = run_scan(DATA_DATE, session_factory=session_factory)
    second = run_scan(DATA_DATE, session_factory=session_factory)

    assert first.status == "completed_with_warnings"
    assert first.total_stocks == 2
    assert first.processed_stocks == 1
    assert first.matched_stocks == 1
    assert first.detected_signals == 3
    assert first.warning_count == 3
    assert first.signal_counts == {
        "moving_average_cross": 1,
        "recent_breakout": 1,
        "volume_spike": 1,
    }
    assert second.detected_signals == 3

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ScannerRun)) == 2
        assert session.scalar(select(func.count()).select_from(SignalDefinition)) == 3
        assert session.scalar(select(func.count()).select_from(TechnicalSignal)) == 6
        stored_run = session.get(ScannerRun, first.run_id)
        assert stored_run is not None
        assert stored_run.finished_at is not None
        assert stored_run.error_count == 0

        explanations = session.scalars(
            select(TechnicalSignal.explanation).where(
                TechnicalSignal.scanner_run_id == first.run_id
            )
        ).all()
        assert all("research" in explanation for explanation in explanations)
        assert all(
            "buy" not in explanation.lower() and "sell" not in explanation.lower()
            for explanation in explanations
        )


@pytest.mark.postgres
def test_selected_stock_scan_and_failure_lifecycle(
    migrated_engine: Engine,
) -> None:
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )
    with session_factory() as session:
        add_price_history(
            session,
            Stock(
                symbol="600001",
                exchange="SSE",
                name="Synthetic Complete",
                status="active",
            ),
            complete=True,
        )
        session.commit()

    summary = run_scan(
        DATA_DATE,
        stock_keys=(("SSE", "600001"),),
        signal_codes=("recent_breakout",),
        session_factory=session_factory,
    )

    assert summary.status == "completed"
    assert summary.universe_name == "selected_stocks"
    assert summary.detected_signals == 1

    with pytest.raises(ScanExecutionError) as error:
        run_scan(
            DATA_DATE,
            stock_keys=(("SZSE", "999999"),),
            session_factory=session_factory,
        )

    with session_factory() as session:
        failed_run = session.get(ScannerRun, error.value.run_id)
        assert failed_run is not None
        assert failed_run.status == "failed"
        assert failed_run.finished_at is not None
        assert failed_run.error_count == 1
        assert "Selected stocks were not found" in (failed_run.error_message or "")
        assert (
            session.scalar(
                select(func.count())
                .select_from(TechnicalSignal)
                .where(TechnicalSignal.scanner_run_id == failed_run.id)
            )
            == 0
        )
