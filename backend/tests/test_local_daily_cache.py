from datetime import date

from backend.app.services.local_daily_cache import (
    LOCAL_CACHE_SOURCE,
    LocalDailyCache,
)


def test_local_daily_cache_lists_searches_and_loads_prices(tmp_path) -> None:
    cache_dir = tmp_path / "daily_qfq"
    price_dir = cache_dir / "prices" / "上交所主板"
    price_dir.mkdir(parents=True)
    (cache_dir / "stocks_manifest.csv").write_text(
        "\n".join(
            [
                "code,full_code,market,name,list_date,category,should_fetch",
                "600000,sh.600000,sh,浦发银行,1999-11-10,上交所主板,true",
                "510050,sh.510050,sh,华夏上证50ETF,2005-02-23,ETF/基金,false",
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
                    "902245952.4400,1,baostock,d,2,上交所主板,浦发银行"
                ),
                (
                    "2026-06-15,sh.600000,9.68,9.72,9.47,9.53,87932132,"
                    "842270433.5200,1,baostock,d,2,上交所主板,浦发银行"
                ),
            ]
        ),
        encoding="utf-8",
    )

    cache = LocalDailyCache(cache_dir)
    stocks, total = cache.list_stocks(
        query="浦发",
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
    assert prices[0].close == 9.53
    assert prices[0].source == LOCAL_CACHE_SOURCE
