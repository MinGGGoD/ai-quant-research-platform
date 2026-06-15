from datetime import date

from backend.app.services.market_data_sync import (
    DateRange,
    group_missing_sessions,
    range_is_covered,
)


def test_groups_only_consecutive_missing_trade_sessions() -> None:
    open_dates = (
        date(2026, 6, 8),
        date(2026, 6, 9),
        date(2026, 6, 10),
        date(2026, 6, 11),
        date(2026, 6, 12),
        date(2026, 6, 15),
    )

    ranges = group_missing_sessions(
        open_dates,
        {
            date(2026, 6, 9),
            date(2026, 6, 12),
        },
    )

    assert ranges == (
        DateRange(date(2026, 6, 8), date(2026, 6, 8)),
        DateRange(date(2026, 6, 10), date(2026, 6, 11)),
        DateRange(date(2026, 6, 15), date(2026, 6, 15)),
    )


def test_range_coverage_merges_overlapping_and_adjacent_ranges() -> None:
    ranges = (
        DateRange(date(2026, 6, 1), date(2026, 6, 5)),
        DateRange(date(2026, 6, 6), date(2026, 6, 10)),
    )

    assert range_is_covered(ranges, date(2026, 6, 2), date(2026, 6, 9))
    assert not range_is_covered(ranges, date(2026, 5, 31), date(2026, 6, 9))
    assert not range_is_covered(ranges, date(2026, 6, 2), date(2026, 6, 11))
