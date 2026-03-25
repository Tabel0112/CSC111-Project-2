"""Tests for Plotly visualization assembly."""

from __future__ import annotations

import unittest

import plotly.graph_objects as go

from country_node import CountryNode
from visualization import create_simulation_figure


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
            {"wave": 0, "shock_data": {"USA": 0.2}, "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0}},
            {"wave": 1, "shock_data": {"CAN": 0.06}, "health_data": {"USA": 0.8, "CAN": 0.94, "MEX": 1.0}},
        ]

        figure = create_simulation_figure(countries, wave_history, {"USA", "CAN", "MEX"})

        self.assertIsInstance(figure.data[1], go.Choropleth)
        self.assertIsInstance(figure.data[2], go.Scattergeo)

    def test_edges_only_follow_currently_active_wave(self) -> None:
        """Edge traces should only include lines touching the active wave countries."""
        countries = build_visualization_graph()
        wave_history = [
            {"wave": 0, "shock_data": {"USA": 0.2}, "health_data": {"USA": 0.8, "CAN": 1.0, "MEX": 1.0}},
            {"wave": 1, "shock_data": {"CAN": 0.06}, "health_data": {"USA": 0.8, "CAN": 0.94, "MEX": 1.0}},
        ]

        figure = create_simulation_figure(countries, wave_history, {"USA", "CAN", "MEX"})

        base_edge_trace = figure.data[0]
        next_edge_trace = figure.frames[1].data[0]

        self.assertEqual(base_edge_trace.lat.count(None), 1)
        self.assertEqual(next_edge_trace.lat.count(None), 2)


if __name__ == "__main__":
    unittest.main()
