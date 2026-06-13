from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class StockRecord:
    symbol: str
    exchange: str
    name: str
    list_date: date | None
    delist_date: date | None
    status: str

    @property
    def key(self) -> tuple[str, str]:
        return self.exchange, self.symbol


@dataclass(frozen=True, slots=True)
class DailyPriceRecord:
    symbol: str
    exchange: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal | None
    source: str

    @property
    def stock_key(self) -> tuple[str, str]:
        return self.exchange, self.symbol

    @property
    def key(self) -> tuple[str, str, date]:
        return self.exchange, self.symbol, self.trade_date


@dataclass(frozen=True, slots=True)
class IngestionWarning:
    code: str
    message: str
    stock_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MarketDataBatch:
    stocks: tuple[StockRecord, ...]
    daily_prices: tuple[DailyPriceRecord, ...]
    warnings: tuple[IngestionWarning, ...] = ()


class MarketDataProvider(Protocol):
    def load(self) -> MarketDataBatch:
        """Load and validate one complete market data batch."""


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    stocks_inserted: int
    stocks_updated: int
    prices_inserted: int
    prices_updated: int
    warnings: tuple[IngestionWarning, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stocks_inserted": self.stocks_inserted,
            "stocks_updated": self.stocks_updated,
            "prices_inserted": self.prices_inserted,
            "prices_updated": self.prices_updated,
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
