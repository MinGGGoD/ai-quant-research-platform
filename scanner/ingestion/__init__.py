"""Market data ingestion interfaces and implementations."""

from scanner.ingestion.csv_provider import CsvMarketDataProvider
from scanner.ingestion.errors import (
    IngestionPersistenceError,
    IngestionValidationError,
    ValidationIssue,
)
from scanner.ingestion.service import ingest_market_data
from scanner.ingestion.types import (
    DailyPriceRecord,
    IngestionSummary,
    IngestionWarning,
    MarketDataBatch,
    MarketDataProvider,
    StockRecord,
)

__all__ = [
    "CsvMarketDataProvider",
    "DailyPriceRecord",
    "IngestionPersistenceError",
    "IngestionSummary",
    "IngestionValidationError",
    "IngestionWarning",
    "MarketDataBatch",
    "MarketDataProvider",
    "StockRecord",
    "ValidationIssue",
    "ingest_market_data",
]
