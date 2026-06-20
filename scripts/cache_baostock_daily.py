from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

DEFAULT_STOCKS_FILE = Path(r"E:\projects\chan.py\Dataset\stocks.json")
DEFAULT_OUTPUT_ROOT = Path("data/cache/baostock")
DEFAULT_OUTPUT_DIR = Path("data/cache/baostock/daily_qfq")
DEFAULT_START_DATE = date(2016, 1, 1)
DEFAULT_END_DATE = date(2026, 6, 19)
BAOSTOCK_FREQUENCY = "d"
BAOSTOCK_FRONT_ADJUST_FLAG = "2"
DEFAULT_RETRIES = 5
DEFAULT_RETRY_BASE_SLEEP_SECONDS = 2.0

MINUTE_FREQUENCIES = frozenset({"5", "15", "30", "60"})
SUPPORTED_FREQUENCIES = frozenset({"d", "w", "m", *MINUTE_FREQUENCIES})

PRICE_FIELDS = (
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "tradestatus",
)
MINUTE_PRICE_FIELDS = (
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
)
PERIOD_PRICE_FIELDS = (
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adjustflag",
    "turn",
    "pctChg",
)
METADATA_COLUMNS = (
    "source",
    "frequency",
    "adjustflag",
    "category",
    "name",
)
CACHE_COLUMNS = (
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "tradestatus",
    "source",
    "frequency",
    "adjustflag",
    "category",
    "name",
)
FETCH_CATEGORIES = frozenset(
    {
        "上交所主板",
        "上交所科创板",
        "深交所主板",
        "深交所创业板",
    }
)


class BaoStockResponse(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]

    def next(self) -> bool: ...

    def get_row_data(self) -> list[str]: ...


class BaoStockModule(Protocol):
    def login(self) -> BaoStockResponse: ...

    def logout(self) -> BaoStockResponse: ...

    def query_history_k_data_plus(
        self,
        code: str,
        fields: str,
        *,
        start_date: str,
        end_date: str,
        frequency: str,
        adjustflag: str,
    ) -> BaoStockResponse: ...


@dataclass(frozen=True, slots=True)
class Security:
    code: str
    full_code: str
    market: str
    name: str
    list_date: date
    category: str
    should_fetch: bool

    @property
    def baostock_code(self) -> str:
        return self.full_code

    @property
    def cache_file_stem(self) -> str:
        return self.full_code.replace(".", "_")


@dataclass(frozen=True, slots=True)
class CacheStatus:
    code: str
    full_code: str
    name: str
    category: str
    status: str
    start_date: str | None
    end_date: str | None
    rows_written: int
    cache_file: str | None
    message: str | None = None


