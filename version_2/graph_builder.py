"""Helpers for building and filtering the directed trade graph."""

from __future__ import annotations

from collections.abc import Iterable

from config import MAX_EDGE_WEIGHT
from country_node import CountryNode
from utils import sort_countries_by_gdp


def build_country_nodes(
    gdp_data: dict[str, dict[str, object]],
    coordinates: dict[str, tuple[float, float]],
) -> dict[str, CountryNode]:
    """Build CountryNode objects from GDP and coordinate data."""
    countries = {}

    for code, details in gdp_data.items():
        lat, lon = coordinates.get(code, (0.0, 0.0))
        countries[code] = CountryNode(
            code=code,
            name=str(details["name"]),
            total_gdp=float(details["gdp"]),
            lat=lat,
            lon=lon,
        )

    return countries


def compute_edge_weight(trade_value: float, importer_total_imports: float) -> float:
    """Return the exporter share of the importer's total imports."""
    if importer_total_imports <= 0:
        return 0.0
    return min(trade_value / importer_total_imports, MAX_EDGE_WEIGHT)


def _compute_import_totals(
    countries: dict[str, CountryNode],
    trade_data: list[dict[str, object]],
) -> dict[str, float]:
    """Return total imports for each importer present in the graph."""
    totals = {code: 0.0 for code in countries}

    for row in trade_data:
        exporter_code = str(row["exporter_code"])
        importer_code = str(row["importer_code"])
        if exporter_code not in countries or importer_code not in countries:
            continue
        totals[importer_code] += float(row["trade_value"])

    return totals


def add_trade_edges(
    countries: dict[str, CountryNode],
    trade_data: list[dict[str, object]],
) -> None:
    """Add directed weighted edges from exporter to importer."""
    import_totals = _compute_import_totals(countries, trade_data)

    for row in trade_data:
        exporter_code = str(row["exporter_code"])
        importer_code = str(row["importer_code"])

        if exporter_code not in countries or importer_code not in countries:
            continue

        exporter = countries[exporter_code]
        importer = countries[importer_code]
        trade_value = float(row["trade_value"])
        weight = compute_edge_weight(trade_value, import_totals[importer_code])
        exporter.total_exports += trade_value
        importer.total_imports += trade_value

        if weight > 0:
            exporter.add_trading_partner(importer, weight)


def build_trade_graph(
    gdp_data: dict[str, dict[str, object]],
    trade_data: list[dict[str, object]],
    coordinates: dict[str, tuple[float, float]],
) -> dict[str, CountryNode]:
    """Build the full graph from cleaned GDP, trade, and coordinate data."""
    countries = build_country_nodes(gdp_data, coordinates)
    add_trade_edges(countries, trade_data)
    return countries


def clone_trade_graph(countries: dict[str, CountryNode]) -> dict[str, CountryNode]:
    """Return a detached copy of the country graph for display-only filtering."""
    cloned = {
        code: CountryNode(
            code=country.code,
            name=country.name,
            total_gdp=country.total_gdp,
            lat=country.lat,
            lon=country.lon,
            total_imports=country.total_imports,
            total_exports=country.total_exports,
        )
        for code, country in countries.items()
    }

    for exporter in countries.values():
        cloned_exporter = cloned[exporter.code]
        for importer, weight in exporter.trading_partners.items():
            cloned_exporter.add_trading_partner(cloned[importer.code], weight)

    return cloned


def reset_all_countries(countries: dict[str, CountryNode]) -> None:
    """Reset every country to full health."""
    for country in countries.values():
        country.reset_health()


def get_top_countries_by_gdp(
    countries: dict[str, CountryNode],
    top_n: int,
) -> list[CountryNode]:
    """Return the top <top_n> countries by GDP."""
    ordered = sort_countries_by_gdp(countries)
    return ordered[:top_n]


def get_visible_country_codes(
    countries: dict[str, CountryNode],
    top_n: int,
) -> set[str]:
    """Return the ISO-3 codes of the top GDP countries."""
    return {country.code for country in get_top_countries_by_gdp(countries, top_n)}


def _compute_incoming_weight_totals(
    countries: dict[str, CountryNode],
) -> dict[str, float]:
    """Return summed incoming edge weights for each country."""
    incoming_totals = {code: 0.0 for code in countries}
    for exporter in countries.values():
        for importer, weight in exporter.trading_partners.items():
            incoming_totals[importer.code] += weight
    return incoming_totals


