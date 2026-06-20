from datetime import date

from scripts.cache_baostock_daily import (
    BaoStockDailyClient,
    Security,
    cache_row_key,
    classify_security,
    default_output_dir,
    load_daily_rows_with_retries,
    load_kline_rows_with_retries,
    next_fetch_start,
    normalize_frequency,
    select_securities,
)


def test_classifies_confirmed_stock_prefixes() -> None:
    assert classify_security("600000", "sh") == ("上交所主板", True)
    assert classify_security("688001", "sh") == ("上交所科创板", True)
    assert classify_security("000001", "sz") == ("深交所主板", True)
    assert classify_security("300001", "sz") == ("深交所创业板", True)


def test_ignores_explicitly_unsupported_prefixes() -> None:
    assert classify_security("920001", "bj") == ("忽略-北交所", False)
    assert classify_security("900901", "sh") == ("忽略-沪市B股", False)
    assert classify_security("200001", "sz") == ("忽略-深市B股", False)


def test_classifies_remaining_codes_as_etf_fund() -> None:
    assert classify_security("510050", "sh") == ("ETF/基金", False)
    assert classify_security("159915", "sz") == ("ETF/基金", False)


def test_normalizes_30m_frequency_and_output_directory() -> None:
    assert normalize_frequency("30m") == "30"
    assert normalize_frequency("30") == "30"
    assert (
        str(default_output_dir("30", "2"))
        .replace("\\", "/")
        .endswith("data/cache/baostock/30m_qfq")
    )


def test_minute_cache_key_keeps_multiple_bars_on_one_date() -> None:
    first_key = cache_row_key(
        {"date": "2026-06-12", "time": "20260612100000000"},
        "30",
    )
    second_key = cache_row_key(
        {"date": "2026-06-12", "time": "20260612103000000"},
        "30",
    )

    assert first_key != second_key


def test_next_fetch_start_respects_listing_date_and_cache() -> None:
    base_start = date(2016, 1, 1)
    listed_on = date(2018, 3, 2)

    assert next_fetch_start(
        base_start=base_start,
        listed_on=listed_on,
        cached_through=None,
        force=False,
    ) == date(2018, 3, 2)
    assert next_fetch_start(
        base_start=base_start,
        listed_on=listed_on,
        cached_through=date(2020, 1, 8),
        force=False,
    ) == date(2020, 1, 9)
    assert next_fetch_start(
        base_start=base_start,
        listed_on=listed_on,
        cached_from=date(2020, 1, 8),
        cached_through=date(2020, 1, 10),
        force=False,
    ) == date(2018, 3, 2)
    assert next_fetch_start(
        base_start=base_start,
        listed_on=listed_on,
        cached_through=date(2020, 1, 8),
        force=True,
    ) == date(2018, 3, 2)


def test_selects_only_fetchable_stock_categories_by_default() -> None:
    securities = [
        Security(
            code="600000",
            full_code="sh.600000",
            market="sh",
            name="浦发银行",
            list_date=date(1999, 11, 10),
            category="上交所主板",
            should_fetch=True,
        ),
        Security(
            code="510050",
            full_code="sh.510050",
            market="sh",
            name="华夏上证50ETF",
            list_date=date(2005, 2, 23),
            category="ETF/基金",
            should_fetch=False,
        ),
    ]

    assert [
        item.code
        for item in select_securities(
            securities,
            codes=set(),
            include_etf_fund=False,
            limit=None,
        )
    ] == ["600000"]
    assert [
        item.code
        for item in select_securities(
            securities,
            codes=set(),
            include_etf_fund=True,
            limit=None,
        )
    ] == ["600000", "510050"]


class FakeResponse:
    def __init__(
        self,
        *,
        error_code: str = "0",
        error_msg: str = "",
        fields: list[str] | None = None,
        rows: list[list[str]] | None = None,
    ) -> None:
        self.error_code = error_code
        self.error_msg = error_msg
        self.fields = fields or [
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "tradestatus",
        ]
        self._rows = rows or []
        self._index = -1

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._index]


class FlakyBaoStockModule:
    def __init__(self) -> None:
        self.login_count = 0
        self.logout_count = 0
        self.request_count = 0

    def login(self) -> FakeResponse:
        self.login_count += 1
        return FakeResponse()

    def logout(self) -> FakeResponse:
        self.logout_count += 1
        return FakeResponse()

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
        self.request_count += 1
        if self.request_count == 1:
            return FakeResponse(
                error_code="10054",
                error_msg="network receive error",
            )
        return FakeResponse(
            rows=[
                [
                    "2026-06-12",
                    code,
                    "9.50",
                    "9.71",
                    "9.40",
                    "9.67",
                    "94049852",
                    "902245952.4400",
                    "1",
                ]
            ]
        )


class MinuteBaoStockModule:
    def __init__(self) -> None:
        self.requested_fields = ""
        self.requested_frequency = ""
        self.requested_adjustflag = ""

    def login(self) -> FakeResponse:
        return FakeResponse()

    def logout(self) -> FakeResponse:
        return FakeResponse()

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
        self.requested_fields = fields
        self.requested_frequency = frequency
        self.requested_adjustflag = adjustflag
        return FakeResponse(
            fields=[
                "date",
                "time",
                "code",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "adjustflag",
            ],
            rows=[
                [
                    "2026-06-12",
                    "20260612100000000",
                    code,
                    "9.50",
                    "9.71",
                    "9.40",
                    "9.67",
                    "94049852",
                    "902245952.4400",
                    "2",
                ]
            ],
        )


def test_loads_30m_rows_with_minute_fields() -> None:
    module = MinuteBaoStockModule()
    security = Security(
        code="600000",
        full_code="sh.600000",
        market="sh",
        name="Synthetic Bank",
        list_date=date(1999, 11, 10),
        category="SSE Main",
        should_fetch=True,
    )

    with BaoStockDailyClient(module) as client:
        rows = load_kline_rows_with_retries(
            client,
            security,
            start_date=date(2026, 6, 12),
            end_date=date(2026, 6, 12),
            frequency="30",
            adjustflag="2",
            retries=0,
            retry_base_sleep_seconds=0,
        )

    assert module.requested_fields == (
        "date,time,code,open,high,low,close,volume,amount,adjustflag"
    )
    assert module.requested_frequency == "30"
    assert module.requested_adjustflag == "2"
    assert rows[0]["time"] == "20260612100000000"
    assert rows[0]["frequency"] == "30"
    assert rows[0]["adjustflag"] == "2"


def test_retries_and_reconnects_after_baostock_receive_error() -> None:
    module = FlakyBaoStockModule()
    security = Security(
        code="600000",
        full_code="sh.600000",
        market="sh",
        name="浦发银行",
        list_date=date(1999, 11, 10),
        category="上交所主板",
        should_fetch=True,
    )

    with BaoStockDailyClient(module) as client:
        rows = load_daily_rows_with_retries(
            client,
            security,
            start_date=date(2026, 6, 12),
            end_date=date(2026, 6, 12),
            retries=1,
            retry_base_sleep_seconds=0,
        )

    assert module.request_count == 2
    assert module.login_count == 2
    assert module.logout_count == 2
    assert rows[0]["code"] == "sh.600000"
    assert rows[0]["adjustflag"] == "2"
