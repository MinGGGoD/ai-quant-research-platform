import asyncio
import os
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ai import GeneratedResearchNote, ResearchNoteContext
from backend.app.api.routes import (
    configured_market_data_history_provider,
    configured_research_note_generator,
)
from backend.app.database import (
    DailyPrice,
    DailyPriceSyncRange,
    ResearchNote,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)
from backend.app.database.session import get_db_session
from backend.app.main import app
from scanner.ingestion import DailyPriceRecord, MarketDataBatch, StockRecord

RUN_ID = UUID("c62d4313-9199-4f27-a8f7-c64284e78792")
SIGNAL_ID = UUID("9a694b1c-255b-4708-b47b-f0e35b2ad1f0")
DATA_DATE = date(2026, 6, 12)
SAFE_NOTE_CONTENT = """Observations
Stored prices changed across the available period.
Technical patterns
A deterministic volume pattern was recorded.
Risk factors
The available history is limited.
Limitations
This note uses only stored research context."""


class FakeResearchNoteGenerator:
    def generate(self, context: ResearchNoteContext) -> GeneratedResearchNote:
        assert context.stock.symbol == "600519"
        return GeneratedResearchNote(
            content=SAFE_NOTE_CONTENT,
            model_name="synthetic-model",
            provider_metadata={"request_id": "synthetic-provider-request"},
        )


class UnsafeResearchNoteGenerator:
    def generate(self, context: ResearchNoteContext) -> GeneratedResearchNote:
        del context
        return GeneratedResearchNote(
            content="The reader should buy this stock.",
            model_name="synthetic-model",
        )


class FakeMarketDataHistoryProvider:
    source = "asharehub_raw"
    supported_exchanges = frozenset({"SSE", "SZSE", "BSE"})

    def __init__(self) -> None:
        self.calendar_calls: list[tuple[str, date, date]] = []
        self.price_calls: list[tuple[str, date, date]] = []

    def reset(self) -> None:
        self.calendar_calls.clear()
        self.price_calls.clear()

    def load_open_dates(
        self,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> tuple[date, ...]:
        self.calendar_calls.append((exchange, start_date, end_date))
        return (date(2026, 6, 10), date(2026, 6, 11), date(2026, 6, 12))

    def load_prices(
        self,
        stock: StockRecord,
        start_date: date,
        end_date: date,
    ) -> MarketDataBatch:
        self.price_calls.append((stock.symbol, start_date, end_date))
        return MarketDataBatch(
            stocks=(stock,),
            daily_prices=(
                DailyPriceRecord(
                    symbol=stock.symbol,
                    exchange=stock.exchange,
                    trade_date=date(2026, 6, 10),
                    open=Decimal("9.8000"),
                    high=Decimal("10.1000"),
                    low=Decimal("9.7000"),
                    close=Decimal("10.0000"),
                    volume=900,
                    amount=Decimal("9000.0000"),
                    source="asharehub_raw",
                ),
            ),
        )


fake_market_data_provider = FakeMarketDataHistoryProvider()


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


@pytest.fixture(scope="module")
def api_session_factory(
    migrated_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE research_notes, technical_signals, "
                "daily_price_sync_ranges, daily_prices, scanner_runs, "
                "signal_definitions, stocks "
                "RESTART IDENTITY CASCADE"
            )
        )

    with session_factory() as session:
        active_stock = Stock(
            symbol="600519",
            exchange="SSE",
            name="Synthetic Research Stock",
            list_date=date(2001, 8, 27),
            status="active",
        )
        active_stock.daily_prices.extend(
            [
                DailyPrice(
                    trade_date=date(2026, 6, 11),
                    open=Decimal("10.0000"),
                    high=Decimal("10.5000"),
                    low=Decimal("9.8000"),
                    close=Decimal("10.3000"),
                    volume=1000,
                    amount=Decimal("10250.0000"),
                    source="synthetic_api_fixture",
                ),
                DailyPrice(
                    trade_date=DATA_DATE,
                    open=Decimal("10.3000"),
                    high=Decimal("11.0000"),
                    low=Decimal("10.2000"),
                    close=Decimal("10.9000"),
                    volume=2500,
                    amount=Decimal("26750.0000"),
                    source="synthetic_api_fixture",
                ),
            ]
        )
        session.add_all(
            [
                active_stock,
                Stock(
                    symbol="000001",
                    exchange="SZSE",
                    name="Synthetic Delisted Stock",
                    status="delisted",
                ),
            ]
        )
        session.flush()

        scanner_run = ScannerRun(
            id=RUN_ID,
            status="completed",
            data_date=DATA_DATE,
            universe_name="api_test_universe",
            parameters={
                "signals": [{"code": "volume_spike", "version": 1}],
            },
            started_at=datetime(2026, 6, 13, 2, 0, tzinfo=UTC),
            finished_at=datetime(2026, 6, 13, 2, 1, tzinfo=UTC),
            total_stocks=1,
            processed_stocks=1,
            matched_stocks=1,
        )
        definition = SignalDefinition(
            code="volume_spike",
            version=1,
            name="Volume Spike",
            description="Synthetic deterministic research signal.",
            parameters={"lookback_sessions": 20, "multiplier": 2.0},
        )
        session.add_all([scanner_run, definition])
        session.flush()
        session.add(
            TechnicalSignal(
                id=SIGNAL_ID,
                scanner_run_id=RUN_ID,
                stock_id=active_stock.id,
                signal_definition_id=definition.id,
                signal_date=DATA_DATE,
                matched_values={
                    "current_volume": 2500,
                    "average_previous_volume": 1000.0,
                    "volume_ratio": 2.5,
                },
                explanation=(
                    "Technical volume signal detected for research inspection."
                ),
            )
        )
        session.commit()

    def override_get_db_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[configured_research_note_generator] = (
        FakeResearchNoteGenerator
    )
    app.dependency_overrides[configured_market_data_history_provider] = lambda: (
        fake_market_data_provider
    )
    try:
        yield session_factory
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(configured_research_note_generator, None)
        app.dependency_overrides.pop(configured_market_data_history_provider, None)


