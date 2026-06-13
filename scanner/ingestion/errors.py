from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    file: str
    row: int | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IngestionValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(f"Market data validation failed with {len(issues)} issue(s)")


class IngestionPersistenceError(RuntimeError):
    """Raised when a validated batch cannot be persisted safely."""


class MarketDataProviderError(RuntimeError):
    """Raised when a remote market-data provider cannot return a complete batch."""
