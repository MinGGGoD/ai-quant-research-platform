import pytest

from scanner.cli import main


def test_scanner_help_text(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AI Quant Research Platform scanner." in captured.out
    assert "Phase 4." in captured.out
