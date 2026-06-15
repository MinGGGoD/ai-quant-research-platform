from __future__ import annotations

from statistics import fmean
from uuid import UUID

from sqlalchemy.orm import Session

from ai import (
    PROMPT_VERSION,
    PriceSummary,
    ResearchNoteContext,
    ResearchNoteGenerator,
    SignalObservation,
    StockResearchContext,
    validate_generated_content,
)
from backend.app.api.repository import list_prices, list_signals
from backend.app.database import ResearchNote, Stock


class ResearchContextUnavailableError(ValueError):
    """Raised when stored data is insufficient for a research note."""


def build_research_context(
    session: Session,
    *,
    stock: Stock,
    scanner_run_id: UUID | None,
    price_window: int,
    signal_limit: int,
) -> ResearchNoteContext:
    prices = list_prices(
        session,
        stock_id=stock.id,
        from_date=None,
        to_date=None,
        limit=price_window,
    )
    if not prices:
        raise ResearchContextUnavailableError(
            "At least one daily price record is required for note generation."
        )

    first_price = prices[0]
    latest_price = prices[-1]
    first_close = float(first_price.close)
    latest_close = float(latest_price.close)
    close_change_percent = None
    if len(prices) > 1 and first_close != 0:
        close_change_percent = round(
            ((latest_close - first_close) / first_close) * 100,
            4,
        )

    signal_rows, _ = list_signals(
        session,
        scanner_run_id=scanner_run_id,
        stock_id=stock.id,
        signal_code=None,
        from_date=None,
        to_date=None,
        limit=signal_limit,
        offset=0,
    )
    observations = tuple(
        SignalObservation(
            id=str(signal.id),
            scanner_run_id=str(signal.scanner_run_id),
            signal_date=signal.signal_date.isoformat(),
            code=definition.code,
            version=definition.version,
            name=definition.name,
            matched_values=signal.matched_values,
            explanation=signal.explanation,
        )
        for signal, _, definition in signal_rows
    )

    return ResearchNoteContext(
        stock=StockResearchContext(
            symbol=stock.symbol,
            exchange=stock.exchange,
            name=stock.name,
            status=stock.status,
            list_date=stock.list_date.isoformat() if stock.list_date else None,
        ),
        price_summary=PriceSummary(
            record_count=len(prices),
            start_date=first_price.trade_date.isoformat(),
            end_date=latest_price.trade_date.isoformat(),
            first_close=first_close,
            latest_close=latest_close,
            close_change_percent=close_change_percent,
            period_high=max(float(price.high) for price in prices),
            period_low=min(float(price.low) for price in prices),
            average_volume=round(fmean(price.volume for price in prices), 2),
            sources=tuple(sorted({price.source for price in prices})),
        ),
        technical_signals=observations,
        scanner_run_id=str(scanner_run_id) if scanner_run_id else None,
    )


def generate_and_store_research_note(
    session: Session,
    *,
    stock: Stock,
    scanner_run_id: UUID | None,
    price_window: int,
    signal_limit: int,
    max_output_characters: int,
    generator: ResearchNoteGenerator,
) -> ResearchNote:
    stock_id = stock.id
    stock_symbol = stock.symbol
    context = build_research_context(
        session,
        stock=stock,
        scanner_run_id=scanner_run_id,
        price_window=price_window,
        signal_limit=signal_limit,
    )
    # Release the read transaction before waiting on the external model provider.
    session.rollback()
    generated = generator.generate(context)
    content = validate_generated_content(
        generated.content,
        max_characters=max_output_characters,
    )

    note = ResearchNote(
        stock_id=stock_id,
        scanner_run_id=scanner_run_id,
        title=(
            f"Research observations for {stock_symbol} "
            f"through {context.price_summary.end_date}"
        ),
        content=content,
        source_type="ai_generated",
        model_name=generated.model_name,
        prompt_version=PROMPT_VERSION,
        generation_metadata={
            "context": context.to_dict(),
            "generation": generated.provider_metadata,
            "limits": {
                "price_window": price_window,
                "signal_limit": signal_limit,
                "max_output_characters": max_output_characters,
            },
        },
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return note
