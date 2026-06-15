from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class PriceBar:
    trade_date: date
    high: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class SignalMatch:
    signal_date: date
    matched_values: dict[str, Any]
    explanation: str


@dataclass(frozen=True, slots=True)
class SignalEvaluation:
    status: Literal["matched", "not_matched", "insufficient_data"]
    match: SignalMatch | None = None
    warning: str | None = None

    @property
    def was_evaluated(self) -> bool:
        return self.status != "insufficient_data"


@dataclass(frozen=True, slots=True)
class SignalRule:
    code: str
    version: int
    name: str
    description: str
    parameters: dict[str, Any]
    required_bars: int

    def evaluate(
        self,
        history: tuple[PriceBar, ...],
        data_date: date,
    ) -> SignalEvaluation:
        from scanner.signals.rules import evaluate_rule

        return evaluate_rule(self, history, data_date)
