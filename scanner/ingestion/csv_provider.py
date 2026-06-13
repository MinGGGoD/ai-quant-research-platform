import csv
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scanner.ingestion.errors import IngestionValidationError, ValidationIssue
from scanner.ingestion.types import (
    DailyPriceRecord,
    IngestionWarning,
    MarketDataBatch,
    StockRecord,
)

ALLOWED_EXCHANGES = {"SSE", "SZSE", "BSE"}
ALLOWED_STATUSES = {"active", "suspended", "delisted"}
SYMBOL_PATTERN = re.compile(r"^\d{6}$")
STOCK_REQUIRED_FIELDS = {"symbol", "exchange", "name"}
PRICE_REQUIRED_FIELDS = {
    "symbol",
    "exchange",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


class CsvMarketDataProvider:
    """Load a complete, validated market data batch from two CSV files."""

    def __init__(
        self,
        stocks_file: Path,
        prices_file: Path,
        source: str,
        *,
        expected_through: date | None = None,
        max_staleness_days: int = 7,
    ) -> None:
        normalized_source = source.strip()
        if not normalized_source or len(normalized_source) > 64:
            raise ValueError("source must contain between 1 and 64 characters")
        if max_staleness_days < 0:
            raise ValueError("max_staleness_days must be non-negative")

        self.stocks_file = stocks_file
        self.prices_file = prices_file
        self.source = normalized_source
        self.expected_through = expected_through
        self.max_staleness_days = max_staleness_days

    def load(self) -> MarketDataBatch:
        issues: list[ValidationIssue] = []
        stocks = self._load_stocks(issues)
        prices = self._load_prices(issues)
        self._validate_duplicate_stocks(stocks, issues)
        self._validate_duplicate_prices(prices, issues)
        self._validate_expected_dates(prices, issues)

        if issues:
            raise IngestionValidationError(issues)

        return MarketDataBatch(
            stocks=tuple(stocks),
            daily_prices=tuple(prices),
            warnings=tuple(self._staleness_warnings(prices)),
        )

    def _read_rows(
        self,
        path: Path,
        required_fields: set[str],
        issues: list[ValidationIssue],
    ) -> list[tuple[int, dict[str, str]]]:
        try:
            with path.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                fieldnames = set(reader.fieldnames or [])
                missing_headers = sorted(required_fields - fieldnames)
                if missing_headers:
                    issues.append(
                        ValidationIssue(
                            code="missing_columns",
                            message=(
                                "Missing required columns: "
                                + ", ".join(missing_headers)
                            ),
                            file=str(path),
                        )
                    )
                    return []

                rows = [
                    (
                        row_number,
                        {
                            key: (value or "").strip()
                            for key, value in row.items()
                            if key is not None
                        },
                    )
                    for row_number, row in enumerate(reader, start=2)
                ]
        except (OSError, csv.Error) as error:
            issues.append(
                ValidationIssue(
                    code="file_error",
                    message=str(error),
                    file=str(path),
                )
            )
            return []

        if not rows:
            issues.append(
                ValidationIssue(
                    code="empty_file",
                    message="The CSV file contains no data rows",
                    file=str(path),
                )
            )
        return rows

    def _load_stocks(self, issues: list[ValidationIssue]) -> list[StockRecord]:
        records: list[StockRecord] = []
        for row_number, row in self._read_rows(
            self.stocks_file,
            STOCK_REQUIRED_FIELDS,
            issues,
        ):
            issue_count = len(issues)
            symbol = self._symbol(row, self.stocks_file, row_number, issues)
            exchange = self._exchange(row, self.stocks_file, row_number, issues)
            name = self._required_text(
                row,
                "name",
                self.stocks_file,
                row_number,
                issues,
                max_length=128,
            )
            list_date = self._optional_date(
                row,
                "list_date",
                self.stocks_file,
                row_number,
                issues,
            )
            delist_date = self._optional_date(
                row,
                "delist_date",
                self.stocks_file,
                row_number,
                issues,
            )
            status = row.get("status", "") or "active"
            if status not in ALLOWED_STATUSES:
                self._add_issue(
                    issues,
                    self.stocks_file,
                    row_number,
                    "status",
                    "invalid_status",
                    f"status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}",
                )
            if (
                list_date is not None
                and delist_date is not None
                and delist_date < list_date
            ):
                self._add_issue(
                    issues,
                    self.stocks_file,
                    row_number,
                    "delist_date",
                    "invalid_date_range",
                    "delist_date cannot be earlier than list_date",
                )

            if len(issues) == issue_count:
                records.append(
                    StockRecord(
                        symbol=symbol,
                        exchange=exchange,
                        name=name,
                        list_date=list_date,
                        delist_date=delist_date,
                        status=status,
                    )
                )
        return records

    def _load_prices(self, issues: list[ValidationIssue]) -> list[DailyPriceRecord]:
        records: list[DailyPriceRecord] = []
        for row_number, row in self._read_rows(
            self.prices_file,
            PRICE_REQUIRED_FIELDS,
            issues,
        ):
            issue_count = len(issues)
            symbol = self._symbol(row, self.prices_file, row_number, issues)
            exchange = self._exchange(row, self.prices_file, row_number, issues)
            trade_date = self._required_date(
                row,
                "trade_date",
                self.prices_file,
                row_number,
                issues,
            )
            open_price = self._required_decimal(
                row, "open", self.prices_file, row_number, issues
            )
            high = self._required_decimal(
                row, "high", self.prices_file, row_number, issues
            )
            low = self._required_decimal(
                row, "low", self.prices_file, row_number, issues
            )
            close = self._required_decimal(
                row, "close", self.prices_file, row_number, issues
            )
            volume = self._required_integer(
                row, "volume", self.prices_file, row_number, issues
            )
            amount = self._optional_decimal(
                row, "amount", self.prices_file, row_number, issues
            )

            for field, value in (
                ("open", open_price),
                ("high", high),
                ("low", low),
                ("close", close),
            ):
                if value is not None and value < 0:
                    self._add_issue(
                        issues,
                        self.prices_file,
                        row_number,
                        field,
                        "negative_value",
                        f"{field} cannot be negative",
                    )
            if volume is not None and volume < 0:
                self._add_issue(
                    issues,
                    self.prices_file,
                    row_number,
                    "volume",
                    "negative_value",
                    "volume cannot be negative",
                )
            if amount is not None and amount < 0:
                self._add_issue(
                    issues,
                    self.prices_file,
                    row_number,
                    "amount",
                    "negative_value",
                    "amount cannot be negative",
                )
            if all(value is not None for value in (open_price, high, low, close)):
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                if high < max(open_price, low, close):
                    self._add_issue(
                        issues,
                        self.prices_file,
                        row_number,
                        "high",
                        "invalid_ohlc",
                        "high must be greater than or equal to open, low, and close",
                    )
                if low > min(open_price, high, close):
                    self._add_issue(
                        issues,
                        self.prices_file,
                        row_number,
                        "low",
                        "invalid_ohlc",
                        "low must be less than or equal to open, high, and close",
                    )

            if len(issues) == issue_count:
                assert trade_date is not None
                assert open_price is not None
                assert high is not None
                assert low is not None
                assert close is not None
                assert volume is not None
                records.append(
                    DailyPriceRecord(
                        symbol=symbol,
                        exchange=exchange,
                        trade_date=trade_date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                        amount=amount,
                        source=self.source,
                    )
                )
        return records

    def _validate_duplicate_stocks(
        self,
        records: list[StockRecord],
        issues: list[ValidationIssue],
    ) -> None:
        seen: set[tuple[str, str]] = set()
        for record in records:
            if record.key in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate_stock",
                        message=(
                            f"Duplicate stock key {record.exchange}:{record.symbol}"
                        ),
                        file=str(self.stocks_file),
                    )
                )
            seen.add(record.key)

    def _validate_duplicate_prices(
        self,
        records: list[DailyPriceRecord],
        issues: list[ValidationIssue],
    ) -> None:
        seen: set[tuple[str, str, date]] = set()
        for record in records:
            if record.key in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate_price",
                        message=(
                            "Duplicate daily price key "
                            f"{record.exchange}:{record.symbol}:{record.trade_date}"
                        ),
                        file=str(self.prices_file),
                    )
                )
            seen.add(record.key)

    def _validate_expected_dates(
        self,
        records: list[DailyPriceRecord],
        issues: list[ValidationIssue],
    ) -> None:
        if self.expected_through is None:
            return
        for record in records:
            if record.trade_date > self.expected_through:
                issues.append(
                    ValidationIssue(
                        code="future_trade_date",
                        message=(
                            f"{record.trade_date} is later than expected-through "
                            f"date {self.expected_through}"
                        ),
                        file=str(self.prices_file),
                        field="trade_date",
                    )
                )

    def _staleness_warnings(
        self,
        records: list[DailyPriceRecord],
    ) -> list[IngestionWarning]:
        if self.expected_through is None:
            return []

        latest_dates: dict[tuple[str, str], date] = defaultdict(lambda: date.min)
        for record in records:
            latest_dates[record.stock_key] = max(
                latest_dates[record.stock_key],
                record.trade_date,
            )

        warnings: list[IngestionWarning] = []
        for (exchange, symbol), latest_date in sorted(latest_dates.items()):
            stale_days = (self.expected_through - latest_date).days
            if stale_days > self.max_staleness_days:
                warnings.append(
                    IngestionWarning(
                        code="stale_price_data",
                        message=(
                            f"Latest trade date {latest_date} is {stale_days} days "
                            f"before expected-through date {self.expected_through}"
                        ),
                        stock_key=f"{exchange}:{symbol}",
                    )
                )
        return warnings

    def _symbol(
        self,
        row: dict[str, str],
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> str:
        symbol = self._required_text(
            row, "symbol", path, row_number, issues, max_length=16
        )
        if symbol and SYMBOL_PATTERN.fullmatch(symbol) is None:
            self._add_issue(
                issues,
                path,
                row_number,
                "symbol",
                "invalid_symbol",
                "symbol must contain exactly six digits",
            )
        return symbol

    def _exchange(
        self,
        row: dict[str, str],
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> str:
        exchange = self._required_text(
            row, "exchange", path, row_number, issues, max_length=8
        ).upper()
        if exchange and exchange not in ALLOWED_EXCHANGES:
            self._add_issue(
                issues,
                path,
                row_number,
                "exchange",
                "invalid_exchange",
                f"exchange must be one of: {', '.join(sorted(ALLOWED_EXCHANGES))}",
            )
        return exchange

    def _required_text(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
        *,
        max_length: int,
    ) -> str:
        value = row.get(field, "")
        if not value:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "missing_value",
                f"{field} is required",
            )
        elif len(value) > max_length:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "value_too_long",
                f"{field} cannot exceed {max_length} characters",
            )
        return value

    def _required_date(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        value = row.get(field, "")
        if not value:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "missing_value",
                f"{field} is required",
            )
            return None
        return self._parse_date(value, field, path, row_number, issues)

    def _optional_date(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        value = row.get(field, "")
        if not value:
            return None
        return self._parse_date(value, field, path, row_number, issues)

    def _parse_date(
        self,
        value: str,
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> date | None:
        try:
            return date.fromisoformat(value)
        except ValueError:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "invalid_date",
                f"{field} must use YYYY-MM-DD format",
            )
            return None

    def _required_decimal(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        value = row.get(field, "")
        if not value:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "missing_value",
                f"{field} is required",
            )
            return None
        return self._parse_decimal(value, field, path, row_number, issues)

    def _optional_decimal(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        value = row.get(field, "")
        if not value:
            return None
        return self._parse_decimal(value, field, path, row_number, issues)

    def _parse_decimal(
        self,
        value: str,
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> Decimal | None:
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            parsed = None
        if parsed is None or not parsed.is_finite():
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "invalid_number",
                f"{field} must be a finite decimal number",
            )
            return None
        return parsed

    def _required_integer(
        self,
        row: dict[str, str],
        field: str,
        path: Path,
        row_number: int,
        issues: list[ValidationIssue],
    ) -> int | None:
        value = row.get(field, "")
        if not value:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "missing_value",
                f"{field} is required",
            )
            return None
        try:
            return int(value)
        except ValueError:
            self._add_issue(
                issues,
                path,
                row_number,
                field,
                "invalid_integer",
                f"{field} must be an integer",
            )
            return None

    @staticmethod
    def _add_issue(
        issues: list[ValidationIssue],
        path: Path,
        row_number: int,
        field: str,
        code: str,
        message: str,
    ) -> None:
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                file=str(path),
                row=row_number,
                field=field,
            )
        )
