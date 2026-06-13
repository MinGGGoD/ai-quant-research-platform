from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import SessionLocal
from scanner.ingestion.repository import upsert_market_data
from scanner.ingestion.types import (
    IngestionSummary,
    MarketDataProvider,
)


def ingest_market_data(
    provider: MarketDataProvider,
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> IngestionSummary:
    batch = provider.load()

    with session_factory() as session:
        try:
            stats = upsert_market_data(session, batch)
            session.commit()
        except Exception:
            session.rollback()
            raise

    return IngestionSummary(
        stocks_inserted=stats.stocks_inserted,
        stocks_updated=stats.stocks_updated,
        prices_inserted=stats.prices_inserted,
        prices_updated=stats.prices_updated,
        warnings=batch.warnings,
    )
