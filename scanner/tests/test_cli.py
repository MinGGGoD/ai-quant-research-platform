import pytest

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