def classify_security(code: str, market: str) -> tuple[str, bool]:
    normalized_code = code.strip()
    normalized_market = market.strip().lower()

    if normalized_code.startswith("920"):
        return "忽略-北交所", False
    if normalized_code.startswith("900"):
        return "忽略-沪市B股", False
    if normalized_code.startswith("200"):
        return "忽略-深市B股", False
    if normalized_code.startswith("60") and normalized_market == "sh":
        return "上交所主板", True
    if normalized_code.startswith("68") and normalized_market == "sh":
        return "上交所科创板", True
    if normalized_code.startswith("00") and normalized_market == "sz":
        return "深交所主板", True
    if normalized_code.startswith("30") and normalized_market == "sz":
        return "深交所创业板", True
    return "ETF/基金", False


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def normalize_frequency(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "1d": "d",
        "daily": "d",
        "day": "d",
        "1w": "w",
        "weekly": "w",
        "week": "w",
        "1m": "m",
        "monthly": "m",
        "month": "m",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_FREQUENCIES:
        raise argparse.ArgumentTypeError(
            "frequency must be one of d, w, m, 5, 15, 30, or 60"
        )
    return normalized


def frequency_label(frequency: str) -> str:
    labels = {
        "d": "daily",
        "w": "weekly",
        "m": "monthly",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "60": "60m",
    }
    return labels[frequency]


def adjustment_label(adjustflag: str) -> str:
    labels = {"1": "hfq", "2": "qfq", "3": "raw"}
    return labels.get(adjustflag, f"adjustflag_{adjustflag}")


def default_output_dir(frequency: str, adjustflag: str) -> Path:
    return DEFAULT_OUTPUT_ROOT / (
        f"{frequency_label(frequency)}_{adjustment_label(adjustflag)}"
    )


def price_fields_for_frequency(frequency: str) -> tuple[str, ...]:
    if frequency in MINUTE_FREQUENCIES:
        return MINUTE_PRICE_FIELDS
    if frequency in {"w", "m"}:
        return PERIOD_PRICE_FIELDS
    return PRICE_FIELDS


def cache_columns_for_frequency(frequency: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((*price_fields_for_frequency(frequency), *METADATA_COLUMNS))
    )


def cache_row_key(row: dict[str, str], frequency: str) -> str:
    if frequency in MINUTE_FREQUENCIES:
        return f"{row['date']} {row.get('time', '')}"
    return row["date"]


def load_securities(stocks_file: Path) -> list[Security]:
    payload = json.loads(stocks_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("stocks.json must contain a JSON array")

    securities: list[Security] = []
    seen_full_codes: set[str] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"stocks.json row {index} must be an object")

        code = str(item.get("code", "")).strip()
        market = str(item.get("market", "")).strip().lower()
        full_code = str(item.get("full_code", "")).strip().lower()
        name = str(item.get("name", "")).strip()
        list_date_raw = str(item.get("list_date", "")).strip()

        if not code or not market or not full_code or not name or not list_date_raw:
            raise ValueError(f"stocks.json row {index} has missing required fields")
        if full_code in seen_full_codes:
            raise ValueError(f"Duplicate full_code in stocks.json: {full_code}")
        if full_code != f"{market}.{code}":
            raise ValueError(
                f"stocks.json row {index} full_code does not match market/code"
            )

        category, should_fetch = classify_security(code, market)
        securities.append(
            Security(
                code=code,
                full_code=full_code,
                market=market,
                name=name,
                list_date=parse_iso_date(list_date_raw),
                category=category,
                should_fetch=should_fetch,
            )
        )
        seen_full_codes.add(full_code)

    return securities


def select_securities(
    securities: list[Security],
    *,
    codes: set[str],
    include_etf_fund: bool,
    limit: int | None,
) -> list[Security]:
    selected = [
        security
        for security in securities
        if (
            security.should_fetch
            or (include_etf_fund and security.category == "ETF/基金")
        )
        and (not codes or security.code in codes or security.full_code in codes)
    ]
    if limit is not None:
        return selected[:limit]
    return selected


def cache_file_for(output_dir: Path, security: Security) -> Path:
    return output_dir / "prices" / security.category / f"{security.cache_file_stem}.csv"


def read_cached_rows(
    cache_file: Path,
    *,
    frequency: str = BAOSTOCK_FREQUENCY,
) -> dict[str, dict[str, str]]:
    if not cache_file.exists():
        return {}
    cache_columns = cache_columns_for_frequency(frequency)
    with cache_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {
            cache_row_key(row, frequency): {
                column: row.get(column, "") for column in cache_columns
            }
            for row in reader
            if row.get("date")
        }


def write_cached_rows(
    cache_file: Path,
    rows_by_date: dict[str, dict[str, str]],
    *,
    frequency: str = BAOSTOCK_FREQUENCY,
) -> int:
    cache_columns = cache_columns_for_frequency(frequency)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = [rows_by_date[key] for key in sorted(rows_by_date)]
    with cache_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=cache_columns)
        writer.writeheader()
        writer.writerows(ordered_rows)
    return len(ordered_rows)


def latest_cached_date(rows_by_date: dict[str, dict[str, str]]) -> date | None:
    if not rows_by_date:
        return None
    return max(parse_iso_date(row["date"]) for row in rows_by_date.values())


def earliest_cached_date(rows_by_date: dict[str, dict[str, str]]) -> date | None:
    if not rows_by_date:
        return None
    return min(parse_iso_date(row["date"]) for row in rows_by_date.values())