async def api_request(
    method: str,
    path: str,
    params: Mapping[str, str | int] | None = None,
    json: Mapping[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(method, path, params=params, json=json)


def request(
    path: str,
    params: Mapping[str, str | int] | None = None,
) -> httpx.Response:
    return asyncio.run(api_request("GET", path, params=params))


def post(
    path: str,
    *,
    params: Mapping[str, str | int] | None = None,
    json: Mapping[str, object] | None = None,
) -> httpx.Response:
    return asyncio.run(api_request("POST", path, params=params, json=json))


@pytest.mark.postgres
def test_readiness_and_stock_endpoints(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    readiness = request("/api/v1/health")
    stocks = request("/api/v1/stocks", params={"query": "Research", "limit": 1})
    stock_aliases = request("/stocks", params={"limit": 1})
    stock = request("/api/v1/stocks/600519.SH")
    alias = request("/stocks/600519", params={"exchange": "SSE"})

    assert readiness.status_code == 200
    assert readiness.json()["database"] == "available"
    assert stocks.status_code == 200
    assert stocks.json()["pagination"] == {"limit": 1, "offset": 0, "total": 1}
    assert stocks.json()["items"][0]["symbol"] == "600519"
    assert stock_aliases.status_code == 200
    assert stock.status_code == 200
    assert stock.json()["exchange"] == "SSE"
    assert alias.status_code == 200
    assert alias.json()["id"] == stock.json()["id"]


@pytest.mark.postgres
def test_stock_prices_are_chronological_and_filterable(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    response = request(
        "/api/v1/stocks/600519/prices",
        params={
            "exchange": "SSE",
            "from_date": "2026-06-11",
            "to_date": "2026-06-12",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frequency"] == "daily"
    assert payload["price_adjustment"] == "source_defined"
    assert [item["trade_date"] for item in payload["items"]] == [
        "2026-06-11",
        "2026-06-12",
    ]
    assert payload["items"][1]["close"] == 10.9
    assert payload["items"][1]["source"] == "synthetic_api_fixture"


@pytest.mark.postgres
def test_stock_chan_analysis_endpoint(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    response = request(
        "/api/v1/stocks/600519/chan-analysis",
        params={
            "exchange": "SSE",
            "from_date": "2026-06-11",
            "to_date": "2026-06-12",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frequency"] == "daily"
    assert payload["algorithm"]["code"] == "vespa314_chan_py"
    assert payload["price_bar_count"] == 2
    assert payload["fractals"] == []
    assert payload["observations"] == []


@pytest.mark.postgres
def test_scanner_run_endpoints(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    listing = request(
        "/api/v1/scanner-runs",
        params={"status": "completed", "limit": 10},
    )
    detail = request(f"/api/v1/scanner-runs/{RUN_ID}")

    assert listing.status_code == 200
    assert listing.json()["pagination"]["total"] == 1
    assert listing.json()["items"][0]["id"] == str(RUN_ID)
    assert detail.status_code == 200
    assert detail.json()["parameters"]["signals"][0]["code"] == "volume_spike"
    assert detail.json()["summary"]["matched_stocks"] == 1


@pytest.mark.postgres
def test_signal_endpoints_and_pagination(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    signals = request(
        "/api/v1/signals",
        params={
            "scanner_run_id": str(RUN_ID),
            "signal_code": "volume_spike",
            "limit": 1,
        },
    )
    stock_signals = request(
        "/api/v1/stocks/600519/signals",
        params={"exchange": "SSE", "signal_code": "volume_spike"},
    )

    assert signals.status_code == 200
    assert signals.json()["pagination"] == {"limit": 1, "offset": 0, "total": 1}
    assert signals.json()["items"][0]["id"] == str(SIGNAL_ID)
    assert signals.json()["items"][0]["stock"]["symbol"] == "600519"
    assert signals.json()["items"][0]["signal"]["code"] == "volume_spike"
    assert stock_signals.status_code == 200
    assert stock_signals.json()["stock"]["exchange"] == "SSE"
    assert stock_signals.json()["items"][0]["matched_values"]["volume_ratio"] == 2.5


@pytest.mark.postgres
def test_api_error_shapes(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    invalid_range = request(
        "/api/v1/stocks/600519/prices",
        params={
            "exchange": "SSE",
            "from_date": "2026-06-12",
            "to_date": "2026-06-11",
        },
    )
    missing = request("/api/v1/stocks/999999")
    invalid_frequency = request(
        "/api/v1/stocks/600519/prices",
        params={"exchange": "SSE", "frequency": "tick"},
    )
    invalid_page = request("/api/v1/stocks", params={"limit": 0})
    unknown_signal = request(
        "/api/v1/signals",
        params={"signal_code": "not_defined"},
    )

    assert invalid_range.status_code == 400
    assert invalid_range.json()["error"]["code"] == "invalid_date_range"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "stock_not_found"
    assert invalid_frequency.status_code == 400
    assert invalid_frequency.json()["error"]["code"] == "unsupported_price_frequency"
    assert invalid_page.status_code == 422
    assert invalid_page.json()["error"]["code"] == "validation_error"
    assert unknown_signal.status_code == 400
    assert unknown_signal.json()["error"]["code"] == "unsupported_signal_code"
    assert (
        invalid_range.headers["X-Request-ID"]
        == invalid_range.json()["error"]["request_id"]
    )


@pytest.mark.postgres
def test_database_errors_return_service_unavailable(
    api_session_factory: sessionmaker[Session],
) -> None:
    def unavailable_session() -> Iterator[Session]:
        raise SQLAlchemyError("synthetic database outage")
        yield

    def restored_session() -> Iterator[Session]:
        with api_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = unavailable_session
    try:
        response = request("/api/v1/health")
    finally:
        app.dependency_overrides[get_db_session] = restored_session

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


@pytest.mark.postgres
def test_research_note_generation_and_retrieval(
    api_session_factory: sessionmaker[Session],
) -> None:
    created = post(
        "/api/v1/stocks/600519/research-notes",
        params={"exchange": "SSE"},
        json={
            "scanner_run_id": str(RUN_ID),
            "price_window": 20,
            "signal_limit": 10,
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["stock"]["symbol"] == "600519"
    assert payload["content"] == SAFE_NOTE_CONTENT
    assert payload["model_name"] == "synthetic-model"
    assert payload["prompt_version"] == "research-note-v1"
    assert payload["metadata"]["context"]["price_summary"]["record_count"] == 2
    assert (
        payload["metadata"]["context"]["technical_signals"][0]["code"] == "volume_spike"
    )

    listing = request(
        "/api/v1/stocks/600519/research-notes",
        params={"exchange": "SSE"},
    )
    detail = request(f"/api/v1/research-notes/{payload['id']}")

    assert listing.status_code == 200
    assert listing.json()["pagination"]["total"] == 1
    assert listing.json()["items"][0]["id"] == payload["id"]
    assert detail.status_code == 200
    assert detail.json()["scanner_run_id"] == str(RUN_ID)

    with api_session_factory() as session:
        note = session.get(ResearchNote, UUID(payload["id"]))
        assert note is not None
        assert note.source_type == "ai_generated"
        assert note.generation_metadata["generation"]["request_id"] == (
            "synthetic-provider-request"
        )


@pytest.mark.postgres
def test_research_note_rejects_unsafe_output_without_persisting(
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        before = session.query(ResearchNote).count()

    app.dependency_overrides[configured_research_note_generator] = (
        UnsafeResearchNoteGenerator
    )
    try:
        response = post(
            "/api/v1/stocks/600519/research-notes",
            params={"exchange": "SSE"},
            json={},
        )
    finally:
        app.dependency_overrides[configured_research_note_generator] = (
            FakeResearchNoteGenerator
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "unsafe_ai_output"
    with api_session_factory() as session:
        assert session.query(ResearchNote).count() == before


@pytest.mark.postgres
def test_research_note_requires_stored_price_context(
    api_session_factory: sessionmaker[Session],
) -> None:
    del api_session_factory

    response = post(
        "/api/v1/stocks/000001/research-notes",
        params={"exchange": "SZSE"},
        json={},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_research_context"


@pytest.mark.postgres
def test_price_sync_fetches_only_missing_sessions_and_caches_coverage(
    api_session_factory: sessionmaker[Session],
) -> None:
    fake_market_data_provider.reset()

    first = post(
        "/api/v1/stocks/600519/prices/sync",
        params={"exchange": "SSE"},
        json={
            "from_date": "2026-06-10",
            "to_date": "2026-06-12",
        },
    )
    second = post(
        "/api/v1/stocks/600519/prices/sync",
        params={"exchange": "SSE"},
        json={
            "from_date": "2026-06-10",
            "to_date": "2026-06-12",
        },
    )
    app.dependency_overrides[configured_market_data_history_provider] = lambda: None
    try:
        cached_without_provider = post(
            "/api/v1/stocks/600519/prices/sync",
            params={"exchange": "SSE"},
            json={
                "from_date": "2026-06-10",
                "to_date": "2026-06-12",
            },
        )
    finally:
        app.dependency_overrides[configured_market_data_history_provider] = lambda: (
            fake_market_data_provider
        )

    assert first.status_code == 200
    assert first.json()["sync"] == {
        "requested_range": {
            "from_date": "2026-06-10",
            "to_date": "2026-06-12",
        },
        "effective_range": {
            "from_date": "2026-06-10",
            "to_date": "2026-06-12",
        },
        "cache_hit": False,
        "fetched_ranges": [
            {
                "from_date": "2026-06-10",
                "to_date": "2026-06-10",
            }
        ],
        "prices_inserted": 1,
        "prices_updated": 0,
    }
    assert [item["trade_date"] for item in first.json()["items"]] == [
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
    ]
    assert second.status_code == 200
    assert second.json()["sync"]["cache_hit"] is True
    assert second.json()["sync"]["fetched_ranges"] == []
    assert cached_without_provider.status_code == 200
    assert cached_without_provider.json()["sync"]["cache_hit"] is True
    assert fake_market_data_provider.calendar_calls == [
        ("SSE", date(2026, 6, 10), date(2026, 6, 12))
    ]
    assert fake_market_data_provider.price_calls == [
        ("600519", date(2026, 6, 10), date(2026, 6, 10))
    ]

    with api_session_factory() as session:
        coverage = session.scalars(select(DailyPriceSyncRange)).one()
        assert coverage.start_date == date(2026, 6, 10)
        assert coverage.end_date == date(2026, 6, 12)
