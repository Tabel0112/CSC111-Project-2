"""Tests for graph construction."""

from __future__ import annotations

import unittest

from config import MAX_EDGE_WEIGHT
from country_node import CountryNode
from graph_builder import (
    build_country_resilience_profiles,
    build_trade_graph,
    clone_trade_graph,
    compute_demand_weight,
    compute_supply_weight,
    get_visible_country_codes_by_metric,
)


class TestGraphBuilder(unittest.TestCase):
    """Tests for trade graph creation."""

    def test_edge_weight_is_capped(self) -> None:
        """Very large trade ratios should be capped for stability."""
        self.assertEqual(compute_supply_weight(90.0, 100.0), MAX_EDGE_WEIGHT)
        self.assertEqual(compute_demand_weight(90.0, 100.0), MAX_EDGE_WEIGHT)

    def test_edge_weight_uses_importer_and_exporter_totals(self) -> None:
        """Edges should store both supply-side and demand-side dependence."""
        gdp_data = {
            "USA": {"name": "United States", "gdp": 100.0},
            "CAN": {"name": "Canada", "gdp": 50.0},
            "MEX": {"name": "Mexico", "gdp": 40.0},
        }
        coordinates = {"USA": (0.0, 0.0), "CAN": (1.0, 1.0), "MEX": (2.0, 2.0)}
        trade_data = [
            {"exporter_code": "USA", "importer_code": "CAN", "trade_value": 10.0},
            {"exporter_code": "MEX", "importer_code": "CAN", "trade_value": 30.0},
        ]

        countries = build_trade_graph(gdp_data, trade_data, coordinates)
        usa = countries["USA"]
        can = countries["CAN"]

        self.assertAlmostEqual(usa.trading_partners[can]["supply_weight"], 0.25)
        self.assertAlmostEqual(usa.trading_partners[can]["demand_weight"], MAX_EDGE_WEIGHT)

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

    def test_build_trade_graph_tracks_total_imports_and_exports(self) -> None:
        """Graph construction should preserve raw trade totals on country nodes."""
        gdp_data = {
            "USA": {"name": "United States", "gdp": 100.0},
            "CAN": {"name": "Canada", "gdp": 50.0},
        }
        trade_data = [
            {"exporter_code": "USA", "importer_code": "CAN", "trade_value": 10.0},
            {"exporter_code": "CAN", "importer_code": "USA", "trade_value": 4.0},
        ]

        countries = build_trade_graph(gdp_data, trade_data, {})

        self.assertEqual(countries["USA"].total_exports, 10.0)
        self.assertEqual(countries["USA"].total_imports, 4.0)
        self.assertEqual(countries["CAN"].total_exports, 4.0)
        self.assertEqual(countries["CAN"].total_imports, 10.0)

    def test_resilience_profiles_reward_diversified_importers(self) -> None:
        """More diversified importers should receive higher substitution and inventory values."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        mex = CountryNode("MEX", "Mexico", 40.0)
        deu = CountryNode("DEU", "Germany", 80.0)

        usa.add_trading_partner(can, 0.8)
        mex.add_trading_partner(can, 0.2)
        usa.add_trading_partner(deu, 0.34)
        can.add_trading_partner(deu, 0.33)
        mex.add_trading_partner(deu, 0.33)

        profiles = build_country_resilience_profiles(
            {"USA": usa, "CAN": can, "MEX": mex, "DEU": deu}
        )

        self.assertGreater(
            profiles["substitution_rates"]["DEU"],
            profiles["substitution_rates"]["CAN"],
        )
        self.assertGreater(
            profiles["inventory_buffers"]["DEU"],
            profiles["inventory_buffers"]["CAN"],
        )
        self.assertGreater(
            profiles["delay_shares"]["DEU"],
            profiles["delay_shares"]["CAN"],
        )

    def test_clone_trade_graph_returns_detached_copy(self) -> None:
        """Cloning should preserve structure without sharing partner dictionaries."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.4)

        cloned = clone_trade_graph({"USA": usa, "CAN": can})
        cloned["USA"].trading_partners.clear()

        self.assertEqual(len(usa.trading_partners), 1)
        self.assertEqual(len(cloned["USA"].trading_partners), 0)


if __name__ == "__main__":
    unittest.main()