def next_fetch_start(
    *,
    base_start: date,
    listed_on: date,
    cached_from: date | None = None,
    cached_through: date | None,
    force: bool,
) -> date:
    start = max(base_start, listed_on)
    if force or cached_through is None:
        return start
    if cached_from is not None and cached_from > start:
        return start
    return max(start, cached_through + timedelta(days=1))


class BaoStockDailyClient:
    def __init__(self, module: BaoStockModule | None = None) -> None:
        if module is None:
            import baostock as bs  # type: ignore[import-untyped]

            module = bs
        self._module = module
        self._logged_in = False

    def __enter__(self) -> BaoStockDailyClient:
        self.login()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.logout()

    def login(self) -> None:
        if self._logged_in:
            return
        response = self._module.login()
        if response.error_code != "0":
            raise RuntimeError(f"BaoStock login failed: {response.error_msg}")
        self._logged_in = True

    def logout(self) -> None:
        if self._logged_in:
            self._module.logout()
            self._logged_in = False

    def reconnect(self) -> None:
        self.logout()
        self.login()

    def load_daily_rows(
        self,
        security: Security,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, str]]:
        return self.load_kline_rows(
            security,
            start_date=start_date,
            end_date=end_date,
            frequency=BAOSTOCK_FREQUENCY,
            adjustflag=BAOSTOCK_FRONT_ADJUST_FLAG,
        )

    def load_kline_rows(
        self,
        security: Security,
        *,
        start_date: date,
        end_date: date,
        frequency: str,
        adjustflag: str,
    ) -> list[dict[str, str]]:
        price_fields = price_fields_for_frequency(frequency)
        cache_columns = cache_columns_for_frequency(frequency)
        response = self._module.query_history_k_data_plus(
            security.baostock_code,
            ",".join(price_fields),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            frequency=frequency,
            adjustflag=adjustflag,
        )
        if response.error_code != "0":
            raise RuntimeError(
                f"BaoStock request failed for {security.full_code}: "
                f"{response.error_msg}"
            )

        indexes = {field: index for index, field in enumerate(response.fields)}
        missing = [field for field in price_fields if field not in indexes]
        if missing:
            raise RuntimeError(
                f"BaoStock response omitted fields for {security.full_code}: "
                + ", ".join(missing)
            )

        rows: list[dict[str, str]] = []
        while response.next():
            raw = response.get_row_data()
            tradestatus = (
                raw[indexes["tradestatus"]] if "tradestatus" in indexes else ""
            )
            if tradestatus and tradestatus != "1":
                continue
            row = {field: raw[indexes[field]] for field in price_fields}
            row.update(
                {
                    "source": "baostock",
                    "frequency": frequency,
                    "adjustflag": row.get("adjustflag") or adjustflag,
                    "category": security.category,
                    "name": security.name,
                }
            )
            rows.append({column: row.get(column, "") for column in cache_columns})

        if response.error_code != "0":
            raise RuntimeError(
                f"BaoStock response failed for {security.full_code}: "
                f"{response.error_msg}"
            )
        return rows


def load_daily_rows_with_retries(
    client: BaoStockDailyClient,
    security: Security,
    *,
    start_date: date,
    end_date: date,
    retries: int,
    retry_base_sleep_seconds: float,
) -> list[dict[str, str]]:
    return load_kline_rows_with_retries(
        client,
        security,
        start_date=start_date,
        end_date=end_date,
        frequency=BAOSTOCK_FREQUENCY,
        adjustflag=BAOSTOCK_FRONT_ADJUST_FLAG,
        retries=retries,
        retry_base_sleep_seconds=retry_base_sleep_seconds,
    )


