from __future__ import annotations

import csv
import zlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

EXCHANGE_BY_MARKET = {"sh": "SSE", "sz": "SZSE"}
MARKET_BY_EXCHANGE = {value: key for key, value in EXCHANGE_BY_MARKET.items()}
LOCAL_CACHE_SOURCE = "baostock_qfq_file_cache"
LOCAL_CACHE_DERIVED_60M_SOURCE = "baostock_qfq_file_cache_derived_60m"
LOCAL_CACHE_PRICE_ADJUSTMENT: Literal["front_adjusted"] = "front_adjusted"
PriceFrequency = Literal["daily", "30m", "60m"]
CACHE_DIRECTORY_BY_FREQUENCY: dict[PriceFrequency, str] = {
    "daily": "daily_qfq",
    "30m": "30m_qfq",
    "60m": "60m_qfq",
}


@dataclass(frozen=True, slots=True)
class LocalCachedStock:
    id: int
    symbol: str
    exchange: str
    name: str
    list_date: date | None
    delist_date: date | None
    status: str
    category: str
    full_code: str


@dataclass(frozen=True, slots=True)
class LocalCachedPrice:
    trade_date: date
    timestamp: datetime | None
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float | None
    source: str


def local_stock_id(full_code: str) -> int:
    checksum = zlib.crc32(full_code.encode("utf-8"))
    return -(checksum % 2_000_000_000 + 1)


class LocalDailyCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.manifest_file = cache_dir / "stocks_manifest.csv"
        self._stocks: tuple[LocalCachedStock, ...] | None = None

    def available(self) -> bool:
        return self.manifest_file.exists()

    def list_stocks(
        self,
        *,
        query: str | None,
        exchange: str | None,
        status: str,
        limit: int,
        offset: int,
        exclude_keys: set[tuple[str, str]] | None = None,
    ) -> tuple[list[LocalCachedStock], int]:
        exclude_keys = exclude_keys or set()
        normalized_query = query.casefold() if query else None
        items = [
            stock
            for stock in self.stocks()
            if stock.status == status
            and (stock.exchange, stock.symbol) not in exclude_keys
            and (exchange is None or stock.exchange == exchange)
            and (
                normalized_query is None
                or normalized_query in stock.symbol.casefold()
                or normalized_query in stock.name.casefold()
                or normalized_query in stock.full_code.casefold()
            )
        ]
        return items[offset : offset + limit], len(items)

    def find_stocks(
        self,
        *,
        symbol: str,
        exchange: str | None,
        exclude_keys: set[tuple[str, str]] | None = None,
    ) -> list[LocalCachedStock]:
        exclude_keys = exclude_keys or set()
        normalized_symbol = symbol.strip()
        return [
            stock
            for stock in self.stocks()
            if stock.symbol == normalized_symbol
            and (exchange is None or stock.exchange == exchange)
            and (stock.exchange, stock.symbol) not in exclude_keys
        ]

    def list_prices(
        self,
        stock: LocalCachedStock,
        *,
        from_date: date | None,
        to_date: date | None,
        limit: int,
        frequency: PriceFrequency = "daily",
    ) -> list[LocalCachedPrice]:
        if frequency == "60m" and not self.price_file_for(
            stock,
            frequency="60m",
        ).exists():
            thirty_minute_prices = self._read_prices(
                stock,
                from_date=from_date,
                to_date=to_date,
                limit=limit * 2,
                frequency="30m",
            )
            return self._aggregate_30m_to_60m(thirty_minute_prices)[-limit:]

        return self._read_prices(
            stock,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            frequency=frequency,
        )

    def price_file_for(
        self,
        stock: LocalCachedStock,
        *,
        frequency: PriceFrequency = "daily",
    ) -> Path:
        return (
            self.cache_dir_for_frequency(frequency)
            / "prices"
            / stock.category
            / f"{stock.full_code.replace('.', '_')}.csv"
        )

    def cache_dir_for_frequency(self, frequency: PriceFrequency) -> Path:
        if frequency == "daily":
            return self.cache_dir
        return self.cache_dir.parent / CACHE_DIRECTORY_BY_FREQUENCY[frequency]

    def price_date_bounds(
        self,
        stock: LocalCachedStock,
        *,
        frequency: PriceFrequency = "daily",
    ) -> tuple[date | None, date | None]:
        price_file = self.price_file_for(stock, frequency=frequency)
        if not price_file.exists():
            return None, None

        dates: list[date] = []
        with price_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("date"):
                    dates.append(date.fromisoformat(row["date"]))
        if not dates:
            return None, None
        return min(dates), max(dates)

    def stocks(self) -> tuple[LocalCachedStock, ...]:
        if self._stocks is None:
            self._stocks = self._load_stocks()
        return self._stocks

    def _read_prices(
        self,
        stock: LocalCachedStock,
        *,
        from_date: date | None,
        to_date: date | None,
        limit: int,
        frequency: PriceFrequency,
    ) -> list[LocalCachedPrice]:
        price_file = self.price_file_for(stock, frequency=frequency)
        if not price_file.exists():
            return []
        rows: list[LocalCachedPrice] = []
        with price_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                trade_date = date.fromisoformat(row["date"])
                if from_date is not None and trade_date < from_date:
                    continue
                if to_date is not None and trade_date > to_date:
                    continue
                rows.append(
                    LocalCachedPrice(
                        trade_date=trade_date,
                        timestamp=(
                            self._parse_intraday_timestamp(row["time"])
                            if frequency in {"30m", "60m"}
                            else None
                        ),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]),
                        amount=float(row["amount"]) if row.get("amount") else None,
                        source=LOCAL_CACHE_SOURCE,
                    )
                )
        return rows[-limit:]

    def _aggregate_30m_to_60m(
        self,
        prices: list[LocalCachedPrice],
    ) -> list[LocalCachedPrice]:
        aggregated: list[LocalCachedPrice] = []
        day_rows: list[LocalCachedPrice] = []
        current_date: date | None = None

        for price in prices:
            if current_date is not None and price.trade_date != current_date:
                aggregated.extend(self._aggregate_intraday_day(day_rows))
                day_rows = []
            current_date = price.trade_date
            day_rows.append(price)

        if day_rows:
            aggregated.extend(self._aggregate_intraday_day(day_rows))
        return aggregated

    def _aggregate_intraday_day(
        self,
        prices: list[LocalCachedPrice],
    ) -> list[LocalCachedPrice]:
        rows = sorted(
            prices,
            key=lambda price: price.timestamp or datetime.min,
        )
        aggregated: list[LocalCachedPrice] = []
        for index in range(0, len(rows), 2):
            group = rows[index : index + 2]
            first = group[0]
            last = group[-1]
            amounts = [
                price.amount for price in group if price.amount is not None
            ]
            aggregated.append(
                LocalCachedPrice(
                    trade_date=last.trade_date,
                    timestamp=last.timestamp,
                    open=first.open,
                    high=max(price.high for price in group),
                    low=min(price.low for price in group),
                    close=last.close,
                    volume=sum(price.volume for price in group),
                    amount=sum(amounts) if amounts else None,
                    source=LOCAL_CACHE_DERIVED_60M_SOURCE,
                )
            )
        return aggregated

    def _parse_intraday_timestamp(self, value: str) -> datetime:
        return datetime.strptime(value.strip()[:14], "%Y%m%d%H%M%S")

    def _load_stocks(self) -> tuple[LocalCachedStock, ...]:
        if not self.manifest_file.exists():
            return ()
        stocks: list[LocalCachedStock] = []
        with self.manifest_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("should_fetch") != "true":
                    continue
                market = row["market"].strip().lower()
                exchange = EXCHANGE_BY_MARKET.get(market)
                if exchange is None:
                    continue
                full_code = row["full_code"].strip().lower()
                symbol = row["code"].strip()
                stocks.append(
                    LocalCachedStock(
                        id=local_stock_id(full_code),
                        symbol=symbol,
                        exchange=exchange,
                        name=row["name"].strip(),
                        list_date=(
                            date.fromisoformat(row["list_date"])
                            if row.get("list_date")
                            else None
                        ),
                        delist_date=None,
                        status="active",
                        category=row["category"].strip(),
                        full_code=full_code,
                    )
                )
        return tuple(sorted(stocks, key=lambda stock: (stock.exchange, stock.symbol)))
