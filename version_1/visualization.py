"""Plotly-based visualization for simulation replay."""

from __future__ import annotations

import plotly.graph_objects as go

from config import REPLAY_ENABLED, SHOW_EDGES
from country_node import CountryNode
from utils import format_hover_text, normalize_size


def _build_edge_trace(
    countries: dict[str, CountryNode],
    visible_codes: set[str],
    active_codes: set[str],
) -> go.Scattergeo:
    """Return line traces only for edges touching currently affected countries."""
    lats = []
    lons = []

    for exporter in countries.values():
        if exporter.code not in visible_codes:
            continue

        for importer in exporter.trading_partners:
            if importer.code not in visible_codes:
                continue
            if exporter.code not in active_codes and importer.code not in active_codes:
                continue

            lats.extend([exporter.lat, importer.lat, None])
            lons.extend([exporter.lon, importer.lon, None])

    return go.Scattergeo(
        lat=lats,
        lon=lons,
        mode="lines",
        line={"width": 0.7, "color": "rgba(255, 127, 14, 0.28)"},
        hoverinfo="skip",
        showlegend=False,
    )


def _build_country_trace(
    countries: dict[str, CountryNode],
    wave_snapshot: dict[str, object],
    visible_codes: set[str],
    _max_gdp: float,
) -> go.Choropleth:
    """Return a choropleth trace that colors entire countries by health."""
    locations = []
    colors = []
    hover_texts = []

    shock_data = wave_snapshot["shock_data"]
    health_data = wave_snapshot["health_data"]

    for code in sorted(visible_codes):
        country = countries[code]
        locations.append(country.code)
        health = float(health_data.get(code, 1.0))
        colors.append(health)
        hover_texts.append(
            format_hover_text(country, health, float(shock_data.get(code, 0.0)))
        )

    return go.Choropleth(
        locations=locations,
        z=colors,
        text=hover_texts,
        locationmode="ISO-3",
        colorscale="RdYlGn",
        zmin=0,
        zmax=1,
        marker={"line": {"width": 0.4, "color": "white"}},
        colorbar={"title": "Health"},
        hovertemplate="%{text}<extra></extra>",
        showscale=True,
        showlegend=False,
    )


def _build_active_marker_trace(
    countries: dict[str, CountryNode],
    wave_snapshot: dict[str, object],
    visible_codes: set[str],
    max_gdp: float,
) -> go.Scattergeo:
    """Return a centroid overlay marking countries actively shocked in this wave."""
    latitudes = []
    longitudes = []
    sizes = []
    colors = []
    hover_texts = []

    shock_data = wave_snapshot["shock_data"]
    health_data = wave_snapshot["health_data"]

    for code in sorted(shock_data):
        if code not in visible_codes or code not in countries:
            continue

        country = countries[code]
        shock_value = float(shock_data[code])
        latitudes.append(country.lat)
        longitudes.append(country.lon)
        sizes.append(normalize_size(country.total_gdp, max_gdp) * 0.45 + shock_value * 36.0)
        colors.append(shock_value)
        hover_texts.append(
            format_hover_text(country, float(health_data.get(code, 1.0)), shock_value)
        )

    return go.Scattergeo(
        lat=latitudes,
        lon=longitudes,
        mode="markers",
        marker={
            "size": sizes,
            "color": colors,
            "colorscale": "YlOrRd",
            "cmin": 0,
            "cmax": 1,
            "opacity": 0.95,
            "line": {"width": 1.2, "color": "white"},
            "symbol": "circle",
        },
        text=hover_texts,
        hovertemplate="%{text}<extra>Active wave</extra>",
        showlegend=False,
    )


def create_simulation_figure(
    countries: dict[str, CountryNode],
    wave_history: list[dict[str, object]],
    visible_codes: set[str],
    show_edges: bool = SHOW_EDGES,
    replay_enabled: bool = REPLAY_ENABLED,
) -> go.Figure:
    """Create an animated Plotly figure for the saved wave history."""
    if not wave_history:
        raise ValueError("Wave history is empty.")

    max_gdp = max(countries[code].total_gdp for code in visible_codes)
    base_data = []
    first_wave = wave_history[0]
    first_active_codes = set(first_wave["shock_data"])
    if show_edges:
        base_data.append(_build_edge_trace(countries, visible_codes, first_active_codes))

    base_data.append(_build_country_trace(countries, first_wave, visible_codes, max_gdp))
    base_data.append(_build_active_marker_trace(countries, first_wave, visible_codes, max_gdp))
    frames = []

    for wave_snapshot in wave_history:
        active_codes = set(wave_snapshot["shock_data"])
        frame_data = []
        if show_edges:
            frame_data.append(_build_edge_trace(countries, visible_codes, active_codes))
        frame_data.append(_build_country_trace(countries, wave_snapshot, visible_codes, max_gdp))
        frame_data.append(_build_active_marker_trace(countries, wave_snapshot, visible_codes, max_gdp))
        frames.append(
            go.Frame(
                data=frame_data,
                name=f"Wave {wave_snapshot['wave']}",
            )
        )

    figure = go.Figure(data=base_data, frames=frames)
    figure.update_layout(
        title="Macroeconomic Shock Simulator",
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "showcoastlines": True,
            "showcountries": True,
            "showocean": True,
            "oceancolor": "rgb(208, 226, 242)",
            "landcolor": "rgb(247, 245, 239)",
            "countrycolor": "rgb(150, 150, 150)",
            "coastlinecolor": "rgb(110, 110, 110)",
            "bgcolor": "rgb(235, 243, 250)",
        },
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        paper_bgcolor="rgb(235, 243, 250)",
    )

    if replay_enabled:
        figure.update_layout(
            updatemenus=[
                {
                    "type": "buttons",
                    "buttons": [
                        {
                            "label": "Play",
                            "method": "animate",
                            "args": [None, {"frame": {"duration": 950, "redraw": True}}],
                        },
                        {
                            "label": "Pause",
                            "method": "animate",
                            "args": [[None], {"frame": {"duration": 0, "redraw": False}}],
                        },
                    ],
                }
            ],
            sliders=[
                {
                    "currentvalue": {"prefix": "Wave: "},
                    "steps": [
                        {
                            "label": str(wave_snapshot["wave"]),
                            "method": "animate",
                            "args": [
                                [f"Wave {wave_snapshot['wave']}"],
                                {"frame": {"duration": 0, "redraw": True}},
                            ],
                        }
                        for wave_snapshot in wave_history
                    ],
                }
            ],
        )

    return figure


def show_simulation(
    countries: dict[str, CountryNode],
    wave_history: list[dict[str, object]],
    visible_codes: set[str],
    show_edges: bool = SHOW_EDGES,
) -> None:
    """Display the simulation figure."""
    figure = create_simulation_figure(countries, wave_history, visible_codes, show_edges)
    figure.show(renderer="browser")
