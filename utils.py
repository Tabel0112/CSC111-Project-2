"""Small helper functions used across the project."""

from __future__ import annotations

from country_node import CountryNode


def safe_float(value: object, default: float = 0.0) -> float:
    """Return <value> as a float when possible, or <default> otherwise.

    >>> safe_float("12.5")
    12.5
    >>> safe_float("1,250")
    1250.0
    >>> safe_float("NA", default=-1.0)
    -1.0
    """
    if value is None:
        return default

    if isinstance(value, float):
        return value

    cleaned = str(value).strip().replace(",", "")
    if cleaned in {"", "..", "NA", "N/A", "null", "None"}:
        return default

    try:
        return float(cleaned)
    except ValueError:
        return default


def normalize_size(total_gdp: float, max_gdp: float) -> float:
    """Return a Plotly node size using the project formula.

    >>> normalize_size(25.0, 100.0)
    14.0
    >>> normalize_size(10.0, 0.0)
    4.0
    """
    if max_gdp <= 0:
        return 4.0

    return 4.0 + 20.0 * (total_gdp / max_gdp) ** 0.5


def clamp_shock(shock: float) -> float:
    """Clamp a shock into the interval [0.0, 1.0].

    >>> clamp_shock(-0.2)
    0.0
    >>> clamp_shock(0.35)
    0.35
    >>> clamp_shock(1.8)
    1.0
    """
    return max(0.0, min(shock, 1.0))


def country_dict_to_snapshot(countries: dict[str, CountryNode]) -> dict[str, float]:
    """Return a health snapshot for all countries, sorted by code."""
    return {
        code: countries[code].current_health
        for code in sorted(countries)
    }


def sort_countries_by_gdp(countries: dict[str, CountryNode]) -> list[CountryNode]:
    """Return all countries sorted by descending GDP."""
    return sorted(
        countries.values(),
        key=lambda country: (-country.total_gdp, country.code),
    )


def format_hover_text(
    country: CountryNode,
    health: float,
    impact: float,
    inventory: float = 1.0,
    shortage: float = 0.0,
) -> str:
    """Return hover text for a country marker."""
    return (
        f"{country.name} ({country.code})<br>"
        f"GDP: {country.total_gdp:,.0f}<br>"
        f"Health: {health:.3f}<br>"
        f"Current impact: {impact:.3f}<br>"
        f"Inventory buffer: {inventory:.3f}<br>"
        f"Import shortage: {shortage:.3f}"
    )


if __name__ == "__main__":
    import doctest
    import python_ta
    from pyta_config import PYTA_CONFIG

    doctest.testmod()
    python_ta.check_all(config=PYTA_CONFIG)
