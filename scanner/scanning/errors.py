from uuid import UUID


class ScanConfigurationError(ValueError):
    """Raised when a requested scan configuration is unsupported."""


class ScanExecutionError(RuntimeError):
    """Raised after a persisted scanner run fails."""

    def __init__(self, run_id: UUID, message: str) -> None:
        self.run_id = run_id
        super().__init__(message)
