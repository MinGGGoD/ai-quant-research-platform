from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from backend.app.api import routes
from backend.app.config import Settings
from scanner.ingestion import AShareHubHistoryClient, BaoStockHistoryClient


def configured_provider(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> tuple[
    AShareHubHistoryClient | BaoStockHistoryClient | None,
    Iterator[AShareHubHistoryClient | BaoStockHistoryClient | None],
]:
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    dependency = routes.configured_market_data_history_provider()
    return next(dependency), dependency


def close_dependency(
    dependency: Iterator[AShareHubHistoryClient | BaoStockHistoryClient | None],
) -> None:
    with pytest.raises(StopIteration):
        next(dependency)


def test_auto_provider_uses_baostock_without_asharehub_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, dependency = configured_provider(
        monkeypatch,
        Settings(
            market_data_provider="auto",
            asharehub_api_key=None,
        ),
    )
    try:
        assert isinstance(provider, BaoStockHistoryClient)
    finally:
        close_dependency(dependency)


def test_auto_provider_prefers_asharehub_when_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, dependency = configured_provider(
        monkeypatch,
        Settings(
            market_data_provider="auto",
            asharehub_api_key=SecretStr("test-key"),
        ),
    )
    try:
        assert isinstance(provider, AShareHubHistoryClient)
    finally:
        close_dependency(dependency)


def test_explicit_asharehub_provider_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, dependency = configured_provider(
        monkeypatch,
        Settings(
            market_data_provider="asharehub",
            asharehub_api_key=None,
        ),
    )
    try:
        assert provider is None
    finally:
        close_dependency(dependency)