def _rank_countries_by_metric(
    countries: dict[str, CountryNode],
    metric: str,
) -> list[CountryNode]:
    """Return countries ordered by the requested visibility metric."""
    if metric == "gdp":
        return get_top_countries_by_gdp(countries, len(countries))

    incoming_totals = _compute_incoming_weight_totals(countries)

    if metric == "exports":
        return sorted(
            countries.values(),
            key=lambda country: (-sum(country.trading_partners.values()), country.code),
        )

    if metric == "imports":
        return sorted(
            countries.values(),
            key=lambda country: (-incoming_totals[country.code], country.code),
        )

    if metric == "trade":
        return sorted(
            countries.values(),
            key=lambda country: (
                -(sum(country.trading_partners.values()) + incoming_totals[country.code]),
                country.code,
            ),
        )

    raise ValueError(f"Unsupported visibility metric: {metric}")


def get_visible_country_codes_by_metric(
    countries: dict[str, CountryNode],
    top_n: int,
    metric: str,
) -> set[str]:
    """Return visible country codes using GDP, export, import, or total-trade ranking."""
    ordered = _rank_countries_by_metric(countries, metric)
    return {country.code for country in ordered[:top_n]}


def _compute_import_share_lists(
    countries: dict[str, CountryNode],
) -> dict[str, list[float]]:
    """Return incoming import-share weights for each importer."""
    share_lists = {code: [] for code in countries}

    for exporter in countries.values():
        for importer, weight in exporter.trading_partners.items():
            share_lists[importer.code].append(weight)

    return share_lists


def _clamp_unit(value: float) -> float:
    """Return <value> clamped to the closed unit interval."""
    return max(0.0, min(1.0, value))


def build_country_resilience_profiles(
    countries: dict[str, CountryNode],
) -> dict[str, dict[str, float]]:
    """Return country-specific resilience values derived from current trade structure.

    The current dataset does not include direct inventory or substitution measurements,
    so this function builds proxies from:
    - supplier diversification
    - largest-supplier concentration
    - import dependence relative to GDP
    - number of active suppliers
    """
    substitution_rates = {}
    inventory_buffers = {}
    delay_shares = {}
    diversification_scores = {}
    import_dependency_scores = {}
    concentration_scores = {}
    share_lists = _compute_import_share_lists(countries)

    for code, shares in share_lists.items():
        if not shares:
            diversification = 0.3
            largest_supplier_share = 1.0
            breadth = 0.0
        else:
            total_share = sum(shares)
            normalized_shares = [share / total_share for share in shares]
            concentration = sum(share * share for share in normalized_shares)
            effective_partner_count = 1.0 / concentration if concentration > 0 else len(shares)
            diversification = min(1.0, max(0.0, (effective_partner_count - 1.0) / 9.0))
            largest_supplier_share = max(normalized_shares)
            breadth = _clamp_unit((len(normalized_shares) - 1.0) / 14.0)

        country = countries[code]
        import_dependency = _clamp_unit((country.total_imports / max(country.total_gdp, 1.0)) / 0.6)
        diversification_scores[code] = diversification
        import_dependency_scores[code] = import_dependency
        concentration_scores[code] = largest_supplier_share

        substitution_rates[code] = min(
            0.65,
            max(
                0.06,
                0.08
                + 0.28 * diversification
                + 0.14 * breadth
                - 0.18 * largest_supplier_share
                - 0.16 * import_dependency,
            ),
        )
        inventory_buffers[code] = min(
            0.14,
            max(
                0.015,
                0.02
                + 0.045 * diversification
                + 0.025 * breadth
                + 0.02 * (1.0 - import_dependency),
            ),
        )
        delay_shares[code] = min(
            0.45,
            max(
                0.08,
                0.10
                + 0.20 * diversification
                + 0.10 * breadth
                + 0.05 * (1.0 - largest_supplier_share),
            ),
        )

    return {
        "substitution_rates": substitution_rates,
        "inventory_buffers": inventory_buffers,
        "delay_shares": delay_shares,
        "diversification_scores": diversification_scores,
        "import_dependency_scores": import_dependency_scores,
        "concentration_scores": concentration_scores,
    }


def limit_top_k_partners(
    countries: dict[str, CountryNode],
    top_k: int,
) -> None:
    """Keep only the top-k outgoing partners for each country."""
    if top_k <= 0:
        return

    for country in countries.values():
        ordered = sorted(
            country.trading_partners.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        country.trading_partners = dict(ordered[:top_k])
