from datetime import date
from decimal import Decimal

import httpx
import pytest

from scanner.ingestion import (
    AShareHubMarketDataProvider,
    IngestionValidationError,
    MarketDataProviderError,
)


def stock_payload() -> dict[str, object]:
    return {
        "ts_code": "000001.SZ",
        "symbol": "000001",
        "name": "Ping An Bank",
        "exchange": "SZSE",
        "list_status": "L",
        "list_date": "1991-04-03",
        "delist_date": None,
    }


def price_payload() -> dict[str, object]:
    return {
        "ts_code": "000001.SZ",
        "trade_date": "2026-06-12",
        "open": "11.1000",
        "high": "11.3000",
        "low": "11.0000",
        "close": "11.2000",
        "vol": "2032355.4600",
        "amount": "2263042.9306",
    }


def make_client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(
        base_url="https://asharehub.com",
        transport=handler,
        headers={"X-API-Key": "test-key"},
    )


def test_loads_and_normalizes_asharehub_daily_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "test-key"
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[stock_payload()])
        if request.url.path == "/v1/market/daily":
            return httpx.Response(200, json=[price_payload()])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    provider = AShareHubMarketDataProvider(
        api_key="test-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        ts_codes=("000001.sz",),
        client=make_client(httpx.MockTransport(handler)),
    )

    batch = provider.load()

    assert len(batch.stocks) == 1
    assert batch.stocks[0].key == ("SZSE", "000001")
    assert batch.daily_prices[0].volume == 203_235_546
    assert batch.daily_prices[0].amount == Decimal("2263042930.6000")
    assert batch.daily_prices[0].source == "asharehub_raw"


def test_supports_beijing_exchange_codes() -> None:
    bj_stock = {
        **stock_payload(),
        "ts_code": "920001.BJ",
        "symbol": "920001",
        "exchange": "BSE",
    }
    bj_price = {**price_payload(), "ts_code": "920001.BJ"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[bj_stock])
        return httpx.Response(200, json=[bj_price])

    batch = AShareHubMarketDataProvider(
        api_key="test-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        ts_codes=("920001.BJ",),
        client=make_client(httpx.MockTransport(handler)),
    ).load()

    assert batch.stocks[0].exchange == "BSE"
    assert batch.daily_prices[0].exchange == "BSE"


def test_skips_prices_without_stock_metadata_with_warning() -> None:
    missing_price = {**price_payload(), "ts_code": "301669.SZ"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[stock_payload()])
        return httpx.Response(200, json=[price_payload(), missing_price])

    batch = AShareHubMarketDataProvider(
        api_key="test-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        client=make_client(httpx.MockTransport(handler)),
    ).load()

    assert len(batch.daily_prices) == 1
    assert batch.warnings[0].code == "unknown_stock"
    assert batch.warnings[0].stock_key == "SZSE:301669"


def test_paginates_until_a_short_page() -> None:
    offsets: list[tuple[str, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append((request.url.path, offset))
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[stock_payload()] if offset == 0 else [])
        if request.url.path == "/v1/market/daily":
            return httpx.Response(200, json=[price_payload()] if offset == 0 else [])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    provider = AShareHubMarketDataProvider(
        api_key="test-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        page_size=1,
        max_requests=4,
        client=make_client(httpx.MockTransport(handler)),
    )

    batch = provider.load()

    assert len(batch.daily_prices) == 1
    assert offsets == [
        ("/v1/reference/stocks", 0),
        ("/v1/reference/stocks", 1),
        ("/v1/market/daily", 0),
        ("/v1/market/daily", 1),
    ]


def test_request_budget_prevents_partial_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[stock_payload()])
        return httpx.Response(200, json=[price_payload()])

    provider = AShareHubMarketDataProvider(
        api_key="do-not-leak-this-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        page_size=1,
        max_requests=1,
        client=make_client(httpx.MockTransport(handler)),
    )

    with pytest.raises(MarketDataProviderError) as error:
        provider.load()

    assert "request budget exhausted" in str(error.value)
    assert "do-not-leak-this-key" not in str(error.value)


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "rejected the API key"),
        (429, "daily request limit"),
        (500, "HTTP 500"),
    ],
)
def test_reports_remote_errors_without_exposing_key(
    status_code: int,
    message: str,
) -> None:
    provider = AShareHubMarketDataProvider(
        api_key="do-not-leak-this-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        client=make_client(
            httpx.MockTransport(
                lambda request: httpx.Response(status_code, request=request)
            )
        ),
    )

    with pytest.raises(MarketDataProviderError) as error:
        provider.load()

    assert message in str(error.value)
    assert "do-not-leak-this-key" not in str(error.value)


def test_rejects_invalid_provider_values() -> None:
    invalid_price = {**price_payload(), "high": "10.0000", "vol": "1.001"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/reference/stocks":
            return httpx.Response(200, json=[stock_payload()])
        return httpx.Response(200, json=[invalid_price])

    provider = AShareHubMarketDataProvider(
        api_key="test-key",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        client=make_client(httpx.MockTransport(handler)),
    )

    with pytest.raises(IngestionValidationError) as error:
        provider.load()

    assert {"invalid_ohlc", "invalid_volume_unit"} <= {
        issue.code for issue in error.value.issues
    }


def test_rejects_invalid_dates_codes_and_limits() -> None:
    with pytest.raises(ValueError, match="start_date"):
        AShareHubMarketDataProvider(
            api_key="test-key",
            start_date=date(2026, 6, 13),
            end_date=date(2026, 6, 12),
        )
    with pytest.raises(ValueError, match="ts_codes"):
        AShareHubMarketDataProvider(
            api_key="test-key",
            start_date=date(2026, 6, 12),
            end_date=date(2026, 6, 12),
            ts_codes=("600000.SSE",),
        )
    with pytest.raises(ValueError, match="page_size"):
        AShareHubMarketDataProvider(
            api_key="test-key",
            start_date=date(2026, 6, 12),
            end_date=date(2026, 6, 12),
            page_size=5001,
        )
