import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import get_settings
from scanner.ingestion import (
    AShareHubMarketDataProvider,
    CsvMarketDataProvider,
    IngestionPersistenceError,
    IngestionValidationError,
    MarketDataProviderError,
    ingest_market_data,
)

SCANNER_VERSION = "0.1.0"
MAX_REPORTED_VALIDATION_ISSUES = 50


def validation_error_payload(error: IngestionValidationError) -> dict[str, object]:
    reported_issues = error.issues[:MAX_REPORTED_VALIDATION_ISSUES]
    return {
        "status": "validation_failed",
        "issue_count": len(error.issues),
        "issues": [issue.to_dict() for issue in reported_issues],
        "issues_truncated": len(reported_issues) < len(error.issues),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-scanner",
        description=(
            "AI Quant Research Platform scanner. "
            "Market data ingestion is available; scanning begins in Phase 4."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCANNER_VERSION}",
    )
    subparsers = parser.add_subparsers(dest="command")
    ingest_parser = subparsers.add_parser(
        "ingest-csv",
        help="Import validated stock and daily price CSV files into PostgreSQL.",
    )
    ingest_parser.add_argument(
        "--stocks-file",
        type=Path,
        required=True,
        help="CSV containing stock metadata.",
    )
    ingest_parser.add_argument(
        "--prices-file",
        type=Path,
        required=True,
        help="CSV containing daily OHLCV data.",
    )
    ingest_parser.add_argument(
        "--source",
        required=True,
        help="Non-broker source identifier stored with every daily price.",
    )
    ingest_parser.add_argument(
        "--expected-through",
        type=date.fromisoformat,
        help="Optional expected latest date in YYYY-MM-DD format.",
    )
    ingest_parser.add_argument(
        "--max-staleness-days",
        type=int,
        default=7,
        help="Warn when a stock's latest row is older than this many days.",
    )
    asharehub_parser = subparsers.add_parser(
        "ingest-asharehub",
        help="Import unadjusted daily market data from AShareHub.",
    )
    asharehub_parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        required=True,
        help="First trade date in YYYY-MM-DD format.",
    )
    asharehub_parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        required=True,
        help="Last trade date in YYYY-MM-DD format.",
    )
    asharehub_parser.add_argument(
        "--ts-code",
        action="append",
        default=[],
        help=(
            "Optional AShareHub stock code such as 000001.SZ or 920001.BJ. "
            "Repeat for multiple stocks; omit for the whole A-share market."
        ),
    )
    asharehub_parser.add_argument(
        "--page-size",
        type=int,
        default=5000,
        help="Rows requested per API call, from 1 to 5000.",
    )
    asharehub_parser.add_argument(
        "--max-requests",
        type=int,
        default=20,
        help="Maximum AShareHub requests allowed for this import.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "ingest-csv":
        try:
            csv_provider = CsvMarketDataProvider(
                stocks_file=args.stocks_file,
                prices_file=args.prices_file,
                source=args.source,
                expected_through=args.expected_through,
                max_staleness_days=args.max_staleness_days,
            )
            summary = ingest_market_data(csv_provider)
        except IngestionValidationError as error:
            print(
                json.dumps(validation_error_payload(error), indent=2),
                file=sys.stderr,
            )
            return 2
        except (IngestionPersistenceError, SQLAlchemyError, ValueError) as error:
            print(
                json.dumps(
                    {"status": "failed", "error": str(error)},
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1

        print(
            json.dumps(
                {"status": "completed", **summary.to_dict()},
                indent=2,
            )
        )
        return 0

    if args.command == "ingest-asharehub":
        try:
            api_key = get_settings().asharehub_api_key
            if api_key is None:
                raise ValueError(
                    "AQR_ASHAREHUB_API_KEY is required for ingest-asharehub"
                )
            asharehub_provider = AShareHubMarketDataProvider(
                api_key=api_key.get_secret_value(),
                start_date=args.start_date,
                end_date=args.end_date,
                ts_codes=tuple(args.ts_code),
                page_size=args.page_size,
                max_requests=args.max_requests,
            )
            summary = ingest_market_data(asharehub_provider)
        except IngestionValidationError as error:
            print(
                json.dumps(validation_error_payload(error), indent=2),
                file=sys.stderr,
            )
            return 2
        except (
            IngestionPersistenceError,
            MarketDataProviderError,
            SQLAlchemyError,
            ValueError,
        ) as error:
            print(
                json.dumps(
                    {"status": "failed", "error": str(error)},
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1

        print(
            json.dumps(
                {"status": "completed", **summary.to_dict()},
                indent=2,
            )
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 0
