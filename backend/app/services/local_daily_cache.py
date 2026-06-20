from __future__ import annotations

import csv
import zlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

EXCHANGE_BY_MARKET = {"sh": "SSE", "sz": "SZSE"}
MARKET_BY_EXCHANGE = {value: key for key, value in EXCHANGE_BY_MARKET.items()}
LOCAL_CACHE_SOURCE = "baostock_qfq_file_cache"
LOCAL_CACHE_PRICE_ADJUSTMENT: Literal["front_adjusted"] = "front_adjusted"


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
class LocalCachedDailyPrice:
    trade_date: date
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
    ) -> list[LocalCachedDailyPrice]:
        price_file = self.price_file_for(stock)
        if not price_file.exists():
            return []
        rows: list[LocalCachedDailyPrice] = []
        with price_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                trade_date = date.fromisoformat(row["date"])
                if from_date is not None and trade_date < from_date:
                    continue
                if to_date is not None and trade_date > to_date:
                    continue
                rows.append(
                    LocalCachedDailyPrice(
                        trade_date=trade_date,
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

    def price_file_for(self, stock: LocalCachedStock) -> Path:
        return (
            self.cache_dir
            / "prices"
            / stock.category
            / f"{stock.full_code.replace('.', '_')}.csv"
        )

    def stocks(self) -> tuple[LocalCachedStock, ...]:
        if self._stocks is None:
            self._stocks = self._load_stocks()
        return self._stocks

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
