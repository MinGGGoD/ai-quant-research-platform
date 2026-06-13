from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.database import DailyPrice, Stock
from scanner.ingestion.errors import IngestionPersistenceError
from scanner.ingestion.types import MarketDataBatch


@dataclass(frozen=True, slots=True)
class PersistenceStats:
    stocks_inserted: int
    stocks_updated: int
    prices_inserted: int
    prices_updated: int


def upsert_market_data(session: Session, batch: MarketDataBatch) -> PersistenceStats:
    stock_keys = [record.key for record in batch.stocks]
    existing_stock_keys = _existing_stock_keys(session, stock_keys)

    if batch.stocks:
        stock_insert = insert(Stock).values(
            [
                {
                    "symbol": record.symbol,
                    "exchange": record.exchange,
                    "name": record.name,
                    "list_date": record.list_date,
                    "delist_date": record.delist_date,
                    "status": record.status,
                }
                for record in batch.stocks
            ]
        )
        session.execute(
            stock_insert.on_conflict_do_update(
                constraint="uq_stocks_exchange_symbol",
                set_={
                    "name": stock_insert.excluded.name,
                    "list_date": stock_insert.excluded.list_date,
                    "delist_date": stock_insert.excluded.delist_date,
                    "status": stock_insert.excluded.status,
                    "updated_at": func.now(),
                },
            )
        )

    referenced_stock_keys = sorted({record.stock_key for record in batch.daily_prices})
    stock_ids = _stock_ids(session, referenced_stock_keys)
    missing_stock_keys = set(referenced_stock_keys) - set(stock_ids)
    if missing_stock_keys:
        formatted_keys = ", ".join(
            f"{exchange}:{symbol}" for exchange, symbol in sorted(missing_stock_keys)
        )
        raise IngestionPersistenceError(
            f"Daily prices reference unknown stocks: {formatted_keys}"
        )

    price_keys = [
        (stock_ids[record.stock_key], record.trade_date)
        for record in batch.daily_prices
    ]
    existing_price_keys = _existing_price_keys(session, price_keys)

    if batch.daily_prices:
        price_insert = insert(DailyPrice).values(
            [
                {
                    "stock_id": stock_ids[record.stock_key],
                    "trade_date": record.trade_date,
                    "open": record.open,
                    "high": record.high,
                    "low": record.low,
                    "close": record.close,
                    "volume": record.volume,
                    "amount": record.amount,
                    "source": record.source,
                }
                for record in batch.daily_prices
            ]
        )
        session.execute(
            price_insert.on_conflict_do_update(
                constraint="uq_daily_prices_stock_id_trade_date",
                set_={
                    "open": price_insert.excluded.open,
                    "high": price_insert.excluded.high,
                    "low": price_insert.excluded.low,
                    "close": price_insert.excluded.close,
                    "volume": price_insert.excluded.volume,
                    "amount": price_insert.excluded.amount,
                    "source": price_insert.excluded.source,
                    "updated_at": func.now(),
                },
            )
        )

    return PersistenceStats(
        stocks_inserted=len(stock_keys) - len(existing_stock_keys),
        stocks_updated=len(existing_stock_keys),
        prices_inserted=len(price_keys) - len(existing_price_keys),
        prices_updated=len(existing_price_keys),
    )


def _existing_stock_keys(
    session: Session,
    keys: list[tuple[str, str]],
) -> set[tuple[str, str]]:
    if not keys:
        return set()
    rows = session.execute(
        select(Stock.exchange, Stock.symbol).where(
            tuple_(Stock.exchange, Stock.symbol).in_(keys)
        )
    )
    return set(rows.tuples())


def _stock_ids(
    session: Session,
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    if not keys:
        return {}
    rows = session.execute(
        select(Stock.exchange, Stock.symbol, Stock.id).where(
            tuple_(Stock.exchange, Stock.symbol).in_(keys)
        )
    )
    return {
        (exchange, symbol): stock_id for exchange, symbol, stock_id in rows.tuples()
    }


def _existing_price_keys(
    session: Session,
    keys: list[tuple[int, date]],
) -> set[tuple[int, date]]:
    if not keys:
        return set()
    rows = session.execute(
        select(DailyPrice.stock_id, DailyPrice.trade_date).where(
            tuple_(DailyPrice.stock_id, DailyPrice.trade_date).in_(keys)
        )
    )
    return set(rows.tuples())
