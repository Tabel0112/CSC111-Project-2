"""Macroeconomic Shock Simulator: Runtime Helpers

This module contains small parsing and country-visibility helper functions used
by the dashboard during simulation setup and display filtering.

Copyright and Usage Information
===============================

This file is provided solely for the personal and private use of students
taking CSC111 at the University of Toronto. All forms of distribution of this
code, whether as given or with any changes, are expressly prohibited.

This file is Copyright (c) 2026 Baiyang Chen and collaborators.
"""

from __future__ import annotations

from country_node import CountryNode
from graph_builder import get_visible_country_codes, get_visible_country_codes_by_metric


def parse_csv_values(raw_value: str) -> list[str]:
    """Return non-empty comma-separated values."""
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def parse_country_names(raw_value: str) -> list[str]:
    """Return country names split by semicolons when present, otherwise commas."""
    separator = ";" if ";" in raw_value else ","
    return [value.strip() for value in raw_value.split(separator) if value.strip()]


def choose_visible_country_codes(
    countries: dict[str, CountryNode],
    wave_history: list[dict[str, object]],
    top_n: int,
    metric: str,
) -> set[str]:
    """Return visible countries, always keeping shocked or pressured countries."""
    visible_codes = (
        get_visible_country_codes(countries, top_n)
        if metric == "gdp"
        else get_visible_country_codes_by_metric(countries, top_n, metric)
    )
    shocked_codes = {
        shocked_code
        for wave_snapshot in wave_history
        for shocked_code in wave_snapshot["shock_data"]
        if shocked_code in countries
    }
    pressured_codes = {
        pressured_code
        for wave_snapshot in wave_history
        for pressured_code in wave_snapshot.get("pressure_data", {})
        if pressured_code in countries
    }
    return visible_codes | shocked_codes | pressured_codes


if __name__ == "__main__":
    import doctest
    import python_ta
    from pyta_config import PYTA_CONFIG

    doctest.testmod()
    python_ta.check_all(config=PYTA_CONFIG)
