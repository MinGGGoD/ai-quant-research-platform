import argparse
from collections.abc import Sequence

SCANNER_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-scanner",
        description=(
            "AI Quant Research Platform scanner. "
            "Market scanning commands will be added in Phase 4."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCANNER_VERSION}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
