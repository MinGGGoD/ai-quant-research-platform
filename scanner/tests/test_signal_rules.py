from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest

from scanner.signals import RULES_BY_CODE, PriceBar

DATA_DATE = date(2026, 6, 12)


def make_history(
    closes: Sequence[int | str],
    *,
    highs: Sequence[int | str] | None = None,
    volumes: Sequence[int] | None = None,
) -> tuple[PriceBar, ...]:
    start_date = DATA_DATE - timedelta(days=len(closes) - 1)
    resolved_highs = highs or closes
    resolved_volumes = volumes or [100] * len(closes)
    return tuple(
        PriceBar(
            trade_date=start_date + timedelta(days=index),
            high=Decimal(str(resolved_highs[index])),
            close=Decimal(str(close)),
            volume=resolved_volumes[index],
        )
        for index, close in enumerate(closes)
    )


@pytest.mark.parametrize(
    ("closes", "direction"),
    [
        ([10] * 15 + [9] * 5 + [20], "above"),
        ([10] * 15 + [11] * 5 + [0], "below"),
    ],
)
def test_moving_average_cross_detects_both_directions(
    closes: list[int],
    direction: str,
) -> None:
    evaluation = RULES_BY_CODE["moving_average_cross"].evaluate(
        make_history(closes),
        DATA_DATE,
    )

    assert evaluation.status == "matched"
    assert evaluation.match is not None
    assert evaluation.match.matched_values["direction"] == direction
    assert "research" in evaluation.match.explanation


def test_moving_average_cross_reports_non_match() -> None:
    evaluation = RULES_BY_CODE["moving_average_cross"].evaluate(
        make_history([10] * 21),
        DATA_DATE,
    )

    assert evaluation.status == "not_matched"
    assert evaluation.match is None


def test_recent_breakout_uses_previous_sessions_and_strict_boundary() -> None:
    matching = RULES_BY_CODE["recent_breakout"].evaluate(
        make_history(
            [10] * 20 + ["10.01"],
            highs=[10] * 20 + ["10.20"],
        ),
        DATA_DATE,
    )
    boundary = RULES_BY_CODE["recent_breakout"].evaluate(
        make_history([10] * 21, highs=[10] * 21),
        DATA_DATE,
    )

    assert matching.status == "matched"
    assert matching.match is not None
    assert matching.match.matched_values["previous_high"] == 10.0
    assert boundary.status == "not_matched"


def test_volume_spike_matches_at_threshold_and_rejects_zero_baseline() -> None:
    matching = RULES_BY_CODE["volume_spike"].evaluate(
        make_history([10] * 21, volumes=[100] * 20 + [200]),
        DATA_DATE,
    )
    below_threshold = RULES_BY_CODE["volume_spike"].evaluate(
        make_history([10] * 21, volumes=[100] * 20 + [199]),
        DATA_DATE,
    )
    zero_baseline = RULES_BY_CODE["volume_spike"].evaluate(
        make_history([10] * 21, volumes=[0] * 20 + [100]),
        DATA_DATE,
    )

    assert matching.status == "matched"
    assert matching.match is not None
    assert matching.match.matched_values["volume_ratio"] == 2.0
    assert below_threshold.status == "not_matched"
    assert zero_baseline.status == "not_matched"


@pytest.mark.parametrize("signal_code", tuple(RULES_BY_CODE))
def test_rules_report_insufficient_history(signal_code: str) -> None:
    evaluation = RULES_BY_CODE[signal_code].evaluate(
        make_history([10] * 20),
        DATA_DATE,
    )

    assert evaluation.status == "insufficient_data"
    assert evaluation.warning is not None
    assert "requires 21 daily bars" in evaluation.warning


@pytest.mark.parametrize("signal_code", tuple(RULES_BY_CODE))
def test_rules_require_a_price_on_the_evaluated_date(signal_code: str) -> None:
    evaluation = RULES_BY_CODE[signal_code].evaluate(
        make_history([10] * 21),
        DATA_DATE + timedelta(days=1),
    )

    assert evaluation.status == "insufficient_data"
    assert evaluation.warning == "No daily price is available on 2026-06-13."
