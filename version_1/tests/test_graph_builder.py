"""Tests for graph construction."""

from __future__ import annotations

import unittest

from config import MAX_EDGE_WEIGHT
from country_node import CountryNode
from graph_builder import (
    build_trade_graph,
    compute_edge_weight,
    get_visible_country_codes_by_metric,
)


class TestGraphBuilder(unittest.TestCase):
    """Tests for trade graph creation."""

    def test_edge_weight_is_capped(self) -> None:
        """Very large trade ratios should be capped for stability."""
        self.assertEqual(compute_edge_weight(500.0, 1.0), MAX_EDGE_WEIGHT)

    def test_edge_weight_uses_importer_gdp(self) -> None:
        """Edges should be scaled by importer GDP."""
        gdp_data = {
            "USA": {"name": "United States", "gdp": 100.0},
            "CAN": {"name": "Canada", "gdp": 50.0},
        }
        coordinates = {"USA": (0.0, 0.0), "CAN": (1.0, 1.0)}
        trade_data = [
            {"exporter_code": "USA", "importer_code": "CAN", "trade_value": 10.0}
        ]

        countries = build_trade_graph(gdp_data, trade_data, coordinates)
        usa = countries["USA"]
        can = countries["CAN"]

        self.assertAlmostEqual(usa.trading_partners[can], 0.2)

    def test_visible_country_codes_can_rank_by_exports(self) -> None:
        """Visibility ranking should support export-based ordering."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        mex = CountryNode("MEX", "Mexico", 40.0)

        usa.add_trading_partner(can, 0.4)
        usa.add_trading_partner(mex, 0.3)
        can.add_trading_partner(mex, 0.1)

        visible = get_visible_country_codes_by_metric(
            {"USA": usa, "CAN": can, "MEX": mex},
            top_n=1,
            metric="exports",
        )

        self.assertEqual(visible, {"USA"})


if __name__ == "__main__":
    unittest.main()
