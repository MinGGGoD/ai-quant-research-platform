from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Protocol, cast

import baostock as bs  # type: ignore[import-untyped]

from scanner.ingestion.errors import (
    IngestionValidationError,
    MarketDataProviderError,
    ValidationIssue,
)
from scanner.ingestion.types import DailyPriceRecord, MarketDataBatch, StockRecord

BAOSTOCK_SOURCE = "baostock_raw"
CODE_PREFIX_BY_EXCHANGE = {"SSE": "sh", "SZSE": "sz"}
PRICE_FIELDS = "date,code,open,high,low,close,volume,amount,tradestatus"


class BaoStockResponse(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]

    def next(self) -> bool: ...

    def get_row_data(self) -> list[str]: ...


class BaoStockClient(Protocol):
    def login(self) -> BaoStockResponse: ...

    def logout(self) -> BaoStockResponse: ...

    def query_trade_dates(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> BaoStockResponse: ...

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


class BaoStockHistoryClient:
    """Load unadjusted SSE and SZSE daily history without API credentials."""

    source = BAOSTOCK_SOURCE
    supported_exchanges = frozenset({"SSE", "SZSE"})
    _session_lock = Lock()

    def __init__(self, client: BaoStockClient | None = None) -> None:
        self._client = client or cast(BaoStockClient, bs)
        self._logged_in = False
        self._lock_acquired = False

    def load_open_dates(
        self,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> tuple[date, ...]:
        self._validate_request(exchange, start_date, end_date)
        self._ensure_login()
        response = self._client.query_trade_dates(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        rows = self._collect_rows(response, "trade calendar")
        field_indexes = self._field_indexes(
            response,
            ("calendar_date", "is_trading_day"),
            "trade calendar",
        )
        issues: list[ValidationIssue] = []
        sessions: set[date] = set()
        for row_number, row in enumerate(rows, start=1):
            if row[field_indexes["is_trading_day"]] != "1":
                continue
            raw_date = row[field_indexes["calendar_date"]]
            try:
                sessions.add(date.fromisoformat(raw_date))
            except ValueError:
                issues.append(
                    ValidationIssue(
                        code="invalid_date",
                        message="calendar_date must use YYYY-MM-DD format",
                        file="baostock:query_trade_dates",
                        row=row_number,
                        field="calendar_date",
                    )
                )
        if issues:
            raise IngestionValidationError(issues)
        return tuple(sorted(sessions))

    def load_prices(
        self,
        stock: StockRecord,
        start_date: date,
        end_date: date,
    ) -> MarketDataBatch:
        self._validate_request(stock.exchange, start_date, end_date)
        self._ensure_login()
        code = f"{CODE_PREFIX_BY_EXCHANGE[stock.exchange]}.{stock.symbol}"
        response = self._client.query_history_k_data_plus(
            code,
            PRICE_FIELDS,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            frequency="d",
            adjustflag="3",
        )
        rows = self._collect_rows(response, "daily prices")
        field_indexes = self._field_indexes(
            response,
            (
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "tradestatus",
            ),
            "daily prices",
        )
        issues: list[ValidationIssue] = []
        prices: list[DailyPriceRecord] = []
        for row_number, row in enumerate(rows, start=1):
            if row[field_indexes["tradestatus"]] != "1":
                continue
            issue_count = len(issues)
            trade_date = self._date_value(
                row[field_indexes["date"]],
                row_number,
                issues,
            )
            open_price = self._decimal_value(
                row[field_indexes["open"]],
                "open",
                row_number,
                issues,
            )
            high = self._decimal_value(
                row[field_indexes["high"]],
                "high",
                row_number,
                issues,
            )
            low = self._decimal_value(
                row[field_indexes["low"]],
                "low",
                row_number,
                issues,
            )
            close = self._decimal_value(
                row[field_indexes["close"]],
                "close",
                row_number,
                issues,
            )
            volume_decimal = self._decimal_value(
                row[field_indexes["volume"]],
                "volume",
                row_number,
                issues,
            )
            amount = self._decimal_value(
                row[field_indexes["amount"]],
                "amount",
                row_number,
                issues,
                optional=True,
            )
            values = (open_price, high, low, close, volume_decimal, amount)
            if any(value is not None and value < 0 for value in values):
                issues.append(
                    ValidationIssue(
                        code="negative_value",
                        message="Daily price values cannot be negative",
                        file="baostock:query_history_k_data_plus",
                        row=row_number,
                    )
                )
            if all(value is not None for value in (open_price, high, low, close)):
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                if high < max(open_price, low, close) or low > min(
                    open_price,
                    high,
                    close,
                ):
                    issues.append(
                        ValidationIssue(
                            code="invalid_ohlc",
                            message="BaoStock returned inconsistent OHLC values",
                            file="baostock:query_history_k_data_plus",
                            row=row_number,
                        )
                    )
            volume: int | None = None
            if volume_decimal is not None:
                if volume_decimal != volume_decimal.to_integral_value():
                    issues.append(
                        ValidationIssue(
                            code="invalid_volume",
                            message="volume must be a whole number of shares",
                            file="baostock:query_history_k_data_plus",
                            row=row_number,
                            field="volume",
                        )
                    )
                else:
                    volume = int(volume_decimal)

            if len(issues) == issue_count:
                assert trade_date is not None
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                assert volume is not None
                prices.append(
                    DailyPriceRecord(
                        symbol=stock.symbol,
                        exchange=stock.exchange,
                        trade_date=trade_date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                        amount=amount,
                        source=BAOSTOCK_SOURCE,
                    )
                )
        if issues:
            raise IngestionValidationError(issues)
        return MarketDataBatch(stocks=(stock,), daily_prices=tuple(prices))

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
                raise MarketDataProviderError(
                    "BaoStock login failed: " + response.error_msg
                )
            self._logged_in = True
        except Exception:
            self._session_lock.release()
            self._lock_acquired = False
            raise

    def _validate_request(
        self,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> None:
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date")
        if exchange not in self.supported_exchanges:
            raise MarketDataProviderError(
                f"BaoStock does not support exchange {exchange}"
            )

    @staticmethod
    def _collect_rows(
        response: BaoStockResponse,
        operation: str,
    ) -> list[list[str]]:
        if response.error_code != "0":
            raise MarketDataProviderError(
                f"BaoStock {operation} request failed: {response.error_msg}"
            )
        rows: list[list[str]] = []
        while response.next():
            rows.append(response.get_row_data())
        if response.error_code != "0":
            raise MarketDataProviderError(
                f"BaoStock {operation} response failed: {response.error_msg}"
            )
        return rows

    @staticmethod
    def _field_indexes(
        response: BaoStockResponse,
        required_fields: tuple[str, ...],
        operation: str,
    ) -> dict[str, int]:
        indexes = {field: index for index, field in enumerate(response.fields)}
        missing = [field for field in required_fields if field not in indexes]
        if missing:
            raise MarketDataProviderError(
                f"BaoStock {operation} omitted fields: {', '.join(missing)}"
            )
        return indexes

    @staticmethod
    def _date_value(
        value: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        try:
            return date.fromisoformat(value)
        except ValueError:
            issues.append(
                ValidationIssue(
                    code="invalid_date",
                    message="date must use YYYY-MM-DD format",
                    file="baostock:query_history_k_data_plus",
                    row=row,
                    field="date",
                )
            )
            return None

    @staticmethod
    def _decimal_value(
        value: str,
        field: str,
        row: int,
        issues: list[ValidationIssue],
        *,
        optional: bool = False,
    ) -> Decimal | None:
        if optional and not value:
            return None
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError):
            parsed = None
        if parsed is None or not parsed.is_finite():
            issues.append(
                ValidationIssue(
                    code="invalid_number",
                    message=f"{field} must be a finite decimal number",
                    file="baostock:query_history_k_data_plus",
                    row=row,
                    field=field,
                )
            )
            return None
        return parsed
