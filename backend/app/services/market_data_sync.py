from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.database import DailyPrice, DailyPriceSyncRange, Stock
from scanner.ingestion.asharehub_provider import ASHAREHUB_SOURCE
from scanner.ingestion.repository import PersistenceStats, upsert_market_data
from scanner.ingestion.types import MarketDataBatch, StockRecord

MAX_SYNC_RANGE_DAYS = 1096
# AShareHub documents SSE/SZSE calendars; BSE follows the mainland session dates.
CALENDAR_EXCHANGE = {"SSE": "SSE", "SZSE": "SZSE", "BSE": "SSE"}


class MarketDataHistoryProvider(Protocol):
    def load_open_dates(
        self,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> tuple[date, ...]: ...

    def load_prices(
        self,
        stock: StockRecord,
        start_date: date,
        end_date: date,
    ) -> MarketDataBatch: ...


class MarketDataProviderUnavailableError(RuntimeError):
    """Raised when missing history requires an unconfigured provider."""


@dataclass(frozen=True, slots=True)
class DateRange:
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class PriceHistorySyncResult:
    requested_range: DateRange
    effective_range: DateRange | None
    cache_hit: bool
    fetched_ranges: tuple[DateRange, ...]
    prices_inserted: int
    prices_updated: int


def group_missing_sessions(
    open_dates: tuple[date, ...],
    available_dates: set[date],
) -> tuple[DateRange, ...]:
    missing_indexes = [
        index
        for index, trade_date in enumerate(open_dates)
        if trade_date not in available_dates
    ]
    if not missing_indexes:
        return ()

    ranges: list[DateRange] = []
    range_start = missing_indexes[0]
    previous = missing_indexes[0]
    for index in missing_indexes[1:]:
        if index != previous + 1:
            ranges.append(
                DateRange(
                    start_date=open_dates[range_start],
                    end_date=open_dates[previous],
                )
            )
            range_start = index
        previous = index
    ranges.append(
        DateRange(
            start_date=open_dates[range_start],
            end_date=open_dates[previous],
        )
    )
    return tuple(ranges)


def range_is_covered(
    ranges: tuple[DateRange, ...],
    start_date: date,
    end_date: date,
) -> bool:
    cursor = start_date
    for item in sorted(ranges, key=lambda value: value.start_date):
        if item.end_date < cursor:
            continue
        if item.start_date > cursor:
            return False
        cursor = max(cursor, item.end_date + timedelta(days=1))
        if cursor > end_date:
            return True
    return cursor > end_date


def sync_stock_price_history(
    session: Session,
    *,
    stock: Stock,
    from_date: date,
    to_date: date,
    provider: MarketDataHistoryProvider | None,
    today: date | None = None,
) -> PriceHistorySyncResult:
    if from_date > to_date:
        raise ValueError("from_date must not be later than to_date")
    if (to_date - from_date).days + 1 > MAX_SYNC_RANGE_DAYS:
        raise ValueError(
            f"price history synchronization is limited to {MAX_SYNC_RANGE_DAYS} days"
        )

    current_date = today or date.today()
    if to_date > current_date:
        raise ValueError("to_date must not be later than today")

    effective_start = max(from_date, stock.list_date or from_date)
    effective_end = min(to_date, stock.delist_date or to_date)
    requested_range = DateRange(from_date, to_date)
    if effective_start > effective_end:
        return PriceHistorySyncResult(
            requested_range=requested_range,
            effective_range=None,
            cache_hit=True,
            fetched_ranges=(),
            prices_inserted=0,
            prices_updated=0,
        )

    effective_range = DateRange(effective_start, effective_end)
    coverage = _coverage_ranges(
        session,
        stock_id=stock.id,
        start_date=effective_start,
        end_date=effective_end,
    )
    if range_is_covered(coverage, effective_start, effective_end):
        return PriceHistorySyncResult(
            requested_range=requested_range,
            effective_range=effective_range,
            cache_hit=True,
            fetched_ranges=(),
            prices_inserted=0,
            prices_updated=0,
        )
    if provider is None:
        raise MarketDataProviderUnavailableError(
            "AShareHub price synchronization is not configured."
        )

    open_dates = provider.load_open_dates(
        CALENDAR_EXCHANGE[stock.exchange],
        effective_start,
        effective_end,
    )
    stored_dates = set(
        session.scalars(
            select(DailyPrice.trade_date).where(
                DailyPrice.stock_id == stock.id,
                DailyPrice.trade_date >= effective_start,
                DailyPrice.trade_date <= effective_end,
            )
        ).all()
    )
    covered_dates = {
        trade_date
        for trade_date in open_dates
        if any(item.start_date <= trade_date <= item.end_date for item in coverage)
    }
    missing_ranges = group_missing_sessions(
        open_dates,
        stored_dates | covered_dates,
    )

    stock_record = StockRecord(
        symbol=stock.symbol,
        exchange=stock.exchange,
        name=stock.name,
        list_date=stock.list_date,
        delist_date=stock.delist_date,
        status=stock.status,
    )
    batches = [
        provider.load_prices(
            stock_record,
            item.start_date,
            item.end_date,
        )
        for item in missing_ranges
    ]
    combined_batch = MarketDataBatch(
        stocks=(stock_record,),
        daily_prices=tuple(price for batch in batches for price in batch.daily_prices),
        warnings=tuple(warning for batch in batches for warning in batch.warnings),
    )
    fetched_dates = {price.trade_date for price in combined_batch.daily_prices}

    try:
        stats = (
            upsert_market_data(session, combined_batch)
            if batches
            else PersistenceStats(0, 0, 0, 0)
        )
        current_date_complete = (
            current_date not in open_dates
            or current_date in stored_dates
            or current_date in fetched_dates
        )
        completed_end = min(
            effective_end,
            current_date if current_date_complete else current_date - timedelta(days=1),
        )
        if effective_start <= completed_end:
            _store_merged_coverage(
                session,
                stock_id=stock.id,
                start_date=effective_start,
                end_date=completed_end,
            )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return PriceHistorySyncResult(
        requested_range=requested_range,
        effective_range=effective_range,
        cache_hit=not missing_ranges,
        fetched_ranges=missing_ranges,
        prices_inserted=stats.prices_inserted,
        prices_updated=stats.prices_updated,
    )


def _coverage_ranges(
    session: Session,
    *,
    stock_id: int,
    start_date: date,
    end_date: date,
) -> tuple[DateRange, ...]:
    rows = session.execute(
        select(DailyPriceSyncRange.start_date, DailyPriceSyncRange.end_date).where(
            DailyPriceSyncRange.stock_id == stock_id,
            DailyPriceSyncRange.source == ASHAREHUB_SOURCE,
            DailyPriceSyncRange.end_date >= start_date,
            DailyPriceSyncRange.start_date <= end_date,
        )
    ).tuples()
    return tuple(DateRange(start, end) for start, end in rows)


def _store_merged_coverage(
    session: Session,
    *,
    stock_id: int,
    start_date: date,
    end_date: date,
) -> None:
    adjacent_start = start_date - timedelta(days=1)
    adjacent_end = end_date + timedelta(days=1)
    overlapping = session.execute(
        select(
            DailyPriceSyncRange.id,
            DailyPriceSyncRange.start_date,
            DailyPriceSyncRange.end_date,
        ).where(
            DailyPriceSyncRange.stock_id == stock_id,
            DailyPriceSyncRange.source == ASHAREHUB_SOURCE,
            DailyPriceSyncRange.end_date >= adjacent_start,
            DailyPriceSyncRange.start_date <= adjacent_end,
        )
    ).tuples()
    rows = list(overlapping)
    if rows:
        start_date = min(start_date, *(row[1] for row in rows))
        end_date = max(end_date, *(row[2] for row in rows))
        session.execute(
            delete(DailyPriceSyncRange).where(
                DailyPriceSyncRange.id.in_(row[0] for row in rows)
            )
        )
    session.add(
        DailyPriceSyncRange(
            stock_id=stock_id,
            source=ASHAREHUB_SOURCE,
            start_date=start_date,
            end_date=end_date,
        )
    )