def load_kline_rows_with_retries(
    client: BaoStockDailyClient,
    security: Security,
    *,
    start_date: date,
    end_date: date,
    frequency: str,
    adjustflag: str,
    retries: int,
    retry_base_sleep_seconds: float,
) -> list[dict[str, str]]:
    attempts = retries + 1
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.load_kline_rows(
                security,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjustflag,
            )
        except Exception as error:
            last_error = error
            if attempt >= attempts:
                break
            sleep_seconds = retry_base_sleep_seconds * (2 ** (attempt - 1))
            print(
                f"{security.full_code} request failed on attempt "
                f"{attempt}/{attempts}: {error}; reconnecting and retrying "
                f"in {sleep_seconds:.1f}s",
                flush=True,
            )
            time.sleep(sleep_seconds)
            client.reconnect()

    assert last_error is not None
    raise last_error


def write_manifest(output_dir: Path, securities: list[Security]) -> Path:
    manifest_file = output_dir / "stocks_manifest.csv"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with manifest_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=(
                "code",
                "full_code",
                "market",
                "name",
                "list_date",
                "category",
                "should_fetch",
            ),
        )
        writer.writeheader()
        for security in securities:
            writer.writerow(
                {
                    "code": security.code,
                    "full_code": security.full_code,
                    "market": security.market,
                    "name": security.name,
                    "list_date": security.list_date.isoformat(),
                    "category": security.category,
                    "should_fetch": str(security.should_fetch).lower(),
                }
            )
    return manifest_file


def write_summary(output_dir: Path, statuses: list[CacheStatus]) -> Path:
    summary_file = output_dir / "last_run_summary.json"
    summary = {
        "total": len(statuses),
        "completed": sum(1 for item in statuses if item.status == "completed"),
        "skipped": sum(1 for item in statuses if item.status == "skipped"),
        "failed": sum(1 for item in statuses if item.status == "failed"),
        "items": [asdict(item) for item in statuses],
    }
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_file


