from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.app.database import (
    Base,
    DailyPrice,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)

EXPECTED_TABLES = {
    "stocks",
    "daily_prices",
    "scanner_runs",
    "signal_definitions",
    "technical_signals",
}


def test_metadata_contains_phase_two_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_documented_unique_constraints_are_present() -> None:
    stocks = Base.metadata.tables["stocks"]
    daily_prices = Base.metadata.tables["daily_prices"]
    signal_definitions = Base.metadata.tables["signal_definitions"]
    technical_signals = Base.metadata.tables["technical_signals"]

    unique_columns = {
        tuple(constraint.columns.keys())
        for table in (stocks, daily_prices, signal_definitions, technical_signals)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("exchange", "symbol") in unique_columns
    assert ("stock_id", "trade_date") in unique_columns
    assert ("code", "version") in unique_columns
    assert (
        "scanner_run_id",
        "stock_id",
        "signal_definition_id",
        "signal_date",
    ) in unique_columns


def test_daily_price_and_scanner_constraints_are_present() -> None:
    daily_prices = Base.metadata.tables["daily_prices"]
    scanner_runs = Base.metadata.tables["scanner_runs"]

    daily_checks = {
        constraint.name
        for constraint in daily_prices.constraints
        if isinstance(constraint, CheckConstraint)
    }
    scanner_checks = {
        constraint.name
        for constraint in scanner_runs.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert daily_checks == {
        "ck_daily_prices_non_negative_prices",
        "ck_daily_prices_non_negative_volume",
        "ck_daily_prices_valid_high",
        "ck_daily_prices_valid_low",
    }
    assert scanner_checks == {
        "ck_scanner_runs_non_negative_counts",
        "ck_scanner_runs_valid_finished_at",
        "ck_scanner_runs_valid_status",
    }


def test_models_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl


def test_model_relationships_can_be_constructed() -> None:
    stock = Stock(
        symbol="600519",
        exchange="SSE",
        name="Example Stock",
        status="active",
    )
    price = DailyPrice(
        trade_date=date(2026, 6, 12),
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
        data_date=date(2026, 6, 12),
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
        signal_date=date(2026, 6, 12),
        matched_values={"ma_5": 10.2, "ma_20": 10.1},
        explanation="Synthetic research signal.",
    )

    stock.daily_prices.append(price)
    stock.technical_signals.append(signal)
    scanner_run.technical_signals.append(signal)
    definition.technical_signals.append(signal)

    assert price.stock is stock
    assert signal.stock is stock
    assert signal.scanner_run is scanner_run
    assert signal.signal_definition is definition
