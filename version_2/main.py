"""Main entry point for the Macroeconomic Shock Simulator."""

from __future__ import annotations

import argparse
from config import (
    DEFAULT_COORDINATE_FILE,
    DEFAULT_GDP_FILE,
    DEFAULT_INITIAL_COUNTRIES,
    DEFAULT_THRESHOLD,
    DEFAULT_TOP_K_EDGES,
    DEFAULT_TOP_N_COUNTRIES,
    DEFAULT_TRADE_FILE,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Macroeconomic Shock Simulator")
    parser.add_argument("--gdp-file", default=str(DEFAULT_GDP_FILE))
    parser.add_argument("--trade-file", default=str(DEFAULT_TRADE_FILE))
    parser.add_argument("--coord-file", default=str(DEFAULT_COORDINATE_FILE))
    parser.add_argument(
        "--initial-countries",
        default=DEFAULT_INITIAL_COUNTRIES,
        help="Default selected country names for the dashboard, separated by semicolons.",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N_COUNTRIES)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K_EDGES)
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--hide-edges", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Launch the dashboard UI."""
    args = parse_arguments()
    from dashboard import run_dashboard

    run_dashboard(args)


if __name__ == "__main__":
    main()
