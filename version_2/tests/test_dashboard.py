"""Tests for dashboard helper functions."""

from __future__ import annotations

import unittest

from country_node import CountryNode
from dashboard import (
    _build_slider_marks,
    _run_simulation_from_controls,
    sync_shock_rows,
)
from runtime_options import choose_visible_country_codes


class TestDashboardHelpers(unittest.TestCase):
    """Tests for pure dashboard helper functions."""

    def test_sync_shock_rows_preserves_existing_values(self) -> None:
        """Existing shock values should be preserved when countries stay selected."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }
        rows = sync_shock_rows(
            ["USA", "DEU"],
            [{"code": "USA", "country": "United States", "shock": 0.42}],
            countries,
        )

        self.assertEqual(rows[0]["shock"], 0.42)
        self.assertEqual(rows[1]["country"], "Germany")

    def test_build_slider_marks_covers_endpoints(self) -> None:
        """Slider marks should always include the first and last step."""
        marks = _build_slider_marks(18)

        self.assertEqual(marks[0], "0")
        self.assertEqual(marks[17], "17")

    def test_run_simulation_from_controls_falls_back_to_selected_codes(self) -> None:
        """Selected countries should still run if the editable shock table is temporarily empty."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.5)
        countries = {"USA": usa, "CAN": can}

        simulation_data, status = _run_simulation_from_controls(
            countries,
            ["USA"],
            [],
            threshold=0.01,
            top_n=2,
            top_k=2,
            _hide_edges=False,
        )

        self.assertGreaterEqual(len(simulation_data["step_history"]), 1)
        self.assertIn("Selected 1 countries.", status)

    def test_choose_visible_country_codes_keeps_pressured_countries(self) -> None:
        """Pressured countries should remain visible even when outside the top-n ranking."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "ATG": CountryNode("ATG", "Antigua and Barbuda", 1.0),
        }
        step_history = [
            {"step": 0, "shock_data": {"USA": 0.2}, "health_data": {}, "pressure_data": {"ATG": 0.05}},
        ]

        visible_codes = choose_visible_country_codes(countries, step_history, top_n=2, metric="gdp")

        self.assertEqual(visible_codes, {"USA", "CHN", "ATG"})


if __name__ == "__main__":
    unittest.main()
