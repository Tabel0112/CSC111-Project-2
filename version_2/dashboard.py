"""Dash interface for the time-step simulation."""

from __future__ import annotations

from argparse import Namespace
import socket
import threading
import webbrowser

from config import (
    DEFAULT_INITIAL_COUNTRIES,
    DEFAULT_INITIAL_SHOCK,
    DEFAULT_INITIAL_SHOCKS,
    DEFAULT_VISIBLE_BY,
)
from country_node import CountryNode
from data_parser import (
    load_country_coordinates,
    load_gdp_data,
    load_trade_data,
    validate_country_matches,
)
from graph_builder import (
    build_country_resilience_profiles,
    build_trade_graph,
    clone_trade_graph,
    limit_top_k_partners,
    reset_all_countries,
)
from runtime_options import choose_visible_country_codes, parse_country_names, parse_csv_values
from simulation import run_time_step_simulation
from visualization import create_simulation_figure


def build_country_dropdown_options(countries: dict[str, CountryNode]) -> list[dict[str, str]]:
    """Return dropdown options sorted by country name."""
    ordered = sorted(
        (country.name, code)
        for code, country in countries.items()
    )
    return [{"label": name, "value": code} for name, code in ordered]


def build_default_shock_lookup() -> dict[str, float]:
    """Return default shock values keyed by default country name."""
    default_names = parse_country_names(DEFAULT_INITIAL_COUNTRIES)
    default_values = parse_csv_values(DEFAULT_INITIAL_SHOCKS)
    try:
        shocks = [float(value) for value in default_values]
    except ValueError:
        return {}

    if len(shocks) == 1:
        return {name: shocks[0] for name in default_names}
    return {name: shock for name, shock in zip(default_names, shocks)}


def sync_shock_rows(
    selected_codes: list[str],
    existing_rows: list[dict[str, object]],
    countries: dict[str, CountryNode],
) -> list[dict[str, object]]:
    """Return table rows that match the selected countries."""
    existing_lookup = {
        str(row.get("code", "")): float(row.get("shock", DEFAULT_INITIAL_SHOCK))
        for row in existing_rows or []
        if str(row.get("code", "")) in countries
    }
    default_lookup = build_default_shock_lookup()
    default_code_lookup = {
        code: default_lookup.get(country.name, DEFAULT_INITIAL_SHOCK)
        for code, country in countries.items()
    }

    rows = []
    for code in selected_codes:
        if code not in countries:
            continue
        rows.append(
            {
                "code": code,
                "country": countries[code].name,
                "shock": existing_lookup.get(code, default_code_lookup.get(code, DEFAULT_INITIAL_SHOCK)),
            }
        )
    return rows


def shock_rows_to_initial_inputs(rows: list[dict[str, object]]) -> tuple[str, str]:
    """Convert editable shock table rows to runtime input strings."""
    country_names = []
    shocks = []

    for row in rows:
        country_name = str(row.get("country", "")).strip()
        shock = float(row.get("shock", DEFAULT_INITIAL_SHOCK))
        if country_name:
            country_names.append(country_name)
            shocks.append(str(shock))

    return "; ".join(country_names), ",".join(shocks)


def _load_base_graph(args: Namespace) -> dict[str, CountryNode]:
    """Load the unfiltered graph used by the dashboard."""
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


