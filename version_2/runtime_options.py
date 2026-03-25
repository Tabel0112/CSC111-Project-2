"""Shared dashboard parsing and visibility helpers."""

from __future__ import annotations

from country_node import CountryNode
from graph_builder import get_visible_country_codes, get_visible_country_codes_by_metric


def parse_csv_values(raw_value: str) -> list[str]:
    """Return non-empty comma-separated values."""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_country_names(raw_value: str) -> list[str]:
    """Return country names split by semicolons when present, otherwise commas."""
    separator = ";" if ";" in raw_value else ","
    return [item.strip() for item in raw_value.split(separator) if item.strip()]


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
        code
        for wave_snapshot in wave_history
        for code in wave_snapshot["shock_data"]
        if code in countries
    }
    pressured_codes = {
        code
        for wave_snapshot in wave_history
        for code in wave_snapshot.get("pressure_data", {})
        if code in countries
    }
    return visible_codes | shocked_codes | pressured_codes