def cache_security(
    client: BaoStockDailyClient,
    security: Security,
    *,
    output_dir: Path,
    start_date: date,
    end_date: date,
    frequency: str,
    adjustflag: str,
    force: bool,
    retries: int,
    retry_base_sleep_seconds: float,
) -> CacheStatus:
    cache_file = cache_file_for(output_dir, security)
    existing_rows = {} if force else read_cached_rows(cache_file, frequency=frequency)
    cached_from = earliest_cached_date(existing_rows)
    cached_through = latest_cached_date(existing_rows)
    fetch_start = next_fetch_start(
        base_start=start_date,
        listed_on=security.list_date,
        cached_from=cached_from,
        cached_through=cached_through,
        force=force,
    )
    if fetch_start > end_date:
        return CacheStatus(
            code=security.code,
            full_code=security.full_code,
            name=security.name,
            category=security.category,
            status="skipped",
            start_date=None,
            end_date=None,
            rows_written=len(existing_rows),
            cache_file=str(cache_file),
            message="cache already covers requested range",
        )

    rows_by_date = existing_rows
    fetched_rows = load_kline_rows_with_retries(
        client,
        security,
        start_date=fetch_start,
        end_date=end_date,
        frequency=frequency,
        adjustflag=adjustflag,
        retries=retries,
        retry_base_sleep_seconds=retry_base_sleep_seconds,
    )
    for row in fetched_rows:
        rows_by_date[cache_row_key(row, frequency)] = row
    rows_written = write_cached_rows(cache_file, rows_by_date, frequency=frequency)

    return CacheStatus(
        code=security.code,
        full_code=security.full_code,
        name=security.name,
        category=security.category,
        status="completed",
        start_date=fetch_start.isoformat(),
        end_date=end_date.isoformat(),
        rows_written=rows_written,
        cache_file=str(cache_file),
        message=f"fetched {len(fetched_rows)} rows",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cache front-adjusted BaoStock K-line CSV files for the "
            "stock universe listed in stocks.json."
        )
    )
    parser.add_argument("--stocks-file", type=Path, default=DEFAULT_STOCKS_FILE)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--start-date", type=parse_iso_date, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=parse_iso_date, default=DEFAULT_END_DATE)
    parser.add_argument(
        "--frequency",
        type=normalize_frequency,
        default=BAOSTOCK_FREQUENCY,
        help=(
            "K-line frequency: d, w, m, 5, 15, 30, or 60. "
            "Aliases like 30m and daily are accepted."
        ),
    )
    parser.add_argument(
        "--adjustflag",
        choices=("1", "2", "3"),
        default=BAOSTOCK_FRONT_ADJUST_FLAG,
        help="BaoStock adjustment flag: 1=post-adjusted, 2=front-adjusted, 3=raw.",
    )
    parser.add_argument(
        "--code",
        action="append",
        default=[],
        help="Limit to one code or full_code. Repeat as needed.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit selected fetchable securities for a small test run.",
    )
    parser.add_argument(
        "--include-etf-fund",
        action="store_true",
        help="Also fetch securities classified as ETF/基金.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite existing per-security cache files from the computed start date."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.5,
        help="Pause between BaoStock requests.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="Retry each BaoStock request this many times after the first failure.",
    )
    parser.add_argument(
        "--retry-base-sleep-seconds",
        type=float,
        default=DEFAULT_RETRY_BASE_SLEEP_SECONDS,
        help="Initial retry pause; each subsequent retry doubles this value.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only classify and report the selected universe; do not call BaoStock.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch on the first per-security fetch error.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output_dir is None:
        args.output_dir = default_output_dir(args.frequency, args.adjustflag)
    if args.start_date > args.end_date:
        print("start-date cannot be later than end-date", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("limit must be positive", file=sys.stderr)
        return 2
    if args.sleep_seconds < 0:
        print("sleep-seconds cannot be negative", file=sys.stderr)
        return 2
    if args.retries < 0:
        print("retries cannot be negative", file=sys.stderr)
        return 2
    if args.retry_base_sleep_seconds < 0:
        print("retry-base-sleep-seconds cannot be negative", file=sys.stderr)
        return 2

    securities = load_securities(args.stocks_file)
    manifest_file = write_manifest(args.output_dir, securities)
    codes = {code.strip().lower() for code in args.code if code.strip()}
    selected = select_securities(
        securities,
        codes=codes,
        include_etf_fund=args.include_etf_fund,
        limit=args.limit,
    )

    category_counts: dict[str, int] = {}
    for security in securities:
        category_counts[security.category] = (
            category_counts.get(security.category, 0) + 1
        )

    print(f"Loaded {len(securities)} securities from {args.stocks_file}")
    print(f"Wrote manifest to {manifest_file}")
    print("Classification counts:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")
    print(f"Frequency: {args.frequency}")
    print(f"Adjustment flag: {args.adjustflag}")
    print(f"Output directory: {args.output_dir}")
    print(f"Selected fetchable securities: {len(selected)}")

    if args.dry_run:
        return 0

    statuses: list[CacheStatus] = []
    with BaoStockDailyClient() as client:
        for index, security in enumerate(selected, start=1):
            try:
                status = cache_security(
                    client,
                    security,
                    output_dir=args.output_dir,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    frequency=args.frequency,
                    adjustflag=args.adjustflag,
                    force=args.force,
                    retries=args.retries,
                    retry_base_sleep_seconds=args.retry_base_sleep_seconds,
                )
            except Exception as error:
                status = CacheStatus(
                    code=security.code,
                    full_code=security.full_code,
                    name=security.name,
                    category=security.category,
                    status="failed",
                    start_date=None,
                    end_date=None,
                    rows_written=0,
                    cache_file=str(cache_file_for(args.output_dir, security)),
                    message=f"{type(error).__name__}: {error}",
                )
                if args.stop_on_error:
                    statuses.append(status)
                    print(f"[{index}/{len(selected)}] {security.full_code} failed")
                    break

            statuses.append(status)
            print(
                f"[{index}/{len(selected)}] {security.full_code} "
                f"{status.status}: {status.message}"
            )
            if args.sleep_seconds:
                time.sleep(args.sleep_seconds)

    summary_file = write_summary(args.output_dir, statuses)
    failed = sum(1 for item in statuses if item.status == "failed")
    print(f"Wrote run summary to {summary_file}")
    print(f"Completed with {failed} failures")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
