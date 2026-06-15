from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from backend.app.database import DailyPrice, SignalDefinition, Stock
from scanner.scanning.errors import ScanConfigurationError
from scanner.scanning.types import ScanStock, StockKey
from scanner.signals import PriceBar, SignalRule


def load_scan_stocks(
    session: Session,
    stock_keys: Sequence[StockKey],
) -> list[ScanStock]:
    statement = select(Stock.id, Stock.exchange, Stock.symbol)
    if stock_keys:
        statement = statement.where(
            tuple_(Stock.exchange, Stock.symbol).in_(stock_keys)
        )
    else:
        statement = statement.where(Stock.status.in_(("active", "suspended")))

    rows = session.execute(statement.order_by(Stock.exchange, Stock.symbol))
    return [
        ScanStock(id=stock_id, exchange=exchange, symbol=symbol)
        for stock_id, exchange, symbol in rows.tuples()
    ]


def load_price_histories(
    session: Session,
    stock_ids: Sequence[int],
    data_date: date,
    max_bars: int,
) -> dict[int, tuple[PriceBar, ...]]:
    if not stock_ids:
        return {}

    row_number = func.row_number().over(
        partition_by=DailyPrice.stock_id,
        order_by=DailyPrice.trade_date.desc(),
    )
    ranked_prices = (
        select(
            DailyPrice.stock_id.label("stock_id"),
            DailyPrice.trade_date.label("trade_date"),
            DailyPrice.high.label("high"),
            DailyPrice.close.label("close"),
            DailyPrice.volume.label("volume"),
            row_number.label("row_number"),
        )
        .where(
            DailyPrice.stock_id.in_(stock_ids),
            DailyPrice.trade_date <= data_date,
        )
        .subquery()
    )
    rows = session.execute(
        select(
            ranked_prices.c.stock_id,
            ranked_prices.c.trade_date,
            ranked_prices.c.high,
            ranked_prices.c.close,
            ranked_prices.c.volume,
        )
        .where(ranked_prices.c.row_number <= max_bars)
        .order_by(ranked_prices.c.stock_id, ranked_prices.c.trade_date)
    )

    histories: dict[int, list[PriceBar]] = {}
    for stock_id, trade_date, high, close, volume in rows.tuples():
        histories.setdefault(stock_id, []).append(
            PriceBar(
                trade_date=trade_date,
                high=high,
                close=close,
                volume=volume,
            )
        )
    return {stock_id: tuple(history) for stock_id, history in histories.items()}


def ensure_signal_definitions(
    session: Session,
    rules: Sequence[SignalRule],
) -> dict[str, SignalDefinition]:
    rule_keys = [(rule.code, rule.version) for rule in rules]
    existing = session.scalars(
        select(SignalDefinition).where(
            tuple_(SignalDefinition.code, SignalDefinition.version).in_(rule_keys)
        )
    ).all()
    definitions = {
        (definition.code, definition.version): definition for definition in existing
    }

    for rule in rules:
        key = (rule.code, rule.version)
        definition = definitions.get(key)
        if definition is None:
            definition = SignalDefinition(
                code=rule.code,
                version=rule.version,
                name=rule.name,
                description=rule.description,
                parameters=rule.parameters,
                is_active=True,
            )
            session.add(definition)
            definitions[key] = definition
            continue

        if (
            definition.name != rule.name
            or definition.description != rule.description
            or definition.parameters != rule.parameters
        ):
            raise ScanConfigurationError(
                f"Stored signal definition differs from {rule.code} version "
                f"{rule.version}; create a new rule version instead of changing it"
            )
        if not definition.is_active:
            raise ScanConfigurationError(
                f"Signal definition is inactive: {rule.code} version {rule.version}"
            )

    session.flush()
    return {rule.code: definitions[(rule.code, rule.version)] for rule in rules}
