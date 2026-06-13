from datetime import date
from pathlib import Path

import pytest

from scanner.ingestion import CsvMarketDataProvider, IngestionValidationError

SAMPLE_DIR = Path(__file__).parents[2] / "data" / "sample"


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def valid_stocks_csv() -> str:
    return (
        "symbol,exchange,name,list_date,delist_date,status\n"
        "609901,SSE,Synthetic Alpha,2020-01-02,,active\n"
    )


def test_loads_documented_synthetic_sample() -> None:
    provider = CsvMarketDataProvider(
        SAMPLE_DIR / "stocks.csv",
        SAMPLE_DIR / "daily_prices.csv",
        "synthetic_csv_v1",
        expected_through=date(2026, 6, 13),
    )

    batch = provider.load()

    assert len(batch.stocks) == 2
    assert len(batch.daily_prices) == 4
    assert batch.daily_prices[0].source == "synthetic_csv_v1"
    assert batch.warnings == ()


def test_rejects_blank_source_identifier() -> None:
    with pytest.raises(ValueError, match="source must contain"):
        CsvMarketDataProvider(
            SAMPLE_DIR / "stocks.csv",
            SAMPLE_DIR / "daily_prices.csv",
            "   ",
        )


@pytest.mark.parametrize(
    ("price_row", "expected_code"),
    [
        (
            "609901,SSE,,10,11,9,10,100,1000\n",
            "missing_value",
        ),
        (
            "609901,SSE,2026/06/12,10,11,9,10,100,1000\n",
            "invalid_date",
        ),
        (
            "609901,SSE,2026-06-12,10,9,8,10,100,1000\n",
            "invalid_ohlc",
        ),
        (
            "609901,SSE,2026-06-12,10,11,9,10,-1,1000\n",
            "negative_value",
        ),
        (
            "609901,SSE,2026-06-12,10,11,9,10,100,NaN\n",
            "invalid_number",
        ),
    ],
)
def test_rejects_invalid_daily_price_rows(
    tmp_path: Path,
    price_row: str,
    expected_code: str,
) -> None:
    stocks_file = write_csv(tmp_path / "stocks.csv", valid_stocks_csv())
    prices_file = write_csv(
        tmp_path / "prices.csv",
        ("symbol,exchange,trade_date,open,high,low,close,volume,amount\n" + price_row),
    )

    with pytest.raises(IngestionValidationError) as error:
        CsvMarketDataProvider(
            stocks_file,
            prices_file,
            "test_source",
        ).load()

    assert expected_code in {issue.code for issue in error.value.issues}


def test_rejects_missing_columns_and_duplicate_keys(tmp_path: Path) -> None:
    stocks_file = write_csv(tmp_path / "stocks.csv", valid_stocks_csv())
    prices_file = write_csv(
        tmp_path / "prices.csv",
        (
            "symbol,exchange,trade_date,open,high,low,close,volume\n"
            "609901,SSE,2026-06-12,10,11,9,10,100\n"
            "609901,SSE,2026-06-12,10,11,9,10,100\n"
        ),
    )

    with pytest.raises(IngestionValidationError) as error:
        CsvMarketDataProvider(
            stocks_file,
            prices_file,
            "test_source",
        ).load()

    assert "duplicate_price" in {issue.code for issue in error.value.issues}

    missing_column_file = write_csv(
        tmp_path / "missing-column.csv",
        "symbol,exchange,trade_date,open,high,low,volume\n",
    )
    with pytest.raises(IngestionValidationError) as missing_error:
        CsvMarketDataProvider(
            stocks_file,
            missing_column_file,
            "test_source",
        ).load()

    assert "missing_columns" in {issue.code for issue in missing_error.value.issues}


def test_reports_stale_data_without_rejecting_batch(tmp_path: Path) -> None:
    stocks_file = write_csv(tmp_path / "stocks.csv", valid_stocks_csv())
    prices_file = write_csv(
        tmp_path / "prices.csv",
        (
            "symbol,exchange,trade_date,open,high,low,close,volume,amount\n"
            "609901,SSE,2026-05-01,10,11,9,10,100,1000\n"
        ),
    )

    batch = CsvMarketDataProvider(
        stocks_file,
        prices_file,
        "test_source",
        expected_through=date(2026, 6, 12),
        max_staleness_days=7,
    ).load()

    assert [warning.code for warning in batch.warnings] == ["stale_price_data"]
    assert batch.warnings[0].stock_key == "SSE:609901"
