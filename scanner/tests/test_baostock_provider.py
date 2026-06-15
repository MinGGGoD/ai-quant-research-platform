from datetime import date
from decimal import Decimal

import pytest

from scanner.ingestion import (
    BaoStockHistoryClient,
    MarketDataProviderError,
    StockRecord,
)


class FakeResponse:
    def __init__(
        self,
        fields: list[str] | None = None,
        rows: list[list[str]] | None = None,
        *,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.error_code = error_code
        self.error_msg = error_msg
        self.fields = fields or []
        self._rows = rows or []
        self._index = -1

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._index]


class FakeBaoStockClient:
    def __init__(self, *, login_error: bool = False) -> None:
        self.login_error = login_error
        self.login_calls = 0
        self.logout_calls = 0
        self.price_requests: list[tuple[str, str, str, str]] = []

    def login(self) -> FakeResponse:
        self.login_calls += 1
        if self.login_error:
            return FakeResponse(error_code="1", error_msg="synthetic login failure")
        return FakeResponse()

    def logout(self) -> FakeResponse:
        self.logout_calls += 1
        return FakeResponse()

    def query_trade_dates(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> FakeResponse:
        assert start_date == "2026-06-11"
        assert end_date == "2026-06-14"
        return FakeResponse(
            fields=["calendar_date", "is_trading_day"],
            rows=[
                ["2026-06-11", "1"],
                ["2026-06-12", "1"],
                ["2026-06-13", "0"],
                ["2026-06-14", "0"],
            ],
        )

    def query_history_k_data_plus(
        self,
        code: str,
        fields: str,
        *,
        start_date: str,
        end_date: str,
        frequency: str,
        adjustflag: str,
    ) -> FakeResponse:
        self.price_requests.append((code, start_date, end_date, adjustflag))
        assert frequency == "d"
        return FakeResponse(
            fields=fields.split(","),
            rows=[
                [
                    "2026-06-11",
                    code,
                    "10.00",
                    "10.50",
                    "9.80",
                    "10.30",
                    "1000",
                    "10250.00",
                    "1",
                ],
                [
                    "2026-06-12",
                    code,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "0",
                ],
            ],
        )


def stock_record() -> StockRecord:
    return StockRecord(
        symbol="601138",
        exchange="SSE",
        name="Industrial Fulian",
        list_date=date(2018, 6, 8),
        delist_date=None,
        status="active",
    )


def test_loads_trade_dates_and_unadjusted_daily_prices() -> None:
    fake_client = FakeBaoStockClient()
    provider = BaoStockHistoryClient(fake_client)
    try:
        sessions = provider.load_open_dates(
            "SSE",
            date(2026, 6, 11),
            date(2026, 6, 14),
        )
        batch = provider.load_prices(
            stock_record(),
            date(2026, 6, 11),
            date(2026, 6, 12),
        )
    finally:
        provider.close()

    assert sessions == (date(2026, 6, 11), date(2026, 6, 12))
    assert fake_client.login_calls == 1
    assert fake_client.logout_calls == 1
    assert fake_client.price_requests == [
        ("sh.601138", "2026-06-11", "2026-06-12", "3")
    ]
    assert batch.stocks == (stock_record(),)
    assert len(batch.daily_prices) == 1
    assert batch.daily_prices[0].volume == 1000
    assert batch.daily_prices[0].amount == Decimal("10250.00")
    assert batch.daily_prices[0].source == "baostock_raw"


def test_reports_login_failure_and_releases_session_lock() -> None:
    failing = BaoStockHistoryClient(FakeBaoStockClient(login_error=True))

    with pytest.raises(MarketDataProviderError, match="login failed"):
        failing.load_open_dates(
            "SSE",
            date(2026, 6, 11),
            date(2026, 6, 14),
        )
    failing.close()

    succeeding = BaoStockHistoryClient(FakeBaoStockClient())
    try:
        assert succeeding.load_open_dates(
            "SSE",
            date(2026, 6, 11),
            date(2026, 6, 14),
        )
    finally:
        succeeding.close()
