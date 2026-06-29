from __future__ import annotations

import csv
import io
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Protocol, cast

import baostock as bs  # type: ignore[import-untyped]

from backend.app.services.local_daily_cache import LocalCachedStock, LocalDailyCache

BAOSTOCK_DAILY_FREQUENCY = "d"
BAOSTOCK_FRONT_ADJUST_FLAG = "2"
BAOSTOCK_SOURCE = "baostock"
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
CACHE_COLUMNS = (
    *PRICE_FIELDS,
    "source",
    "frequency",
    "adjustflag",
    "category",
    "name",
)
SUPPORTED_EXCHANGES = frozenset({"SSE", "SZSE"})
MAX_SYNC_RANGE_DAYS = 1096


class LocalDailyCacheSyncError(RuntimeError):
    """Raised when the local BaoStock file cache cannot be refreshed."""


class BaoStockResponse(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]

    def next(self) -> bool: ...

    def get_row_data(self) -> list[str]: ...


class BaoStockClient(Protocol):
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


class LocalDailyPriceClient(Protocol):
    def load_daily_rows(
        self,
        stock: LocalCachedStock,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, str]]: ...

    def close(self) -> None: ...


class BaoStockQfqDailyClient:
    """Load front-adjusted daily rows in the local CSV cache format."""

    _session_lock = Lock()

    def __init__(self, client: BaoStockClient | None = None) -> None:
        self._client = client or cast(BaoStockClient, bs)
        self._logged_in = False
        self._lock_acquired = False

    def load_daily_rows(
        self,
        stock: LocalCachedStock,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, str]]:
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date")
        if stock.exchange not in SUPPORTED_EXCHANGES:
            raise LocalDailyCacheSyncError(
                f"BaoStock does not support exchange {stock.exchange}."
            )

        self._ensure_login()
        response = self._client.query_history_k_data_plus(
            stock.full_code,
            ",".join(PRICE_FIELDS),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            frequency=BAOSTOCK_DAILY_FREQUENCY,
            adjustflag=BAOSTOCK_FRONT_ADJUST_FLAG,
        )
        rows = self._collect_rows(response)
        indexes = self._field_indexes(response)
        cached_rows: list[dict[str, str]] = []
        for row_number, raw_row in enumerate(rows, start=1):
            if raw_row[indexes["tradestatus"]] != "1":
                continue
            row = {field: raw_row[indexes[field]] for field in PRICE_FIELDS}
            self._validate_row(row, row_number)
            row.update(
                {
                    "source": BAOSTOCK_SOURCE,
                    "frequency": BAOSTOCK_DAILY_FREQUENCY,
                    "adjustflag": BAOSTOCK_FRONT_ADJUST_FLAG,
                    "category": stock.category,
                    "name": stock.name,
                }
            )
            cached_rows.append(
                {column: row.get(column, "") for column in CACHE_COLUMNS}
            )
        return cached_rows

    def close(self) -> None:
        try:
            if self._logged_in:
                with redirect_stdout(io.StringIO()):
                    self._client.logout()
                self._logged_in = False
        finally:
            if self._lock_acquired:
                self._session_lock.release()
                self._lock_acquired = False

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        self._session_lock.acquire()
        self._lock_acquired = True
        try:
            with redirect_stdout(io.StringIO()):
                response = self._client.login()
            if response.error_code != "0":
                raise LocalDailyCacheSyncError(
                    "BaoStock login failed: " + response.error_msg
                )
            self._logged_in = True
        except Exception:
            self._session_lock.release()
            self._lock_acquired = False
            raise

    @staticmethod
    def _collect_rows(response: BaoStockResponse) -> list[list[str]]:
        if response.error_code != "0":
            raise LocalDailyCacheSyncError(
                "BaoStock daily price request failed: " + response.error_msg
            )
        rows: list[list[str]] = []
        while response.next():
            rows.append(response.get_row_data())
        if response.error_code != "0":
            raise LocalDailyCacheSyncError(
                "BaoStock daily price response failed: " + response.error_msg
            )
        return rows

    @staticmethod
    def _field_indexes(response: BaoStockResponse) -> dict[str, int]:
        indexes = {field: index for index, field in enumerate(response.fields)}
        missing = [field for field in PRICE_FIELDS if field not in indexes]
        if missing:
            raise LocalDailyCacheSyncError(
                "BaoStock daily price response omitted fields: " + ", ".join(missing)
            )
        return indexes

    @classmethod
    def _validate_row(cls, row: dict[str, str], row_number: int) -> None:
        try:
            date.fromisoformat(row["date"])
        except ValueError as error:
            raise LocalDailyCacheSyncError(
                f"BaoStock row {row_number} contains an invalid date."
            ) from error

        open_price = cls._decimal_value(row["open"], "open", row_number)
        high = cls._decimal_value(row["high"], "high", row_number)
        low = cls._decimal_value(row["low"], "low", row_number)
        close = cls._decimal_value(row["close"], "close", row_number)
        volume = cls._decimal_value(row["volume"], "volume", row_number)
        if row["amount"]:
            cls._decimal_value(row["amount"], "amount", row_number)
        if volume != volume.to_integral_value():
            raise LocalDailyCacheSyncError(
                f"BaoStock row {row_number} contains a non-integer volume."
            )
        if high < max(open_price, low, close) or low > min(open_price, high, close):
            raise LocalDailyCacheSyncError(
                f"BaoStock row {row_number} contains inconsistent OHLC values."
            )

    @staticmethod
    def _decimal_value(value: str, field: str, row_number: int) -> Decimal:
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as error:
            raise LocalDailyCacheSyncError(
                f"BaoStock row {row_number} contains an invalid {field} value."
            ) from error
        if not parsed.is_finite() or parsed < 0:
            raise LocalDailyCacheSyncError(
                f"BaoStock row {row_number} contains an invalid {field} value."
            )
        return parsed


