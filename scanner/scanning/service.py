from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import ScannerRun, SessionLocal, TechnicalSignal
from scanner.scanning.errors import ScanConfigurationError, ScanExecutionError
from scanner.scanning.repository import (
    ensure_signal_definitions,
    load_price_histories,
    load_scan_stocks,
)
from scanner.scanning.types import ScanSummary, StockKey
from scanner.signals import RULES_BY_CODE, SignalRule

MAX_ERROR_MESSAGE_LENGTH = 2000


def _select_rules(
    signal_codes: Sequence[str],
    available_rules: Mapping[str, SignalRule],
) -> tuple[SignalRule, ...]:
    selected_codes = tuple(signal_codes) or tuple(available_rules)
    if len(set(selected_codes)) != len(selected_codes):
        raise ScanConfigurationError("Signal codes cannot contain duplicates")

    unknown_codes = [code for code in selected_codes if code not in available_rules]
    if unknown_codes:
        raise ScanConfigurationError(
            "Unsupported signal codes: " + ", ".join(unknown_codes)
        )
    return tuple(available_rules[code] for code in selected_codes)


def _validate_stock_keys(stock_keys: Sequence[StockKey]) -> tuple[StockKey, ...]:
    normalized = tuple(
        (exchange.strip().upper(), symbol.strip()) for exchange, symbol in stock_keys
    )
    if len(set(normalized)) != len(normalized):
        raise ScanConfigurationError("Selected stocks cannot contain duplicates")
    if any(not exchange or not symbol for exchange, symbol in normalized):
        raise ScanConfigurationError("Selected stocks require exchange and symbol")
    return normalized


def _run_parameters(
    rules: Sequence[SignalRule],
    stock_keys: Sequence[StockKey],
    max_bars: int,
) -> dict[str, object]:
    return {
        "signals": [{"code": rule.code, "version": rule.version} for rule in rules],
        "stock_selection": (
            [
                {"exchange": exchange, "symbol": symbol}
                for exchange, symbol in stock_keys
            ]
            if stock_keys
            else "all_active_and_suspended"
        ),
        "max_history_bars": max_bars,
    }


def _create_run(
    session_factory: sessionmaker[Session],
    *,
    run_id: UUID,
    data_date: date,
    universe_name: str,
    parameters: dict[str, object],
    started_at: datetime,
) -> None:
    with session_factory() as session:
        session.add(
            ScannerRun(
                id=run_id,
                status="running",
                data_date=data_date,
                universe_name=universe_name,
                parameters=parameters,
                started_at=started_at,
            )
        )
        session.commit()


def _mark_run_failed(
    session_factory: sessionmaker[Session],
    run_id: UUID,
    error: Exception,
) -> None:
    message = f"{type(error).__name__}: {error}"[:MAX_ERROR_MESSAGE_LENGTH]
    with session_factory() as session:
        scanner_run = session.get(ScannerRun, run_id)
        if scanner_run is None:
            raise RuntimeError(f"Scanner run disappeared: {run_id}")
        scanner_run.status = "failed"
        scanner_run.finished_at = datetime.now(UTC)
        scanner_run.error_count = 1
        scanner_run.error_message = message
        session.commit()


def run_scan(
    data_date: date,
    *,
    stock_keys: Sequence[StockKey] = (),
    signal_codes: Sequence[str] = (),
    universe_name: str | None = None,
    session_factory: sessionmaker[Session] = SessionLocal,
    available_rules: Mapping[str, SignalRule] = RULES_BY_CODE,
) -> ScanSummary:
    rules = _select_rules(signal_codes, available_rules)
    normalized_stock_keys = _validate_stock_keys(stock_keys)
    resolved_universe_name = universe_name or (
        "selected_stocks" if normalized_stock_keys else "all_a_shares"
    )
    if not resolved_universe_name.strip():
        raise ScanConfigurationError("universe_name cannot be empty")

    max_bars = max(rule.required_bars for rule in rules)
    run_id = uuid4()
    started_at = datetime.now(UTC)
    _create_run(
        session_factory,
        run_id=run_id,
        data_date=data_date,
        universe_name=resolved_universe_name,
        parameters=_run_parameters(rules, normalized_stock_keys, max_bars),
        started_at=started_at,
    )

    try:
        with session_factory() as session:
            scanner_run = session.get(ScannerRun, run_id)
            if scanner_run is None:
                raise RuntimeError(f"Scanner run disappeared: {run_id}")

            stocks = load_scan_stocks(session, normalized_stock_keys)
            if normalized_stock_keys:
                found_keys = {stock.key for stock in stocks}
                missing_keys = set(normalized_stock_keys) - found_keys
                if missing_keys:
                    missing = ", ".join(
                        f"{exchange}:{symbol}"
                        for exchange, symbol in sorted(missing_keys)
                    )
                    raise ScanConfigurationError(
                        f"Selected stocks were not found: {missing}"
                    )
            if not stocks:
                raise ScanConfigurationError(
                    "No stocks are available for the selected universe"
                )

            histories = load_price_histories(
                session,
                [stock.id for stock in stocks],
                data_date,
                max_bars,
            )
            definitions = ensure_signal_definitions(session, rules)
            signal_counts = {rule.code: 0 for rule in rules}
            warning_counts = {rule.code: 0 for rule in rules}
            matched_stock_ids: set[int] = set()
            processed_stocks = 0
            detected_signals = 0

            for stock in stocks:
                history = histories.get(stock.id, ())
                stock_fully_evaluated = True
                for rule in rules:
                    evaluation = rule.evaluate(history, data_date)
                    if not evaluation.was_evaluated:
                        stock_fully_evaluated = False
                        warning_counts[rule.code] += 1
                        continue
                    if evaluation.match is None:
                        continue

                    definition = definitions[rule.code]
                    session.add(
                        TechnicalSignal(
                            scanner_run_id=run_id,
                            stock_id=stock.id,
                            signal_definition_id=definition.id,
                            signal_date=evaluation.match.signal_date,
                            matched_values=evaluation.match.matched_values,
                            explanation=evaluation.match.explanation,
                        )
                    )
                    signal_counts[rule.code] += 1
                    detected_signals += 1
                    matched_stock_ids.add(stock.id)

                if stock_fully_evaluated:
                    processed_stocks += 1

            warning_count = sum(warning_counts.values())
            status = "completed_with_warnings" if warning_count else "completed"
            scanner_run.status = status
            scanner_run.finished_at = datetime.now(UTC)
            scanner_run.total_stocks = len(stocks)
            scanner_run.processed_stocks = processed_stocks
            scanner_run.matched_stocks = len(matched_stock_ids)
            scanner_run.warning_count = warning_count
            scanner_run.error_count = 0
            scanner_run.error_message = None
            session.commit()

        return ScanSummary(
            run_id=run_id,
            status=status,
            data_date=data_date,
            universe_name=resolved_universe_name,
            total_stocks=len(stocks),
            processed_stocks=processed_stocks,
            matched_stocks=len(matched_stock_ids),
            detected_signals=detected_signals,
            warning_count=warning_count,
            signal_counts=signal_counts,
            warning_counts=warning_counts,
        )
    except Exception as error:
        _mark_run_failed(session_factory, run_id, error)
        raise ScanExecutionError(run_id, str(error)) from error
