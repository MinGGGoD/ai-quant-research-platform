import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from scanner.ingestion import (
    CsvMarketDataProvider,
    IngestionPersistenceError,
    IngestionValidationError,
    ingest_market_data,
)

SCANNER_VERSION = "0.1.0"


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "ingest-csv":
        try:
            provider = CsvMarketDataProvider(
                stocks_file=args.stocks_file,
                prices_file=args.prices_file,
                source=args.source,
                expected_through=args.expected_through,
                max_staleness_days=args.max_staleness_days,
            )
            summary = ingest_market_data(provider)
        except IngestionValidationError as error:
            print(
                json.dumps(
                    {
                        "status": "validation_failed",
                        "issues": [issue.to_dict() for issue in error.issues],
                    },
                    indent=2,
                ),
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

    parser.error(f"Unsupported command: {args.command}")
    return 0
