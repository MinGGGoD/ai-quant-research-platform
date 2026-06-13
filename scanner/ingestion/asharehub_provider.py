import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from scanner.ingestion.errors import (
    IngestionValidationError,
    MarketDataProviderError,
    ValidationIssue,
)
from scanner.ingestion.types import (
    DailyPriceRecord,
    IngestionWarning,
    MarketDataBatch,
    StockRecord,
)

ASHAREHUB_BASE_URL = "https://asharehub.com"
ASHAREHUB_SOURCE = "asharehub_raw"
TS_CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
EXCHANGE_BY_SUFFIX = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}
STATUS_MAP = {"L": "active", "P": "suspended", "D": "delisted"}


class AShareHubMarketDataProvider:
    """Load unadjusted Shanghai, Shenzhen, and Beijing daily data from AShareHub."""

    def __init__(
        self,
        api_key: str,
        start_date: date,
        end_date: date,
        *,
        ts_codes: tuple[str, ...] = (),
        page_size: int = 5000,
        max_requests: int = 20,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("AShareHub API key is required")
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date")
        if not 1 <= page_size <= 5000:
            raise ValueError("page_size must be between 1 and 5000")
        if max_requests < 1:
            raise ValueError("max_requests must be positive")

        normalized_codes = tuple(code.strip().upper() for code in ts_codes)
        invalid_codes = [
            code for code in normalized_codes if TS_CODE_PATTERN.fullmatch(code) is None
        ]
        if invalid_codes:
            raise ValueError(
                "ts_codes must use six digits plus .SH, .SZ, or .BJ; "
                "invalid values: " + ", ".join(invalid_codes)
            )
        if len(set(normalized_codes)) != len(normalized_codes):
            raise ValueError("ts_codes cannot contain duplicates")

        self.start_date = start_date
        self.end_date = end_date
        self.ts_codes = normalized_codes
        self.page_size = page_size
        self.max_requests = max_requests
        self._request_count = 0
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=ASHAREHUB_BASE_URL,
            headers={"X-API-Key": normalized_key},
            timeout=timeout_seconds,
        )

    def load(self) -> MarketDataBatch:
        try:
            stock_payloads = self._load_stock_payloads()
            price_payloads = self._load_price_payloads()
        finally:
            if self._owns_client:
                self._client.close()

        issues: list[ValidationIssue] = []
        stocks = self._parse_stocks(stock_payloads, issues)
        daily_prices = self._parse_prices(price_payloads, issues)
        stock_keys = {stock.key for stock in stocks}
        complete_daily_prices: list[DailyPriceRecord] = []
        warnings: list[IngestionWarning] = []
        for price in daily_prices:
            if price.stock_key not in stock_keys:
                warnings.append(
                    IngestionWarning(
                        code="unknown_stock",
                        message=(
                            "Skipped daily price because AShareHub did not return "
                            "matching stock metadata"
                        ),
                        stock_key=f"{price.exchange}:{price.symbol}",
                    )
                )
            else:
                complete_daily_prices.append(price)

        if issues:
            raise IngestionValidationError(issues)

        return MarketDataBatch(
            stocks=tuple(stocks),
            daily_prices=tuple(complete_daily_prices),
            warnings=tuple(warnings),
        )

    def _load_stock_payloads(self) -> list[dict[str, Any]]:
        if self.ts_codes:
            payloads: list[dict[str, Any]] = []
            for ts_code in self.ts_codes:
                payloads.extend(
                    self._get_all_pages(
                        "/v1/reference/stocks",
                        {"ts_code": ts_code},
                    )
                )
            return payloads
        return self._get_all_pages("/v1/reference/stocks", {})

    def _load_price_payloads(self) -> list[dict[str, Any]]:
        base_params = {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }
        if self.ts_codes:
            payloads: list[dict[str, Any]] = []
            for ts_code in self.ts_codes:
                payloads.extend(
                    self._get_all_pages(
                        "/v1/market/daily",
                        {**base_params, "ts_code": ts_code},
                    )
                )
            return payloads
        return self._get_all_pages("/v1/market/daily", base_params)

    def _get_all_pages(
        self,
        path: str,
        params: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            if self._request_count >= self.max_requests:
                raise MarketDataProviderError(
                    "AShareHub request budget exhausted before the complete batch "
                    f"was retrieved; max_requests={self.max_requests}"
                )
            self._request_count += 1

            try:
                response = self._client.get(
                    path,
                    params={
                        **params,
                        "limit": self.page_size,
                        "offset": offset,
                    },
                )
            except httpx.HTTPError as error:
                raise MarketDataProviderError(
                    f"AShareHub request failed for {path}: {type(error).__name__}"
                ) from error

            if response.status_code == 429:
                raise MarketDataProviderError(
                    "AShareHub daily request limit was reached (HTTP 429)"
                )
            if response.status_code in {401, 403}:
                raise MarketDataProviderError(
                    "AShareHub rejected the API key or access level"
                )
            if response.is_error:
                raise MarketDataProviderError(
                    f"AShareHub returned HTTP {response.status_code} for {path}"
                )

            try:
                payload = response.json()
            except ValueError as error:
                raise MarketDataProviderError(
                    f"AShareHub returned invalid JSON for {path}"
                ) from error
            if not isinstance(payload, list) or not all(
                isinstance(item, dict) for item in payload
            ):
                raise MarketDataProviderError(
                    f"AShareHub returned an unexpected response shape for {path}"
                )

            page = list(payload)
            records.extend(page)
            if len(page) < self.page_size:
                return records
            offset += self.page_size

    def _parse_stocks(
        self,
        payloads: list[dict[str, Any]],
        issues: list[ValidationIssue],
    ) -> list[StockRecord]:
        stocks: list[StockRecord] = []
        seen: set[tuple[str, str]] = set()
        for index, payload in enumerate(payloads, start=1):
            issue_count = len(issues)
            ts_code = self._required_string(
                payload,
                "ts_code",
                "/v1/reference/stocks",
                index,
                issues,
            )
            symbol = self._required_string(
                payload,
                "symbol",
                "/v1/reference/stocks",
                index,
                issues,
            )
            name = self._required_string(
                payload,
                "name",
                "/v1/reference/stocks",
                index,
                issues,
            )
            exchange = self._exchange_from_ts_code(
                ts_code,
                "/v1/reference/stocks",
                index,
                issues,
            )
            list_status = self._required_string(
                payload,
                "list_status",
                "/v1/reference/stocks",
                index,
                issues,
            )
            status = STATUS_MAP.get(list_status)
            if status is None:
                self._issue(
                    issues,
                    "/v1/reference/stocks",
                    index,
                    "list_status",
                    "invalid_status",
                    f"Unsupported AShareHub list_status: {list_status}",
                )
            list_date = self._optional_date(
                payload,
                "list_date",
                "/v1/reference/stocks",
                index,
                issues,
            )
            delist_date = self._optional_date(
                payload,
                "delist_date",
                "/v1/reference/stocks",
                index,
                issues,
            )
            if ts_code and symbol and not ts_code.startswith(f"{symbol}."):
                self._issue(
                    issues,
                    "/v1/reference/stocks",
                    index,
                    "symbol",
                    "symbol_mismatch",
                    "symbol does not match ts_code",
                )

            if len(issues) == issue_count:
                assert exchange is not None
                assert status is not None
                stock = StockRecord(
                    symbol=symbol,
                    exchange=exchange,
                    name=name,
                    list_date=list_date,
                    delist_date=delist_date,
                    status=status,
                )
                if stock.key in seen:
                    self._issue(
                        issues,
                        "/v1/reference/stocks",
                        index,
                        "ts_code",
                        "duplicate_stock",
                        f"Duplicate stock metadata: {exchange}:{symbol}",
                    )
                else:
                    seen.add(stock.key)
                    stocks.append(stock)
        return stocks

    def _parse_prices(
        self,
        payloads: list[dict[str, Any]],
        issues: list[ValidationIssue],
    ) -> list[DailyPriceRecord]:
        prices: list[DailyPriceRecord] = []
        seen: set[tuple[str, str, date]] = set()
        for index, payload in enumerate(payloads, start=1):
            issue_count = len(issues)
            ts_code = self._required_string(
                payload,
                "ts_code",
                "/v1/market/daily",
                index,
                issues,
            )
            exchange = self._exchange_from_ts_code(
                ts_code,
                "/v1/market/daily",
                index,
                issues,
            )
            symbol = ts_code.split(".", maxsplit=1)[0] if ts_code else ""
            trade_date = self._required_date(
                payload,
                "trade_date",
                "/v1/market/daily",
                index,
                issues,
            )
            open_price = self._required_decimal(
                payload, "open", "/v1/market/daily", index, issues
            )
            high = self._required_decimal(
                payload, "high", "/v1/market/daily", index, issues
            )
            low = self._required_decimal(
                payload, "low", "/v1/market/daily", index, issues
            )
            close = self._required_decimal(
                payload, "close", "/v1/market/daily", index, issues
            )
            volume_lots = self._required_decimal(
                payload, "vol", "/v1/market/daily", index, issues
            )
            amount_thousands = self._optional_decimal(
                payload, "amount", "/v1/market/daily", index, issues
            )

            for field, value in (
                ("open", open_price),
                ("high", high),
                ("low", low),
                ("close", close),
                ("vol", volume_lots),
                ("amount", amount_thousands),
            ):
                if value is not None and value < 0:
                    self._issue(
                        issues,
                        "/v1/market/daily",
                        index,
                        field,
                        "negative_value",
                        f"{field} cannot be negative",
                    )
            if all(value is not None for value in (open_price, high, low, close)):
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                if high < max(open_price, low, close):
                    self._issue(
                        issues,
                        "/v1/market/daily",
                        index,
                        "high",
                        "invalid_ohlc",
                        "high must be greater than or equal to open, low, and close",
                    )
                if low > min(open_price, high, close):
                    self._issue(
                        issues,
                        "/v1/market/daily",
                        index,
                        "low",
                        "invalid_ohlc",
                        "low must be less than or equal to open, high, and close",
                    )

            volume: int | None = None
            if volume_lots is not None:
                volume_shares = volume_lots * 100
                if volume_shares != volume_shares.to_integral_value():
                    self._issue(
                        issues,
                        "/v1/market/daily",
                        index,
                        "vol",
                        "invalid_volume_unit",
                        "vol cannot be converted from lots to whole shares",
                    )
                else:
                    volume = int(volume_shares)
            amount = amount_thousands * 1000 if amount_thousands is not None else None

            if len(issues) == issue_count:
                assert exchange is not None
                assert trade_date is not None
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                assert volume is not None
                price = DailyPriceRecord(
                    symbol=symbol,
                    exchange=exchange,
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    amount=amount,
                    source=ASHAREHUB_SOURCE,
                )
                if price.key in seen:
                    self._issue(
                        issues,
                        "/v1/market/daily",
                        index,
                        "trade_date",
                        "duplicate_price",
                        (
                            "Duplicate AShareHub daily price: "
                            f"{exchange}:{symbol}:{trade_date}"
                        ),
                    )
                else:
                    seen.add(price.key)
                    prices.append(price)
        return prices

    def _exchange_from_ts_code(
        self,
        ts_code: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> str | None:
        match = TS_CODE_PATTERN.fullmatch(ts_code)
        if match is None:
            self._issue(
                issues,
                path,
                row,
                "ts_code",
                "invalid_ts_code",
                "ts_code must use six digits plus .SH, .SZ, or .BJ",
            )
            return None
        return EXCHANGE_BY_SUFFIX[match.group(1)]

    def _required_string(
        self,
        payload: Mapping[str, Any],
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            self._issue(
                issues,
                path,
                row,
                field,
                "missing_value",
                f"{field} must be a non-empty string",
            )
            return ""
        return value.strip()

    def _required_date(
        self,
        payload: Mapping[str, Any],
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        value = self._required_string(payload, field, path, row, issues)
        if not value:
            return None
        return self._parse_date(value, field, path, row, issues)

    def _optional_date(
        self,
        payload: Mapping[str, Any],
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        value = payload.get(field)
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            self._issue(
                issues,
                path,
                row,
                field,
                "invalid_date",
                f"{field} must use YYYY-MM-DD format",
            )
            return None
        return self._parse_date(value, field, path, row, issues)

    def _parse_date(
        self,
        value: str,
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        try:
            return date.fromisoformat(value)
        except ValueError:
            self._issue(
                issues,
                path,
                row,
                field,
                "invalid_date",
                f"{field} must use YYYY-MM-DD format",
            )
            return None

    def _required_decimal(
        self,
        payload: Mapping[str, Any],
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        value = payload.get(field)
        if value in (None, ""):
            self._issue(
                issues,
                path,
                row,
                field,
                "missing_value",
                f"{field} is required",
            )
            return None
        return self._parse_decimal(value, field, path, row, issues)

    def _optional_decimal(
        self,
        payload: Mapping[str, Any],
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        value = payload.get(field)
        if value in (None, ""):
            return None
        return self._parse_decimal(value, field, path, row, issues)

    def _parse_decimal(
        self,
        value: Any,
        field: str,
        path: str,
        row: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            parsed = None
        if parsed is None or not parsed.is_finite():
            self._issue(
                issues,
                path,
                row,
                field,
                "invalid_number",
                f"{field} must be a finite decimal number",
            )
            return None
        return parsed

    @staticmethod
    def _issue(
        issues: list[ValidationIssue],
        path: str,
        row: int,
        field: str,
        code: str,
        message: str,
    ) -> None:
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                file=f"asharehub:{path}",
                row=row,
                field=field,
            )
        )
