from collections.abc import Callable
from datetime import date
from decimal import Decimal

from scanner.signals.types import (
    PriceBar,
    SignalEvaluation,
    SignalMatch,
    SignalRule,
)

SHORT_MA_WINDOW = 5
LONG_MA_WINDOW = 20
BREAKOUT_LOOKBACK = 20
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = Decimal("2")


def _moving_average(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, start=Decimal()) / Decimal(len(values))


def _rounded_float(value: Decimal) -> float:
    return float(round(value, 6))


def _insufficient_data(
    rule: SignalRule,
    history: tuple[PriceBar, ...],
    data_date: date,
) -> SignalEvaluation | None:
    if not history or history[-1].trade_date != data_date:
        return SignalEvaluation(
            status="insufficient_data",
            warning=f"No daily price is available on {data_date.isoformat()}.",
        )
    if len(history) < rule.required_bars:
        return SignalEvaluation(
            status="insufficient_data",
            warning=(
                f"{rule.code} requires {rule.required_bars} daily bars; "
                f"{len(history)} available through {data_date.isoformat()}."
            ),
        )
    return None


def _evaluate_moving_average_cross(
    rule: SignalRule,
    history: tuple[PriceBar, ...],
    data_date: date,
) -> SignalEvaluation:
    insufficient = _insufficient_data(rule, history, data_date)
    if insufficient is not None:
        return insufficient

    closes = tuple(bar.close for bar in history)
    previous_short = _moving_average(closes[-(SHORT_MA_WINDOW + 1) : -1])
    previous_long = _moving_average(closes[-(LONG_MA_WINDOW + 1) : -1])
    current_short = _moving_average(closes[-SHORT_MA_WINDOW:])
    current_long = _moving_average(closes[-LONG_MA_WINDOW:])

    direction: str | None = None
    if previous_short <= previous_long and current_short > current_long:
        direction = "above"
    elif previous_short >= previous_long and current_short < current_long:
        direction = "below"

    if direction is None:
        return SignalEvaluation(status="not_matched")

    return SignalEvaluation(
        status="matched",
        match=SignalMatch(
            signal_date=data_date,
            matched_values={
                "direction": direction,
                "short_window": SHORT_MA_WINDOW,
                "long_window": LONG_MA_WINDOW,
                "previous_short_ma": _rounded_float(previous_short),
                "previous_long_ma": _rounded_float(previous_long),
                "current_short_ma": _rounded_float(current_short),
                "current_long_ma": _rounded_float(current_long),
            },
            explanation=(
                f"The {SHORT_MA_WINDOW}-day moving average crossed {direction} "
                f"the {LONG_MA_WINDOW}-day moving average on the evaluated date. "
                "This is a descriptive technical signal for research."
            ),
        ),
    )


def _evaluate_recent_breakout(
    rule: SignalRule,
    history: tuple[PriceBar, ...],
    data_date: date,
) -> SignalEvaluation:
    insufficient = _insufficient_data(rule, history, data_date)
    if insufficient is not None:
        return insufficient

    current = history[-1]
    previous_high = max(bar.high for bar in history[-(BREAKOUT_LOOKBACK + 1) : -1])
    if current.close <= previous_high:
        return SignalEvaluation(status="not_matched")

    return SignalEvaluation(
        status="matched",
        match=SignalMatch(
            signal_date=data_date,
            matched_values={
                "lookback_sessions": BREAKOUT_LOOKBACK,
                "current_close": _rounded_float(current.close),
                "previous_high": _rounded_float(previous_high),
            },
            explanation=(
                f"The closing price was above the highest price from the previous "
                f"{BREAKOUT_LOOKBACK} trading sessions. This is a descriptive "
                "technical signal for research."
            ),
        ),
    )


def _evaluate_volume_spike(
    rule: SignalRule,
    history: tuple[PriceBar, ...],
    data_date: date,
) -> SignalEvaluation:
    insufficient = _insufficient_data(rule, history, data_date)
    if insufficient is not None:
        return insufficient

    current = history[-1]
    previous_volumes = history[-(VOLUME_LOOKBACK + 1) : -1]
    average_volume = Decimal(sum(bar.volume for bar in previous_volumes)) / Decimal(
        VOLUME_LOOKBACK
    )
    if average_volume <= 0:
        return SignalEvaluation(status="not_matched")

    threshold = average_volume * VOLUME_MULTIPLIER
    if Decimal(current.volume) < threshold:
        return SignalEvaluation(status="not_matched")

    volume_ratio = Decimal(current.volume) / average_volume
    return SignalEvaluation(
        status="matched",
        match=SignalMatch(
            signal_date=data_date,
            matched_values={
                "lookback_sessions": VOLUME_LOOKBACK,
                "multiplier": _rounded_float(VOLUME_MULTIPLIER),
                "current_volume": current.volume,
                "average_previous_volume": _rounded_float(average_volume),
                "volume_ratio": _rounded_float(volume_ratio),
            },
            explanation=(
                f"Trading volume was at least {_rounded_float(VOLUME_MULTIPLIER)} "
                f"times the average of the previous {VOLUME_LOOKBACK} trading "
                "sessions. This is a descriptive technical signal for research."
            ),
        ),
    )


MOVING_AVERAGE_CROSS = SignalRule(
    code="moving_average_cross",
    version=1,
    name="Moving Average Cross",
    description=(
        "Detects when the 5-day moving average crosses above or below the 20-day "
        "moving average on the evaluated date."
    ),
    parameters={
        "short_window": SHORT_MA_WINDOW,
        "long_window": LONG_MA_WINDOW,
        "directions": ["above", "below"],
    },
    required_bars=LONG_MA_WINDOW + 1,
)

RECENT_BREAKOUT = SignalRule(
    code="recent_breakout",
    version=1,
    name="Recent Price Breakout",
    description=(
        "Detects when the evaluated closing price is strictly above the highest "
        "price from the previous 20 trading sessions."
    ),
    parameters={
        "lookback_sessions": BREAKOUT_LOOKBACK,
        "comparison": "close_above_previous_high",
    },
    required_bars=BREAKOUT_LOOKBACK + 1,
)

VOLUME_SPIKE = SignalRule(
    code="volume_spike",
    version=1,
    name="Volume Spike",
    description=(
        "Detects when evaluated trading volume is at least twice the average "
        "volume from the previous 20 trading sessions."
    ),
    parameters={
        "lookback_sessions": VOLUME_LOOKBACK,
        "multiplier": float(VOLUME_MULTIPLIER),
    },
    required_bars=VOLUME_LOOKBACK + 1,
)

DEFAULT_RULES = (
    MOVING_AVERAGE_CROSS,
    RECENT_BREAKOUT,
    VOLUME_SPIKE,
)
RULES_BY_CODE = {rule.code: rule for rule in DEFAULT_RULES}

RuleEvaluator = Callable[
    [SignalRule, tuple[PriceBar, ...], date],
    SignalEvaluation,
]
EVALUATORS: dict[str, RuleEvaluator] = {
    MOVING_AVERAGE_CROSS.code: _evaluate_moving_average_cross,
    RECENT_BREAKOUT.code: _evaluate_recent_breakout,
    VOLUME_SPIKE.code: _evaluate_volume_spike,
}


def evaluate_rule(
    rule: SignalRule,
    history: tuple[PriceBar, ...],
    data_date: date,
) -> SignalEvaluation:
    try:
        evaluator = EVALUATORS[rule.code]
    except KeyError as error:
        raise ValueError(f"Unsupported signal rule: {rule.code}") from error
    return evaluator(rule, history, data_date)
