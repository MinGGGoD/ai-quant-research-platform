import argparse
from datetime import date
from uuid import UUID

import pytest

from scanner import cli
from scanner.cli import main
from scanner.scanning import ScanSummary


def test_scanner_help_text(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AI Quant Research Platform scanner." in captured.out
    assert "Detect and store deterministic technical signals." in captured.out
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


def test_scan_command_returns_structured_summary(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_arguments: dict[str, object] = {}

    def fake_run_scan(
        data_date: object,
        **kwargs: object,
    ) -> ScanSummary:
        captured_arguments["data_date"] = data_date
        captured_arguments.update(kwargs)
        return ScanSummary(
            run_id=UUID("2f269155-7d7b-471a-a57e-ec7da86f594b"),
            status="completed",
            data_date=date(2026, 6, 12),
            universe_name="selected_stocks",
            total_stocks=1,
            processed_stocks=1,
            matched_stocks=1,
            detected_signals=1,
            warning_count=0,
            signal_counts={"recent_breakout": 1},
            warning_counts={"recent_breakout": 0},
        )

    monkeypatch.setattr(cli, "run_scan", fake_run_scan)

    exit_code = main(
        [
            "scan",
            "--data-date",
            "2026-06-12",
            "--stock",
            "000001.SZ",
            "--signal",
            "recent_breakout",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_arguments["stock_keys"] == (("SZSE", "000001"),)
    assert captured_arguments["signal_codes"] == ("recent_breakout",)
    assert '"status": "completed"' in captured.out
    assert '"detected_signals": 1' in captured.out


def test_parse_stock_code_rejects_unsupported_format() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli.parse_stock_code("000001.SSE")
