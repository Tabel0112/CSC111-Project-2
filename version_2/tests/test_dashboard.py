"""Tests for dashboard helper functions."""

from __future__ import annotations

import unittest

from country_node import CountryNode
from dashboard import _build_slider_marks, shock_rows_to_initial_inputs, sync_shock_rows


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

    def test_shock_rows_to_initial_inputs_formats_strings(self) -> None:
        """Table rows should convert cleanly into runtime strings."""
        initial_countries, initial_shocks = shock_rows_to_initial_inputs(
            [
                {"code": "USA", "country": "United States", "shock": 0.4},
                {"code": "DEU", "country": "Germany", "shock": 0.25},
            ]
        )

        self.assertEqual(initial_countries, "United States; Germany")
        self.assertEqual(initial_shocks, "0.4,0.25")

    def test_build_slider_marks_covers_endpoints(self) -> None:
        """Slider marks should always include the first and last step."""
        marks = _build_slider_marks(18)

        self.assertEqual(marks[0], "0")
        self.assertEqual(marks[17], "17")


if __name__ == "__main__":
    unittest.main()
