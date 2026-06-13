import pytest

from scanner import cli
from scanner.cli import main


def test_scanner_help_text(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AI Quant Research Platform scanner." in captured.out
    assert "scanning begins in Phase 4." in captured.out
    assert "ingest-csv" in captured.out


def test_ingest_csv_reports_validation_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "ingest-csv",
            "--stocks-file",
            "missing-stocks.csv",
            "--prices-file",
            "missing-prices.csv",
            "--source",
            "test_source",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert '"status": "validation_failed"' in captured.err
    assert captured.err.count('"code": "file_error"') == 2


def test_ingest_asharehub_requires_api_key(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SettingsWithoutKey:
        asharehub_api_key = None

    monkeypatch.setattr(cli, "get_settings", SettingsWithoutKey)

    exit_code = main(
        [
            "ingest-asharehub",
            "--start-date",
            "2026-06-12",
            "--end-date",
            "2026-06-12",
            "--ts-code",
            "000001.SZ",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "AQR_ASHAREHUB_API_KEY is required" in captured.err