@dataclass(frozen=True, slots=True)
class LocalCacheDateRange:
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class LocalDailyCacheSyncResult:
    requested_range: LocalCacheDateRange
    effective_range: LocalCacheDateRange | None
    cache_hit: bool
    fetched_ranges: tuple[LocalCacheDateRange, ...]
    prices_inserted: int
    prices_updated: int


class LocalDailyCacheSynchronizer:
    """Refresh local daily CSV caches when the requested end date is newer."""

    _sync_lock = Lock()

    def __init__(
        self,
        client_factory: Callable[[], LocalDailyPriceClient] = BaoStockQfqDailyClient,
    ) -> None:
        self._client_factory = client_factory

    def sync_daily_prices(
        self,
        cache: LocalDailyCache,
        stock: LocalCachedStock,
        *,
        from_date: date,
        to_date: date,
        today: date | None = None,
    ) -> LocalDailyCacheSyncResult:
        if from_date > to_date:
            raise ValueError("from_date must not be later than to_date")
        if (to_date - from_date).days + 1 > MAX_SYNC_RANGE_DAYS:
            raise ValueError(
                f"price history synchronization is limited to {MAX_SYNC_RANGE_DAYS} "
                "days"
            )

        current_date = today or date.today()
        if to_date > current_date:
            raise ValueError("to_date must not be later than today")

        requested_range = LocalCacheDateRange(from_date, to_date)
        effective_start = max(from_date, stock.list_date or from_date)
        effective_end = min(to_date, stock.delist_date or to_date)
        if effective_start > effective_end:
            return LocalDailyCacheSyncResult(
                requested_range=requested_range,
                effective_range=None,
                cache_hit=True,
                fetched_ranges=(),
                prices_inserted=0,
                prices_updated=0,
            )

        effective_range = LocalCacheDateRange(effective_start, effective_end)
        with self._sync_lock:
            cached_from, cached_through = cache.price_date_bounds(stock)
            del cached_from
            if cached_through is not None and cached_through >= effective_end:
                return LocalDailyCacheSyncResult(
                    requested_range=requested_range,
                    effective_range=effective_range,
                    cache_hit=True,
                    fetched_ranges=(),
                    prices_inserted=0,
                    prices_updated=0,
                )

            fetch_start = max(
                effective_start,
                cached_through + timedelta(days=1)
                if cached_through is not None
                else effective_start,
            )
            if fetch_start > effective_end:
                return LocalDailyCacheSyncResult(
                    requested_range=requested_range,
                    effective_range=effective_range,
                    cache_hit=True,
                    fetched_ranges=(),
                    prices_inserted=0,
                    prices_updated=0,
                )

            client = self._client_factory()
            try:
                fetched_rows = client.load_daily_rows(
                    stock,
                    start_date=fetch_start,
                    end_date=effective_end,
                )
            finally:
                client.close()

            cache_file = cache.price_file_for(stock)
            rows_by_date = self._read_cached_rows(cache_file)
            prices_inserted = 0
            prices_updated = 0
            for row in fetched_rows:
                key = row["date"]
                if key in rows_by_date:
                    if rows_by_date[key] != row:
                        prices_updated += 1
                else:
                    prices_inserted += 1
                rows_by_date[key] = row

            if fetched_rows:
                self._write_cached_rows(cache_file, rows_by_date)

        return LocalDailyCacheSyncResult(
            requested_range=requested_range,
            effective_range=effective_range,
            cache_hit=False,
            fetched_ranges=(LocalCacheDateRange(fetch_start, effective_end),),
            prices_inserted=prices_inserted,
            prices_updated=prices_updated,
        )

    @staticmethod
    def _read_cached_rows(cache_file: Path) -> dict[str, dict[str, str]]:
        if not cache_file.exists():
            return {}
        with cache_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return {
                row["date"]: {column: row.get(column, "") for column in CACHE_COLUMNS}
                for row in reader
                if row.get("date")
            }

    @staticmethod
    def _write_cached_rows(
        cache_file: Path,
        rows_by_date: dict[str, dict[str, str]],
    ) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        ordered_rows = [rows_by_date[key] for key in sorted(rows_by_date)]
        with cache_file.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CACHE_COLUMNS)
            writer.writeheader()
            writer.writerows(ordered_rows)
