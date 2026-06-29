from datetime import date, datetime

from backend.app.services.local_daily_cache import (
    LOCAL_CACHE_DERIVED_60M_SOURCE,
    LOCAL_CACHE_SOURCE,
    LocalDailyCache,
)
from backend.app.services.local_daily_cache_sync import (
    LocalDailyCacheSynchronizer,
)


def daily_cache_row(trade_date: str, close: str) -> dict[str, str]:
    return {
        "date": trade_date,
        "code": "sh.600000",
        "open": "9.50",
        "high": "9.80",
        "low": "9.40",
        "close": close,
        "volume": "1000",
        "amount": "9500.0000",
        "tradestatus": "1",
        "source": "baostock",
        "frequency": "d",
        "adjustflag": "2",
        "category": "SSE Main Board",
        "name": "Shanghai Bank",
    }


class FakeDailyClient:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.calls: list[tuple[date, date]] = []
        self.closed = False

    def load_daily_rows(
        self,
        stock,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, str]]:
        del stock
        self.calls.append((start_date, end_date))
        return self.rows

    def close(self) -> None:
        self.closed = True


def test_local_daily_cache_lists_searches_and_loads_prices(tmp_path) -> None:
    cache_dir = tmp_path / "daily_qfq"
    category = "SSE Main Board"
    price_dir = cache_dir / "prices" / category
    intraday_price_dir = tmp_path / "30m_qfq" / "prices" / category
    price_dir.mkdir(parents=True)
    intraday_price_dir.mkdir(parents=True)
    (cache_dir / "stocks_manifest.csv").write_text(
        "\n".join(
            [
                "code,full_code,market,name,list_date,category,should_fetch",
                "600000,sh.600000,sh,Shanghai Bank,1999-11-10,SSE Main Board,true",
                "510050,sh.510050,sh,ETF Fund,2005-02-23,ETF/Fund,false",
            ]
        ),
        encoding="utf-8",
    )
    (price_dir / "sh_600000.csv").write_text(
        "\n".join(
            [
                (
                    "date,code,open,high,low,close,volume,amount,tradestatus,"
                    "source,frequency,adjustflag,category,name"
                ),
                (
                    "2026-06-12,sh.600000,9.50,9.71,9.40,9.67,94049852,"
                    "902245952.4400,1,baostock,d,2,SSE Main Board,Shanghai Bank"
                ),
                (
                    "2026-06-15,sh.600000,9.68,9.72,9.47,9.53,87932132,"
                    "842270433.5200,1,baostock,d,2,SSE Main Board,Shanghai Bank"
                ),
            ]
        ),
        encoding="utf-8",
    )
    (intraday_price_dir / "sh_600000.csv").write_text(
        "\n".join(
            [
                (
                    "date,time,code,open,high,low,close,volume,amount,"
                    "adjustflag,source,frequency,category,name"
                ),
                (
                    "2026-06-15,20260615100000000,sh.600000,9.50,9.60,"
                    "9.40,9.55,100,955.0000,2,baostock,30,"
                    "SSE Main Board,Shanghai Bank"
                ),
                (
                    "2026-06-15,20260615103000000,sh.600000,9.55,9.70,"
                    "9.52,9.65,200,1930.0000,2,baostock,30,"
                    "SSE Main Board,Shanghai Bank"
                ),
                (
                    "2026-06-15,20260615110000000,sh.600000,9.65,9.80,"
                    "9.62,9.75,300,2925.0000,2,baostock,30,"
                    "SSE Main Board,Shanghai Bank"
                ),
            ]
        ),
        encoding="utf-8",
    )

    cache = LocalDailyCache(cache_dir)
    stocks, total = cache.list_stocks(
        query="Shanghai",
        exchange="SSE",
        status="active",
        limit=10,
        offset=0,
    )

    assert total == 1
    assert stocks[0].symbol == "600000"
    assert stocks[0].exchange == "SSE"
    assert stocks[0].id < 0

    prices = cache.list_prices(
        stocks[0],
        from_date=date(2026, 6, 15),
        to_date=date(2026, 6, 15),
        limit=1000,
    )

    assert len(prices) == 1
    assert prices[0].trade_date == date(2026, 6, 15)
    assert prices[0].timestamp is None
    assert prices[0].close == 9.53
    assert prices[0].source == LOCAL_CACHE_SOURCE

    intraday_prices = cache.list_prices(
        stocks[0],
        from_date=date(2026, 6, 15),
        to_date=date(2026, 6, 15),
        limit=1000,
        frequency="30m",
    )

    assert len(intraday_prices) == 3
    assert intraday_prices[0].timestamp == datetime(2026, 6, 15, 10, 0)
    assert intraday_prices[0].close == 9.55
    assert intraday_prices[0].source == LOCAL_CACHE_SOURCE

    hourly_prices = cache.list_prices(
        stocks[0],
        from_date=date(2026, 6, 15),
        to_date=date(2026, 6, 15),
        limit=1000,
        frequency="60m",
    )

    assert len(hourly_prices) == 2
    assert hourly_prices[0].timestamp == datetime(2026, 6, 15, 10, 30)
    assert hourly_prices[0].open == 9.50
    assert hourly_prices[0].high == 9.70
    assert hourly_prices[0].low == 9.40
    assert hourly_prices[0].close == 9.65
    assert hourly_prices[0].volume == 300
    assert hourly_prices[0].amount == 2885.0
    assert hourly_prices[0].source == LOCAL_CACHE_DERIVED_60M_SOURCE


