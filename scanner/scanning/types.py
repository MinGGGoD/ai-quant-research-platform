from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID

StockKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ScanStock:
    id: int
    exchange: str
    symbol: str

    @property
    def key(self) -> StockKey:
        return self.exchange, self.symbol


@dataclass(frozen=True, slots=True)
class ScanSummary:
    run_id: UUID
    status: str
    data_date: date
    universe_name: str
    total_stocks: int
    processed_stocks: int
    matched_stocks: int
    detected_signals: int
    warning_count: int
    signal_counts: dict[str, int]
    warning_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_id"] = str(self.run_id)
        payload["data_date"] = self.data_date.isoformat()
        return payload
