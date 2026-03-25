"""Plotly-based visualization for time-step simulation replay."""

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
    """Return line traces only for edges touching currently active countries."""
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
        line={"width": 0.6, "color": "rgba(255, 140, 0, 0.22)"},
        hoverinfo="skip",
        showlegend=False,
    )


def _build_country_trace(
    countries: dict[str, CountryNode],
    step_snapshot: dict[str, object],
    visible_codes: set[str],
) -> go.Choropleth:
    """Return a choropleth trace that colors entire countries by health."""
    locations = []
    colors = []
    hover_texts = []

    impact_data = step_snapshot["shock_data"]
    health_data = step_snapshot["health_data"]
    inventory_data = step_snapshot["inventory_data"]
    shortage_data = step_snapshot.get("shortage_data", step_snapshot["pressure_data"])

    for code in sorted(visible_codes):
        country = countries[code]
        locations.append(country.code)
        colors.append(float(health_data.get(code, 1.0)))
        hover_texts.append(
            format_hover_text(
                country,
                float(health_data.get(code, 1.0)),
                float(impact_data.get(code, 0.0)),
                float(inventory_data.get(code, 1.0)),
                float(shortage_data.get(code, 0.0)),
            )
        )

    return go.Choropleth(
        locations=locations,
        z=colors,
        text=hover_texts,
        locationmode="ISO-3",
        colorscale=[
            [0.0, "rgb(120, 0, 0)"],
            [0.3, "rgb(202, 74, 38)"],
            [0.6, "rgb(238, 189, 82)"],
            [1.0, "rgb(57, 148, 93)"],
        ],
        zmin=0,
        zmax=1,
        marker={"line": {"width": 0.35, "color": "white"}},
        colorbar={"title": "Health"},
        hovertemplate="%{text}<extra></extra>",
        showscale=True,
        showlegend=False,
    )


def _build_active_marker_trace(
    countries: dict[str, CountryNode],
    step_snapshot: dict[str, object],
    visible_codes: set[str],
    max_gdp: float,
) -> go.Scattergeo:
    """Return centroid markers for countries with current disruptions."""
    latitudes = []
    longitudes = []
    sizes = []
    colors = []
    hover_texts = []

    impact_data = step_snapshot["shock_data"]
    health_data = step_snapshot["health_data"]
    inventory_data = step_snapshot["inventory_data"]
    shortage_data = step_snapshot.get("shortage_data", step_snapshot["pressure_data"])

    for code in sorted(impact_data):
        if code not in visible_codes or code not in countries:
            continue

        country = countries[code]
        impact = float(impact_data[code])
        latitudes.append(country.lat)
        longitudes.append(country.lon)
        sizes.append(normalize_size(country.total_gdp, max_gdp) * 0.35 + impact * 44.0)
        colors.append(impact)
        hover_texts.append(
            format_hover_text(
                country,
                float(health_data.get(code, 1.0)),
                impact,
                float(inventory_data.get(code, 1.0)),
                float(shortage_data.get(code, 0.0)),
            )
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
            "opacity": 0.92,
            "line": {"width": 1.2, "color": "white"},
            "symbol": "circle",
        },
        text=hover_texts,
        hovertemplate="%{text}<extra>Active disruption</extra>",
        showlegend=False,
    )


def _frame_name(step_snapshot: dict[str, object]) -> str:
    """Return the Plotly frame name for a snapshot."""
    return f"Step {step_snapshot['step']}"


def create_step_figure(
    countries: dict[str, CountryNode],
    step_history: list[dict[str, object]],
    visible_codes: set[str],
    step_index: int,
    show_edges: bool = SHOW_EDGES,
) -> go.Figure:
    """Create a static figure for a single simulation step."""
    if not step_history:
        raise ValueError("Simulation history is empty.")

    bounded_index = max(0, min(step_index, len(step_history) - 1))
    step_snapshot = step_history[bounded_index]
    max_gdp = max(countries[code].total_gdp for code in visible_codes)
    active_codes = set(step_snapshot["shock_data"]) | set(step_snapshot.get("shortage_data", step_snapshot["pressure_data"]))

    figure_data = []
    if show_edges:
        figure_data.append(_build_edge_trace(countries, visible_codes, active_codes))
    figure_data.append(_build_country_trace(countries, step_snapshot, visible_codes))
    figure_data.append(_build_active_marker_trace(countries, step_snapshot, visible_codes, max_gdp))

    figure = go.Figure(data=figure_data)
    figure.update_layout(
        title=f"Macroeconomic Shock Simulator v2 - Step {step_snapshot['step']}",
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "showcoastlines": True,
            "showcountries": True,
            "showocean": True,
            "oceancolor": "rgb(206, 225, 240)",
            "landcolor": "rgb(246, 244, 237)",
            "countrycolor": "rgb(150, 150, 150)",
            "coastlinecolor": "rgb(100, 100, 100)",
            "bgcolor": "rgb(233, 241, 247)",
        },
        margin={"l": 0, "r": 0, "t": 55, "b": 0},
        paper_bgcolor="rgb(233, 241, 247)",
    )
    return figure


def create_simulation_figure(
    countries: dict[str, CountryNode],
    step_history: list[dict[str, object]],
    visible_codes: set[str],
    show_edges: bool = SHOW_EDGES,
    replay_enabled: bool = REPLAY_ENABLED,
) -> go.Figure:
    """Create an animated Plotly figure for the saved time-step history."""
    if not step_history:
        raise ValueError("Simulation history is empty.")

    base_figure = create_step_figure(countries, step_history, visible_codes, 0, show_edges)
    max_gdp = max(countries[code].total_gdp for code in visible_codes)
    base_data = list(base_figure.data)

    frames = []
    for step_snapshot in step_history:
        active_codes = set(step_snapshot["shock_data"]) | set(step_snapshot.get("shortage_data", step_snapshot["pressure_data"]))
        frame_data = []
        if show_edges:
            frame_data.append(_build_edge_trace(countries, visible_codes, active_codes))
        frame_data.append(_build_country_trace(countries, step_snapshot, visible_codes))
        frame_data.append(_build_active_marker_trace(countries, step_snapshot, visible_codes, max_gdp))
        frames.append(go.Frame(data=frame_data, name=_frame_name(step_snapshot)))

    figure = go.Figure(data=base_data, frames=frames)
    figure.update_layout(**base_figure.layout.to_plotly_json())

    if replay_enabled:
        figure.update_layout(
            updatemenus=[
                {
                    "type": "buttons",
                    "buttons": [
                        {
                            "label": "Play",
                            "method": "animate",
                            "args": [None, {"frame": {"duration": 850, "redraw": True}}],
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
                    "currentvalue": {"prefix": "Step: "},
                    "steps": [
                        {
                            "label": str(step_snapshot["step"]),
                            "method": "animate",
                            "args": [
                                [_frame_name(step_snapshot)],
                                {"frame": {"duration": 0, "redraw": True}},
                            ],
                        }
                        for step_snapshot in step_history
                    ],
                }
            ],
        )

    return figure


def show_simulation(
    countries: dict[str, CountryNode],
    step_history: list[dict[str, object]],
    visible_codes: set[str],
    show_edges: bool = SHOW_EDGES,
) -> None:
    """Display the simulation figure."""
    figure = create_simulation_figure(countries, step_history, visible_codes, show_edges)
    figure.show(renderer="browser")
