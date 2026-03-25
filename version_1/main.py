"""Main entry point for the Macroeconomic Shock Simulator."""

from __future__ import annotations

import argparse
import sys

from country_node import CountryNode
from config import (    
    DEFAULT_COORDINATE_FILE,
    DEFAULT_GDP_FILE,
    DEFAULT_INITIAL_COUNTRIES,
    DEFAULT_INITIAL_SHOCK,
    DEFAULT_INITIAL_SHOCKS,
    DEFAULT_THRESHOLD,
    DEFAULT_TOP_K_EDGES,
    DEFAULT_TOP_N_COUNTRIES,
    DEFAULT_TRADE_FILE,
    DEFAULT_VISIBLE_BY,
)
from data_parser import (
    load_country_coordinates,
    load_gdp_data,
    load_trade_data,
    validate_country_matches,
)
from graph_builder import (
    build_trade_graph,
    limit_top_k_partners,
    reset_all_countries,
)
from runtime_options import (
    build_initial_shocks,
    choose_visible_country_codes,
    prompt_for_runtime_options,
)
from simulation import run_bfs_simulation
from visualization import show_simulation


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Macroeconomic Shock Simulator")
    parser.add_argument("--gdp-file", default=str(DEFAULT_GDP_FILE))
    parser.add_argument("--trade-file", default=str(DEFAULT_TRADE_FILE))
    parser.add_argument("--coord-file", default=str(DEFAULT_COORDINATE_FILE))
    parser.add_argument(
        "--initial-countries",
        default=DEFAULT_INITIAL_COUNTRIES,
        help="Country names separated by semicolons, e.g. United States; China; Germany.",
    )
    parser.add_argument("--initial-shock", type=float, default=DEFAULT_INITIAL_SHOCK)
    parser.add_argument(
        "--initial-shocks",
        default=DEFAULT_INITIAL_SHOCKS,
        help=(
            "Optional comma-separated shock magnitudes matching --initial-countries. "
            "A single value applies to all listed countries."
        ),
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N_COUNTRIES)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K_EDGES)
    parser.add_argument(
        "--visible-by",
        choices=["gdp", "exports", "imports", "trade"],
        default=DEFAULT_VISIBLE_BY,
        help="Choose how visible countries are ranked before adding all shocked countries.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip interactive terminal prompts and use CLI/default values directly.",
    )
    parser.add_argument("--hide-edges", action="store_true")
    return parser.parse_args()


def load_project_graph(args: argparse.Namespace) -> dict[str, CountryNode]:
    """Load the real trade graph from the project data files."""
    coordinates = load_country_coordinates(args.coord_file)
    gdp_data = load_gdp_data(args.gdp_file)
    trade_data = load_trade_data(args.trade_file)
    overlap = validate_country_matches(gdp_data, trade_data)

    print(
        "Loaded real data:",
        f"{len(gdp_data)} GDP countries,",
        f"{len(trade_data)} export rows,",
        f"{len(overlap['shared'])} shared country codes.",
    )

    countries = build_trade_graph(gdp_data, trade_data, coordinates)
    if not any(country.trading_partners for country in countries.values()):
        raise ValueError("Real data did not produce any bilateral trade edges.")

    return countries


def _print_run_summary(
    countries: dict[str, CountryNode],
    initial_shocks: dict[str, float],
    wave_history: list[dict[str, object]],
) -> None:
    """Print a short summary of the configured run."""
    country_names = [str(getattr(countries[code], "name", code)) for code in sorted(initial_shocks)]
    print("Mode: real")
    print(f"Initial shock countries: {', '.join(country_names)}")
    print(f"Generated {len(wave_history)} waves.")


def main() -> None:
    """Run the full project flow."""
    args = parse_arguments()
    countries = load_project_graph(args)
    if sys.stdin.isatty() and not args.no_prompt:
        args = prompt_for_runtime_options(args, countries)

    limit_top_k_partners(countries, args.top_k)
    reset_all_countries(countries)

    initial_shocks = build_initial_shocks(
        countries,
        args.initial_countries,
        args.initial_shock,
        args.initial_shocks,
    )
    wave_history = run_bfs_simulation(countries, initial_shocks, threshold=args.threshold)
    visible_codes = choose_visible_country_codes(
        countries,
        wave_history,
        min(args.top_n, len(countries)),
        args.visible_by,
    )

    _print_run_summary(countries, initial_shocks, wave_history)
    show_simulation(
        countries,
        wave_history,
        visible_codes,
        show_edges=not args.hide_edges,
    )


if __name__ == "__main__":
    main()
