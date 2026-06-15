from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from backend.app.database import (
    DailyPrice,
    ResearchNote,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)


def list_stocks(
    session: Session,
    *,
    query: str | None,
    exchange: str | None,
    status: str,
    limit: int,
    offset: int,
) -> tuple[list[Stock], int]:
    filters = [Stock.status == status]
    if query:
        filters.append(
            or_(
                Stock.symbol.ilike(f"%{query}%"),
                Stock.name.ilike(f"%{query}%"),
            )
        )
    if exchange:
        filters.append(Stock.exchange == exchange)

    total = session.scalar(select(func.count()).select_from(Stock).where(*filters)) or 0
    items = session.scalars(
        select(Stock)
        .where(*filters)
        .order_by(Stock.exchange, Stock.symbol)
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), total


def find_stocks(
    session: Session,
    *,
    symbol: str,
    exchange: str | None,
) -> list[Stock]:
    statement = select(Stock).where(Stock.symbol == symbol)
    if exchange:
        statement = statement.where(Stock.exchange == exchange)
    return list(session.scalars(statement.order_by(Stock.exchange)).all())


def list_prices(
    session: Session,
    *,
    stock_id: int,
    from_date: date | None,
    to_date: date | None,
    limit: int,
) -> list[DailyPrice]:
    statement = select(DailyPrice).where(DailyPrice.stock_id == stock_id)
    if from_date:
        statement = statement.where(DailyPrice.trade_date >= from_date)
    if to_date:
        statement = statement.where(DailyPrice.trade_date <= to_date)
    items = session.scalars(
        statement.order_by(DailyPrice.trade_date.desc()).limit(limit)
    ).all()
    return list(reversed(items))


def list_scanner_runs(
    session: Session,
    *,
    status: str | None,
    from_date: date | None,
    to_date: date | None,
    limit: int,
    offset: int,
) -> tuple[list[ScannerRun], int]:
    filters = []
    if status:
        filters.append(ScannerRun.status == status)
    if from_date:
        filters.append(ScannerRun.data_date >= from_date)
    if to_date:
        filters.append(ScannerRun.data_date <= to_date)

    total = (
        session.scalar(select(func.count()).select_from(ScannerRun).where(*filters))
        or 0
    )
    items = session.scalars(
        select(ScannerRun)
        .where(*filters)
        .order_by(ScannerRun.started_at.desc(), ScannerRun.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), total


def signal_statement() -> Select[tuple[TechnicalSignal, Stock, SignalDefinition]]:
    return (
        select(TechnicalSignal, Stock, SignalDefinition)
        .join(Stock, TechnicalSignal.stock_id == Stock.id)
        .join(
            SignalDefinition,
            TechnicalSignal.signal_definition_id == SignalDefinition.id,
        )
    )


def list_signals(
    session: Session,
    *,
    scanner_run_id: UUID | None,
    stock_id: int | None,
    signal_code: str | None,
    from_date: date | None,
    to_date: date | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[TechnicalSignal, Stock, SignalDefinition]], int]:
    filters = []
    if scanner_run_id:
        filters.append(TechnicalSignal.scanner_run_id == scanner_run_id)
    if stock_id:
        filters.append(TechnicalSignal.stock_id == stock_id)
    if signal_code:
        filters.append(SignalDefinition.code == signal_code)
    if from_date:
        filters.append(TechnicalSignal.signal_date >= from_date)
    if to_date:
        filters.append(TechnicalSignal.signal_date <= to_date)

    total = (
        session.scalar(
            select(func.count())
            .select_from(TechnicalSignal)
            .join(
                SignalDefinition,
                TechnicalSignal.signal_definition_id == SignalDefinition.id,
            )
            .where(*filters)
        )
        or 0
    )
    rows = (
        session.execute(
            signal_statement()
            .where(*filters)
            .order_by(
                TechnicalSignal.signal_date.desc(),
                Stock.symbol,
                SignalDefinition.code,
                TechnicalSignal.id,
            )
            .offset(offset)
            .limit(limit)
        )
        .tuples()
        .all()
    )
    return list(rows), total


def list_research_notes(
    session: Session,
    *,
    stock_id: int,
    limit: int,
    offset: int,
) -> tuple[list[ResearchNote], int]:
    filters = [ResearchNote.stock_id == stock_id]
    total = (
        session.scalar(select(func.count()).select_from(ResearchNote).where(*filters))
        or 0
    )
    items = session.scalars(
        select(ResearchNote)
        .where(*filters)
        .order_by(ResearchNote.created_at.desc(), ResearchNote.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), total