def test_local_daily_cache_synchronizer_extends_cache_tail(tmp_path) -> None:
    cache_dir = tmp_path / "daily_qfq"
    category = "SSE Main Board"
    price_dir = cache_dir / "prices" / category
    price_dir.mkdir(parents=True)
    (cache_dir / "stocks_manifest.csv").write_text(
        "\n".join(
            [
                "code,full_code,market,name,list_date,category,should_fetch",
                "600000,sh.600000,sh,Shanghai Bank,1999-11-10,SSE Main Board,true",
            ]
        ),
        encoding="utf-8",
    )
    (price_dir / "sh_600000.csv").write_text(
        "\n".join(
            [
                (
                    "date,code,open,high,low,close,volume,amount,tradestatus,"
                    "source,frequency,adjustflag,category,name"
                ),
                (
                    "2026-06-12,sh.600000,9.50,9.71,9.40,9.67,94049852,"
                    "902245952.4400,1,baostock,d,2,SSE Main Board,Shanghai Bank"
                ),
                (
                    "2026-06-15,sh.600000,9.68,9.72,9.47,9.53,87932132,"
                    "842270433.5200,1,baostock,d,2,SSE Main Board,Shanghai Bank"
                ),
            ]
        ),
        encoding="utf-8",
    )

    cache = LocalDailyCache(cache_dir)
    stock = cache.find_stocks(symbol="600000", exchange="SSE")[0]
    client = FakeDailyClient(
        [
            daily_cache_row("2026-06-16", "9.61"),
            daily_cache_row("2026-06-18", "9.70"),
        ]
    )
    synchronizer = LocalDailyCacheSynchronizer(lambda: client)

    result = synchronizer.sync_daily_prices(
        cache,
        stock,
        from_date=date(2026, 6, 12),
        to_date=date(2026, 6, 18),
        today=date(2026, 6, 18),
    )
    cached_result = synchronizer.sync_daily_prices(
        cache,
        stock,
        from_date=date(2026, 6, 12),
        to_date=date(2026, 6, 18),
        today=date(2026, 6, 18),
    )
    prices = cache.list_prices(
        stock,
        from_date=date(2026, 6, 12),
        to_date=date(2026, 6, 18),
        limit=1000,
    )

    assert result.cache_hit is False
    assert result.fetched_ranges[0].start_date == date(2026, 6, 16)
    assert result.fetched_ranges[0].end_date == date(2026, 6, 18)
    assert result.prices_inserted == 2
    assert result.prices_updated == 0
    assert cached_result.cache_hit is True
    assert client.calls == [(date(2026, 6, 16), date(2026, 6, 18))]
    assert client.closed is True
    assert [price.trade_date for price in prices] == [
        date(2026, 6, 12),
        date(2026, 6, 15),
        date(2026, 6, 16),
        date(2026, 6, 18),
    ]
    assert prices[-1].close == 9.70
