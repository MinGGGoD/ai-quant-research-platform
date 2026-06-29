import random
from datetime import date, timedelta
from decimal import Decimal

from backend.app.services.chan_analysis import (
    CHAN_ALGORITHM_CODE,
    ChanBar,
    analyze_chan_structure,
)


def make_bar(
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> ChanBar:
    return ChanBar(
        index=index,
        trade_date=date(2025, 1, 1) + timedelta(days=index),
        timestamp=None,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal("1000"),
    )


def make_chan_py_fixture(seed: int = 1, count: int = 220) -> tuple[ChanBar, ...]:
    rng = random.Random(seed)
    price = 50.0
    bars: list[ChanBar] = []
    for index in range(count):
        drift = (1 if (index // 7) % 2 == 0 else -1) * rng.uniform(0.4, 2.5)
        price = max(5, price + drift + rng.uniform(-1.5, 1.5))
        spread = rng.uniform(0.6, 2.0)
        open_ = price + rng.uniform(-0.8, 0.8)
        close = price + rng.uniform(-0.8, 0.8)
        high = max(open_, close, price) + spread
        low = min(open_, close, price) - spread
        bars.append(
            make_bar(
                index,
                round(open_, 2),
                round(high, 2),
                round(low, 2),
                round(close, 2),
            )
        )
    return tuple(bars)


def test_chan_analysis_uses_vendored_chan_py_rules() -> None:
    analysis = analyze_chan_structure(make_chan_py_fixture())

    assert CHAN_ALGORITHM_CODE == "vespa314_chan_py"
    assert len(analysis.fractals) >= 40
    assert len(analysis.strokes) >= 20
    assert len(analysis.segments) >= 5
    assert len(analysis.centers) >= 2

    observation_kinds = {observation.kind for observation in analysis.observations}
    assert {"S1", "S2", "S2S", "B1", "B2"}.issubset(observation_kinds)
    assert {observation.side for observation in analysis.observations} == {
        "buy",
        "sell",
    }

    first_stroke = analysis.strokes[0]
    assert first_stroke.direction in {"up", "down"}
    assert first_stroke.price_low < first_stroke.price_high

    first_center = analysis.centers[0]
    assert first_center.price_low <= first_center.price_high
    assert first_center.stroke_indexes


def test_chan_analysis_returns_empty_result_for_short_series() -> None:
    analysis = analyze_chan_structure(
        (
            make_bar(0, 10, 11, 9, 10),
            make_bar(1, 11, 12, 10, 11),
        )
    )

    assert analysis.fractals == ()
    assert analysis.strokes == ()
    assert analysis.segments == ()
    assert analysis.centers == ()
    assert analysis.observations == ()
