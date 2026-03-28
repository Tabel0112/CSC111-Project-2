"""Tests for Plotly visualization assembly."""

from __future__ import annotations

import unittest

import plotly.graph_objects as go

from country_node import CountryNode
from visualization import create_simulation_figure, create_step_figure


def build_visualization_graph() -> dict[str, CountryNode]:
    """Return a tiny graph with coordinates for visualization tests."""
    usa = CountryNode("USA", "United States", 100.0, 38.0, -97.0)
    can = CountryNode("CAN", "Canada", 50.0, 56.0, -106.0)
    mex = CountryNode("MEX", "Mexico", 40.0, 23.0, -102.0)

    usa.add_trading_partner(can, 0.3)
    mex.add_trading_partner(can, 0.2)

    return {"USA": usa, "CAN": can, "MEX": mex}


class TestVisualization(unittest.TestCase):
    """Tests for simulation figure creation."""

    def test_create_simulation_figure_uses_country_shapes(self) -> None:
        """The base map should include a choropleth country layer."""
        countries = build_visualization_graph()
        wave_history = [
            {
                "step": 0,
                "shock_data": {"USA": 0.2},
                "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.08, "MEX": 0.08},
                "pressure_data": {"CAN": 0.06},
            },
            {
                "step": 1,
                "shock_data": {"CAN": 0.06},
                "health_data": {"USA": 0.82, "CAN": 0.94, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.04, "MEX": 0.08},
                "pressure_data": {"MEX": 0.02},
            },
        ]

        figure = create_simulation_figure(countries, wave_history, {"USA", "CAN", "MEX"}, show_edges=True)

        self.assertTrue(any(isinstance(trace, go.Choropleth) for trace in figure.data))
        self.assertTrue(
            any(isinstance(trace, go.Scattergeo) and trace.mode == "markers" for trace in figure.data)
        )

    def test_edges_only_follow_currently_active_wave(self) -> None:
        """Edge traces should only include lines touching the active wave countries."""
        countries = build_visualization_graph()
        wave_history = [
            {
                "step": 0,
                "shock_data": {"USA": 0.2},
                "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.08, "MEX": 0.08},
                "pressure_data": {"CAN": 0.06},
            },
            {
                "step": 1,
                "shock_data": {"CAN": 0.06},
                "health_data": {"USA": 0.82, "CAN": 0.94, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.04, "MEX": 0.08},
                "pressure_data": {"MEX": 0.02},
            },
        ]

        figure = create_simulation_figure(countries, wave_history, {"USA", "CAN", "MEX"}, show_edges=True)

        base_edge_trace = next(
            trace for trace in figure.data
            if isinstance(trace, go.Scattergeo) and trace.mode == "lines"
        )
        next_edge_trace = next(
            trace for trace in figure.frames[1].data
            if isinstance(trace, go.Scattergeo) and trace.mode == "lines"
        )

        self.assertEqual(base_edge_trace.lat.count(None), 2)
        self.assertEqual(next_edge_trace.lat.count(None), 2)

    def test_slider_uses_step_label(self) -> None:
        """The replay slider should be labeled by step."""
        countries = build_visualization_graph()
        step_history = [
            {
                "step": 0,
                "shock_data": {"USA": 0.2},
                "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.08, "MEX": 0.08},
                "pressure_data": {"CAN": 0.06},
            }
        ]

        figure = create_simulation_figure(countries, step_history, {"USA", "CAN", "MEX"})

        self.assertEqual(figure.layout.sliders[0].currentvalue.prefix, "Step: ")

    def test_create_step_figure_is_static(self) -> None:
        """The dashboard step figure should render one step without animation frames."""
        countries = build_visualization_graph()
        step_history = [
            {
                "step": 0,
                "shock_data": {"USA": 0.2},
                "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.08, "MEX": 0.08},
                "pressure_data": {"CAN": 0.06},
            },
            {
                "step": 1,
                "shock_data": {"CAN": 0.06},
                "health_data": {"USA": 0.82, "CAN": 0.94, "MEX": 1.0},
                "inventory_data": {"USA": 0.08, "CAN": 0.04, "MEX": 0.08},
                "pressure_data": {"MEX": 0.02},
            },
        ]

        figure = create_step_figure(countries, step_history, {"USA", "CAN", "MEX"}, 1)

        self.assertEqual(len(figure.frames), 0)
        self.assertIn("Step 1", figure.layout.title.text)


if __name__ == "__main__":
    unittest.main()
