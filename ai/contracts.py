from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class StockResearchContext:
    symbol: str
    exchange: str
    name: str
    status: str
    list_date: str | None


@dataclass(frozen=True)
class PriceSummary:
    record_count: int
    start_date: str
    end_date: str
    first_close: float
    latest_close: float
    close_change_percent: float | None
    period_high: float
    period_low: float
    average_volume: float
    sources: tuple[str, ...]


@dataclass(frozen=True)
class SignalObservation:
    id: str
    scanner_run_id: str
    signal_date: str
    code: str
    version: int
    name: str
    matched_values: dict[str, Any]
    explanation: str


@dataclass(frozen=True)
class ResearchNoteContext:
    stock: StockResearchContext
    price_summary: PriceSummary
    technical_signals: tuple[SignalObservation, ...]
    scanner_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeneratedResearchNote:
    content: str
    model_name: str
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class ResearchNoteGenerator(Protocol):
    def generate(self, context: ResearchNoteContext) -> GeneratedResearchNote:
        """Generate a neutral note from approved stored research context."""
