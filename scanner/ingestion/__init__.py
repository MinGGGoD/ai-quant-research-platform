"""Market data ingestion interfaces and implementations."""

from scanner.ingestion.asharehub_provider import (
    AShareHubHistoryClient,
    AShareHubMarketDataProvider,
)
from scanner.ingestion.csv_provider import CsvMarketDataProvider
from scanner.ingestion.errors import (
    IngestionPersistenceError,
    IngestionValidationError,
    MarketDataProviderError,
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
    "AShareHubMarketDataProvider",
    "AShareHubHistoryClient",
    "CsvMarketDataProvider",
    "DailyPriceRecord",
    "IngestionPersistenceError",
    "IngestionSummary",
    "IngestionValidationError",
    "IngestionWarning",
    "MarketDataProviderError",
    "MarketDataBatch",
    "MarketDataProvider",
    "StockRecord",
    "ValidationIssue",
    "ingest_market_data",
]