def _find_available_port(start_port: int, host: str = "127.0.0.1", tries: int = 20) -> int:
    """Return the first available port at or above start_port."""
    for port in range(start_port, start_port + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port

    raise OSError(f"Could not find an available port between {start_port} and {start_port + tries - 1}.")


def _open_browser_when_ready(url: str, delay_seconds: float = 1.0) -> None:
    """Open the dashboard URL in the default browser after a short delay."""
    timer = threading.Timer(delay_seconds, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def _run_simulation_from_controls(
    template_countries: dict[str, CountryNode],
    selected_codes: list[str],
    rows: list[dict[str, object]],
    threshold: float,
    steps: int,
    top_n: int,
    top_k: int,
    visible_by: str,
    _hide_edges: bool,
):
    """Return simulation outputs from UI control values."""
    countries = clone_trade_graph(template_countries)
    reset_all_countries(countries)

    initial_shock_map = {
        str(row["code"]): float(row["shock"])
        for row in rows
        if row.get("code") in countries
    }
    if not initial_shock_map:
        initial_shock_map = {
            code: DEFAULT_INITIAL_SHOCK
            for code in selected_codes
            if code in countries
        }

    resilience_profiles = build_country_resilience_profiles(countries)
    step_history = run_time_step_simulation(
        countries,
        initial_shock_map,
        threshold=threshold,
        max_steps=steps,
        inventory_buffer=resilience_profiles["inventory_buffers"],
        substitution_rate=resilience_profiles["substitution_rates"],
        delay_share=resilience_profiles["delay_shares"],
    )
    visible_codes = choose_visible_country_codes(
        countries,
        step_history,
        min(top_n, len(countries)),
        visible_by,
    )
    status = (
        f"Selected {len(initial_shock_map)} countries. "
        f"Generated {len(step_history)} steps. "
        f"Last step affects {len(step_history[-1]['shock_data']) if step_history else 0} countries."
    )
    return {
        "step_history": step_history,
        "visible_codes": sorted(visible_codes),
        "top_k": int(top_k),
    }, status


def _build_slider_marks(step_count: int) -> dict[int, str]:
    """Return readable slider marks for the current simulation length."""
    if step_count <= 0:
        return {0: "0"}

    if step_count <= 8:
        return {index: str(index) for index in range(step_count)}

    stride = max(1, step_count // 6)
    marks = {0: "0", step_count - 1: str(step_count - 1)}
    for index in range(stride, step_count - 1, stride):
        marks[index] = str(index)
    return dict(sorted(marks.items()))


def _render_dashboard_figure(
    base_countries: dict[str, CountryNode],
    simulation_data: dict[str, object] | None,
    step_index: int,
    hide_edges: bool,
):
    """Return the figure for the requested step using stored simulation data."""
    if not simulation_data:
        return create_simulation_figure(base_countries, [
            {
                "step": 0,
                "shock_data": {},
                "health_data": {code: 1.0 for code in base_countries},
                "inventory_data": {code: 0.0 for code in base_countries},
                "pressure_data": {},
                "shortage_data": {},
                "deferred_shortage_data": {},
            }
        ], set(list(base_countries)[: min(20, len(base_countries))]), show_edges=False, replay_enabled=False)

    from visualization import create_step_figure

    display_countries = clone_trade_graph(base_countries)
    limit_top_k_partners(display_countries, int(simulation_data["top_k"]))
    return create_step_figure(
        display_countries,
        simulation_data["step_history"],
        set(simulation_data["visible_codes"]),
        step_index,
        show_edges=not hide_edges,
    )


def run_dashboard(args: Namespace) -> None:
    """Launch the Dash UI for the simulator."""
    try:
        from dash import Dash, Input, Output, State, dash_table, dcc, html
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Dash is not installed. Run `pip install -r requirements.txt` in version_2 first."
        ) from exc

    base_countries = _load_base_graph(args)
    options = build_country_dropdown_options(base_countries)
    default_names = parse_country_names(args.initial_countries or DEFAULT_INITIAL_COUNTRIES)
    default_codes = [
        code
        for name in default_names
        for code, country in base_countries.items()
        if country.name == name
    ]
    initial_rows = sync_shock_rows(default_codes, [], base_countries)

    app = Dash(__name__)
    app.layout = html.Div(
        style={"fontFamily": "Georgia, serif", "backgroundColor": "#eef3f7", "minHeight": "100vh", "padding": "18px"},
        children=[
            html.H1("Macroeconomic Shock Simulator v2"),
            html.P("Select starting countries, edit impacts, then rerun the simulation in the browser."),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "380px 1fr", "gap": "18px", "alignItems": "start"},
                children=[
                    html.Div(
                        style={"backgroundColor": "white", "padding": "16px", "borderRadius": "12px", "boxShadow": "0 2px 10px rgba(0,0,0,0.08)"},
                        children=[
                            html.Label("Starting countries"),
                            dcc.Dropdown(
                                id="country-select",
                                options=options,
                                value=default_codes,
                                multi=True,
                                placeholder="Choose one or more countries",
                            ),
                            html.Div(style={"height": "12px"}),
                            html.Label("Shock values"),
                            dash_table.DataTable(
                                id="shock-table",
                                columns=[
                                    {"name": "Code", "id": "code", "editable": False},
                                    {"name": "Country", "id": "country", "editable": False},
                                    {"name": "Shock", "id": "shock", "editable": True, "type": "numeric"},
                                ],
                                data=initial_rows,
                                editable=True,
                                style_table={"overflowX": "auto"},
                                style_cell={"textAlign": "left", "padding": "6px"},
                            ),
                            html.Div(style={"height": "12px"}),
                            html.Label("Threshold"),
                            dcc.Input(id="threshold-input", type="number", value=args.threshold, step="any", min=0),
                            html.Div(style={"height": "8px"}),
                            html.Label("Time steps"),
                            dcc.Input(id="steps-input", type="number", value=args.steps, step=1),
                            html.Div(style={"height": "8px"}),
                            html.Label("Visible countries"),
                            dcc.Input(id="top-n-input", type="number", value=args.top_n, step=1),
                            html.Div(style={"height": "8px"}),
                            html.Label("Visible edges per country"),
                            dcc.Input(id="top-k-input", type="number", value=args.top_k, step=1),
                            html.Div(style={"height": "8px"}),
                            html.Label("Visibility ranking"),
                            dcc.Dropdown(
                                id="visible-by-input",
                                options=[{"label": value.upper(), "value": value} for value in ["gdp", "exports", "imports", "trade"]],
                                value=args.visible_by or DEFAULT_VISIBLE_BY,
                                clearable=False,
                            ),
                            html.Div(style={"height": "8px"}),
                            dcc.Checklist(
                                id="hide-edges-input",
                                options=[{"label": "Hide edges", "value": "hide"}],
                                value=["hide"] if args.hide_edges else [],
                            ),
                            html.Button("Run Simulation", id="run-button", n_clicks=0, style={"marginTop": "12px"}),
                            html.Div(style={"height": "12px"}),
                            html.Div(
                                style={"display": "flex", "gap": "8px", "alignItems": "center"},
                                children=[
                                    html.Button("Previous", id="prev-step-button", n_clicks=0),
                                    html.Button("Play", id="play-toggle-button", n_clicks=0),
                                    html.Button("Next", id="next-step-button", n_clicks=0),
                                ],
                            ),
                            html.Div(style={"height": "10px"}),
                            dcc.Slider(id="step-slider", min=0, max=0, value=0, marks={0: "0"}, step=1),
                            html.P(id="status-text", style={"marginTop": "12px"}),
                        ],
                    ),
                    html.Div(
                        style={"backgroundColor": "white", "padding": "10px", "borderRadius": "12px", "boxShadow": "0 2px 10px rgba(0,0,0,0.08)"},
                        children=[dcc.Graph(id="simulation-graph")],
                    ),
                ],
            ),
            dcc.Store(id="simulation-store"),
            dcc.Store(id="playback-store", data={"playing": False}),
            dcc.Interval(id="playback-interval", interval=850, disabled=True, n_intervals=0),
        ],
    )

    @app.callback(
        Output("shock-table", "data"),
        Input("country-select", "value"),
        State("shock-table", "data"),
    )
    def _sync_table(selected_codes: list[str], existing_rows: list[dict[str, object]]):
        return sync_shock_rows(selected_codes or [], existing_rows or [], base_countries)

    @app.callback(
        Output("simulation-store", "data"),
        Output("status-text", "children"),
        Output("step-slider", "max"),
        Output("step-slider", "value"),
        Output("step-slider", "marks"),
        Output("playback-store", "data"),
        Output("playback-interval", "disabled"),
        Output("play-toggle-button", "children"),
        Input("run-button", "n_clicks"),
        State("country-select", "value"),
        State("shock-table", "data"),
        State("threshold-input", "value"),
        State("steps-input", "value"),
        State("top-n-input", "value"),
        State("top-k-input", "value"),
        State("visible-by-input", "value"),
        State("hide-edges-input", "value"),
    )
    def _run_from_controls(
        _n_clicks: int,
        selected_codes: list[str],
        rows: list[dict[str, object]],
        threshold: float,
        steps: int,
        top_n: int,
        top_k: int,
        visible_by: str,
        hide_edges: list[str],
    ):
        simulation_data, status = _run_simulation_from_controls(
            base_countries,
            selected_codes or [],
            rows or [],
            float(threshold),
            int(steps),
            int(top_n),
            int(top_k),
            visible_by,
            "hide" in (hide_edges or []),
        )
        step_count = len(simulation_data["step_history"])
        return (
            simulation_data,
            status,
            max(0, step_count - 1),
            0,
            _build_slider_marks(step_count),
            {"playing": False},
            True,
            "Play",
        )

    @app.callback(
        Output("step-slider", "value"),
        Output("playback-store", "data"),
        Output("playback-interval", "disabled"),
        Output("play-toggle-button", "children"),
        Input("prev-step-button", "n_clicks"),
        Input("next-step-button", "n_clicks"),
        Input("play-toggle-button", "n_clicks"),
        Input("playback-interval", "n_intervals"),
        State("step-slider", "value"),
        State("step-slider", "max"),
        State("playback-store", "data"),
        prevent_initial_call=True,
    )
    def _control_playback(
        _prev_clicks: int,
        _next_clicks: int,
        _toggle_clicks: int,
        _interval_count: int,
        current_value: int,
        slider_max: int,
        playback_state: dict[str, object] | None,
    ):
        from dash import ctx

        playback_state = dict(playback_state or {"playing": False})
        current_value = int(current_value or 0)
        slider_max = int(slider_max or 0)
        trigger = ctx.triggered_id

        if trigger == "prev-step-button":
            return max(0, current_value - 1), {"playing": False}, True, "Play"

        if trigger == "next-step-button":
            return min(slider_max, current_value + 1), {"playing": False}, True, "Play"

        if trigger == "play-toggle-button":
            is_playing = not bool(playback_state.get("playing", False))
            return current_value, {"playing": is_playing}, (not is_playing), ("Pause" if is_playing else "Play")

        if trigger == "playback-interval" and playback_state.get("playing", False):
            if current_value >= slider_max:
                return slider_max, {"playing": False}, True, "Play"
            return current_value + 1, playback_state, False, "Pause"

        return current_value, playback_state, (not playback_state.get("playing", False)), ("Pause" if playback_state.get("playing", False) else "Play")

    @app.callback(
        Output("simulation-graph", "figure"),
        Input("simulation-store", "data"),
        Input("step-slider", "value"),
        Input("hide-edges-input", "value"),
    )
    def _render_step(
        simulation_data: dict[str, object] | None,
        step_value: int,
        hide_edges: list[str],
    ):
        return _render_dashboard_figure(
            base_countries,
            simulation_data,
            int(step_value or 0),
            "hide" in (hide_edges or []),
        )

    requested_port = int(getattr(args, "port", 8050))
    port = _find_available_port(requested_port)
    url = f"http://127.0.0.1:{port}/"
    if port != requested_port:
        print(f"Port {requested_port} is busy. Using {url} instead.")

    print(f"Opening {url} in your browser...")
    _open_browser_when_ready(url)
    app.run(debug=False, host="127.0.0.1", port=port)
